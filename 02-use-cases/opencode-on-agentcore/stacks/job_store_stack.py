# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""OpenCode Job Store stack — DynamoDB table for job audit/history (user-scoped).

Simplified 4-state model: RUNNING, COMPLETE, FAILED, CANCELLED.
DynamoDB is used for lightweight audit and history records only — not as a state machine.

PK: user#{user_id}   SK: job#{job_id}#{created_at_iso}
GSI1: status#{status} / created_at  (admin monitoring by status)

Record attributes:
  job_id, user_id, status, task_description, repo_url, base_branch,
  target_branch, runtime_session_id, pr_url, stop_reason,
  files_edited, duration_seconds, error, created_at, completed_at

Requirements: 8.1, 8.5
"""

import aws_cdk as cdk
from aws_cdk import (
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_dynamodb as dynamodb,
    aws_kms as kms,
    aws_sns as sns,
    RemovalPolicy,
)
import cdk_nag
from constructs import Construct


class JobStoreStack(cdk.Stack):
    """DynamoDB Job Store table (user-partitioned, 4-state audit/history)."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        cmk: kms.IKey,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # -----------------------------------------------------------------
        # Jobs table (opencode-jobs)
        # PK: user#{user_id}  SK: job#{job_id}#{created_at_iso}
        # States: RUNNING | COMPLETE | FAILED | CANCELLED
        # -----------------------------------------------------------------
        self.job_table = dynamodb.Table(
            self,
            "JobsTable",
            table_name="opencode-jobs",
            partition_key=dynamodb.Attribute(
                name="PK", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="SK", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
            encryption_key=cmk,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True,
            ),
            removal_policy=RemovalPolicy.RETAIN,
        )

        # -----------------------------------------------------------------
        # GSI1 — admin monitoring by status
        # PK: status#{status}  SK: created_at
        #
        # HOT-PARTITION RISK: GSI1 partitions by status#{status} with
        # only 4 possible values (RUNNING, COMPLETE, FAILED, CANCELLED).
        # At low volume this is fine; at higher volume it hits the
        # ~3k RCU / 1k WCU per-partition limit.
        # When scale warrants it, shard the key:
        #   GSI1PK = f"status#{status}#{hash(job_id) % SHARD_COUNT}"
        # and fan out admin queries across shards.
        # -----------------------------------------------------------------
        self.job_table.add_global_secondary_index(
            index_name="GSI1",
            partition_key=dynamodb.Attribute(
                name="GSI1PK", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="GSI1SK", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.INCLUDE,
            non_key_attributes=["job_id", "user_id", "repo_url", "created_at"],
        )

        # -----------------------------------------------------------------
        # cdk-nag suppressions
        # -----------------------------------------------------------------
        cdk_nag.NagSuppressions.add_resource_suppressions(
            self.job_table,
            [
                cdk_nag.NagPackSuppression(
                    id="AwsSolutions-DDB3",
                    reason="Point-in-time recovery is enabled via point_in_time_recovery=True.",
                ),
            ],
        )

        # -----------------------------------------------------------------
        # SNS topic for operational alerts
        # -----------------------------------------------------------------
        self.ops_alerts_topic = sns.Topic(
            self,
            "OpsAlertsTopic",
            topic_name="opencode-ops-alerts",
            master_key=cmk,
        )

        cdk.CfnOutput(
            self,
            "OpsAlertsTopicArn",
            value=self.ops_alerts_topic.topic_arn,
            description="SNS topic ARN for operational alerts",
        )

        # -----------------------------------------------------------------
        # CloudWatch alarm — GSI1 throttled requests
        # Fires when any throttled request occurs on the GSI1 index
        # within a 5-minute evaluation window.
        # -----------------------------------------------------------------
        gsi1_throttle_metric = cloudwatch.Metric(
            namespace="AWS/DynamoDB",
            metric_name="ThrottledRequests",
            dimensions_map={
                "TableName": self.job_table.table_name,
                "GlobalSecondaryIndexName": "GSI1",
            },
            period=cdk.Duration.seconds(300),
            statistic="Sum",
        )

        self.gsi1_throttle_alarm = cloudwatch.Alarm(
            self,
            "GSI1ThrottleAlarm",
            alarm_name="opencode-gsi1-throttled-requests",
            metric=gsi1_throttle_metric,
            threshold=0,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            evaluation_periods=1,
            alarm_description=(
                "GSI1 on opencode-jobs is receiving throttled requests. "
                "This indicates the hot-partition limit (~3k RCU / 1k WCU) "
                "may be reached. Consider implementing the sharding strategy "
                "documented in stacks/job_store_stack.py."
            ),
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )

        self.gsi1_throttle_alarm.add_alarm_action(
            cw_actions.SnsAction(self.ops_alerts_topic)
        )
