# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for Job Store stack (stacks/job_store_stack.py).

Validates: Requirements 7.1, 12.1
- Jobs table key schemas match design (PK, SK, GSI1)
- KMS encryption is configured
- Point-in-time recovery is enabled
"""

import json
from pathlib import Path

import aws_cdk as cdk
from aws_cdk import assertions
import pytest

from stacks.security_stack import SecurityStack
from stacks.job_store_stack import JobStoreStack

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CDK_JSON_PATH = Path(__file__).resolve().parents[2] / "cdk.json"


def _load_cdk_context() -> dict:
    with open(CDK_JSON_PATH) as f:
        return json.load(f)["context"]


def _build_job_store_template() -> assertions.Template:
    ctx = _load_cdk_context()
    app = cdk.App(context=ctx)
    env = cdk.Environment(account="123456789012", region="us-east-1")
    security_stack = SecurityStack(app, "TestSecurity", env=env)
    stack = JobStoreStack(app, "TestJobStore", cmk=security_stack.cmk, env=env)
    return assertions.Template.from_stack(stack)


def _get_tables(tpl: dict) -> dict[str, dict]:
    """Return a mapping of table_name → resource properties for DynamoDB tables."""
    tables = {}
    for lid, res in tpl["Resources"].items():
        if res["Type"] == "AWS::DynamoDB::Table":
            name = res["Properties"].get("TableName", lid)
            tables[name] = res["Properties"]
    return tables


# ---------------------------------------------------------------------------
# Jobs table — key schema tests (Requirement 7.1)
# ---------------------------------------------------------------------------

class TestJobsTableKeySchema:
    """Verify opencode-jobs table PK, SK, and GSI key schemas."""

    def test_jobs_table_exists(self):
        template = _build_job_store_template()
        template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {"TableName": "opencode-jobs"},
        )

    def test_jobs_table_pk_is_string(self):
        """PK attribute named 'PK' with type String."""
        template = _build_job_store_template()
        template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {
                "TableName": "opencode-jobs",
                "KeySchema": assertions.Match.array_with([
                    assertions.Match.object_like({"AttributeName": "PK", "KeyType": "HASH"}),
                ]),
                "AttributeDefinitions": assertions.Match.array_with([
                    assertions.Match.object_like({"AttributeName": "PK", "AttributeType": "S"}),
                ]),
            },
        )

    def test_jobs_table_sk_is_string(self):
        """SK attribute named 'SK' with type String."""
        template = _build_job_store_template()
        template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {
                "TableName": "opencode-jobs",
                "KeySchema": assertions.Match.array_with([
                    assertions.Match.object_like({"AttributeName": "SK", "KeyType": "RANGE"}),
                ]),
                "AttributeDefinitions": assertions.Match.array_with([
                    assertions.Match.object_like({"AttributeName": "SK", "AttributeType": "S"}),
                ]),
            },
        )

    def test_jobs_table_has_one_gsi(self):
        """Jobs table has exactly 1 GSI (GSI1)."""
        template = _build_job_store_template()
        tpl = template.to_json()
        tables = _get_tables(tpl)
        gsis = tables["opencode-jobs"].get("GlobalSecondaryIndexes", [])
        assert len(gsis) == 1, f"Expected 1 GSI, got {len(gsis)}"

    def test_gsi1_key_schema(self):
        """GSI1 PK=GSI1PK (HASH), SK=GSI1SK (RANGE)."""
        template = _build_job_store_template()
        template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {
                "TableName": "opencode-jobs",
                "GlobalSecondaryIndexes": assertions.Match.array_with([
                    assertions.Match.object_like({
                        "IndexName": "GSI1",
                        "KeySchema": assertions.Match.array_with([
                            assertions.Match.object_like({"AttributeName": "GSI1PK", "KeyType": "HASH"}),
                            assertions.Match.object_like({"AttributeName": "GSI1SK", "KeyType": "RANGE"}),
                        ]),
                    }),
                ]),
            },
        )

    def test_gsi1_projection_includes_expected_attributes(self):
        """GSI1 projects: job_id, user_id, repo_url, created_at."""
        template = _build_job_store_template()
        tpl = template.to_json()
        tables = _get_tables(tpl)
        gsis = tables["opencode-jobs"]["GlobalSecondaryIndexes"]
        gsi1 = next(g for g in gsis if g["IndexName"] == "GSI1")
        projection = gsi1["Projection"]
        assert projection["ProjectionType"] == "INCLUDE"
        expected = {"job_id", "user_id", "repo_url", "created_at"}
        actual = set(projection.get("NonKeyAttributes", []))
        assert expected == actual, f"GSI1 projection mismatch: expected {expected}, got {actual}"


# ---------------------------------------------------------------------------
# KMS encryption tests (Requirement 10.4, 12.1)
# ---------------------------------------------------------------------------

class TestKmsEncryption:
    """Verify jobs table uses customer-managed KMS encryption."""

    def test_jobs_table_uses_kms_encryption(self):
        template = _build_job_store_template()
        tpl = template.to_json()
        tables = _get_tables(tpl)
        sse = tables["opencode-jobs"].get("SSESpecification", {})
        assert sse.get("SSEEnabled") is True, "Jobs table SSE not enabled"
        assert sse.get("SSEType") == "KMS", "Jobs table not using KMS encryption"
        assert sse.get("KMSMasterKeyId") is not None, "Jobs table missing KMS key reference"


# ---------------------------------------------------------------------------
# Point-in-time recovery tests (Requirement 12.1)
# ---------------------------------------------------------------------------

class TestPointInTimeRecovery:
    """Verify PITR is enabled on jobs table."""

    def test_jobs_table_pitr_enabled(self):
        template = _build_job_store_template()
        tpl = template.to_json()
        tables = _get_tables(tpl)
        pitr = tables["opencode-jobs"].get("PointInTimeRecoverySpecification", {})
        assert pitr.get("PointInTimeRecoveryEnabled") is True, (
            "Jobs table PITR not enabled"
        )


# ---------------------------------------------------------------------------
# Table count and billing mode
# ---------------------------------------------------------------------------

class TestTableBasics:
    """Verify table count and billing mode."""

    def test_one_dynamodb_table_created(self):
        """Only 1 DynamoDB table (opencode-jobs)."""
        template = _build_job_store_template()
        template.resource_count_is("AWS::DynamoDB::Table", 1)

    def test_jobs_table_pay_per_request(self):
        template = _build_job_store_template()
        template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {
                "TableName": "opencode-jobs",
                "BillingMode": "PAY_PER_REQUEST",
            },
        )

    def test_jobs_table_retained_on_delete(self):
        template = _build_job_store_template()
        tpl = template.to_json()
        for lid, res in tpl["Resources"].items():
            if res["Type"] == "AWS::DynamoDB::Table" and res["Properties"].get("TableName") == "opencode-jobs":
                assert res.get("DeletionPolicy") == "Retain" or res.get("UpdateReplacePolicy") == "Retain", (
                    "Jobs table should have Retain removal policy"
                )
                break


# ---------------------------------------------------------------------------
# CloudWatch alarm tests (Requirement 2.1, 2.2, 2.3, 2.4 — GSI1 throttling)
# ---------------------------------------------------------------------------

class TestGSI1ThrottleAlarm:
    """Verify CloudWatch alarm for GSI1 throttled requests."""

    def test_alarm_resource_exists(self):
        """Template contains a CloudWatch alarm."""
        template = _build_job_store_template()
        template.resource_count_is("AWS::CloudWatch::Alarm", 1)

    def test_alarm_metric_name(self):
        """Alarm uses ThrottledRequests metric."""
        template = _build_job_store_template()
        template.has_resource_properties(
            "AWS::CloudWatch::Alarm",
            {"MetricName": "ThrottledRequests"},
        )

    def test_alarm_namespace(self):
        """Alarm uses AWS/DynamoDB namespace."""
        template = _build_job_store_template()
        template.has_resource_properties(
            "AWS::CloudWatch::Alarm",
            {"Namespace": "AWS/DynamoDB"},
        )

    def test_alarm_threshold_and_comparison(self):
        """Alarm threshold is 0 with GREATER_THAN comparison."""
        template = _build_job_store_template()
        template.has_resource_properties(
            "AWS::CloudWatch::Alarm",
            {
                "Threshold": 0,
                "ComparisonOperator": "GreaterThanThreshold",
            },
        )

    def test_alarm_evaluation_period_and_period(self):
        """Alarm evaluates 1 period of 300 seconds."""
        template = _build_job_store_template()
        template.has_resource_properties(
            "AWS::CloudWatch::Alarm",
            {
                "EvaluationPeriods": 1,
                "Period": 300,
            },
        )

    def test_alarm_dimensions_include_table_and_gsi(self):
        """Alarm dimensions include TableName and GlobalSecondaryIndexName."""
        template = _build_job_store_template()
        template.has_resource_properties(
            "AWS::CloudWatch::Alarm",
            {
                "Dimensions": assertions.Match.array_with([
                    assertions.Match.object_like({
                        "Name": "GlobalSecondaryIndexName",
                        "Value": "GSI1",
                    }),
                ]),
            },
        )
        # TableName dimension uses a Ref; just verify it's present by name.
        template.has_resource_properties(
            "AWS::CloudWatch::Alarm",
            {
                "Dimensions": assertions.Match.array_with([
                    assertions.Match.object_like({"Name": "TableName"}),
                ]),
            },
        )

    def test_alarm_has_sns_action(self):
        """Alarm has at least one alarm action (SNS topic)."""
        template = _build_job_store_template()
        template.has_resource_properties(
            "AWS::CloudWatch::Alarm",
            {
                "AlarmActions": assertions.Match.any_value(),
            },
        )


# ---------------------------------------------------------------------------
# SNS topic tests (Requirement 2.3 — operational alerts)
# ---------------------------------------------------------------------------

class TestOpsAlertsTopic:
    """Verify SNS topic for operational alerts."""

    def test_sns_topic_exists(self):
        """Template contains an SNS topic."""
        template = _build_job_store_template()
        template.resource_count_is("AWS::SNS::Topic", 1)

    def test_sns_topic_name(self):
        """SNS topic is named opencode-ops-alerts."""
        template = _build_job_store_template()
        template.has_resource_properties(
            "AWS::SNS::Topic",
            {"TopicName": "opencode-ops-alerts"},
        )

    def test_sns_topic_arn_output(self):
        """Stack exports the SNS topic ARN."""
        template = _build_job_store_template()
        template.has_output(
            "OpsAlertsTopicArn",
            {"Description": "SNS topic ARN for operational alerts"},
        )
