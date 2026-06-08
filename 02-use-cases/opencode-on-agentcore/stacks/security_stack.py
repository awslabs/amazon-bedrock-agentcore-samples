# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""OpenCode Security stack — KMS CMK, Secrets Manager, Cognito User Pool, CloudTrail.

Requirements: 6.3, 10.6
"""

import aws_cdk as cdk
from aws_cdk import (
    aws_cloudtrail as cloudtrail,
    aws_cognito as cognito,
    aws_iam as iam,
    aws_kms as kms,
    aws_logs as logs,
    aws_s3 as s3,
    aws_secretsmanager as secretsmanager,
    RemovalPolicy,
)
import cdk_nag
from constructs import Construct

from stacks import context_bool, retention_days


class SecurityStack(cdk.Stack):
    """KMS CMK, Secrets Manager secrets, Cognito User Pool, CloudTrail."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        log_retention = self.node.try_get_context("cloudwatch_log_retention_days") or 90

        # -----------------------------------------------------------------
        # KMS Customer-Managed Key (CMK)
        # -----------------------------------------------------------------
        self.cmk = kms.Key(
            self,
            "OpenCodeCmk",
            alias="opencode-cmk",
            description="OpenCode customer-managed key for encryption at rest",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        for service_principal in [
            "s3.amazonaws.com",
            "dynamodb.amazonaws.com",
            "secretsmanager.amazonaws.com",
        ]:
            self.cmk.grant_encrypt_decrypt(
                iam.ServicePrincipal(service_principal)
            )

        self.cmk.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AllowCloudWatchLogs",
                actions=[
                    "kms:Encrypt*",
                    "kms:Decrypt*",
                    "kms:ReEncrypt*",
                    "kms:GenerateDataKey*",
                    "kms:Describe*",
                ],
                principals=[
                    iam.ServicePrincipal(
                        f"logs.{self.region}.amazonaws.com"
                    )
                ],
                resources=["*"],
                conditions={
                    "ArnLike": {
                        "kms:EncryptionContext:aws:logs:arn": f"arn:aws:logs:{self.region}:{self.account}:*"
                    }
                },
            )
        )

        # -----------------------------------------------------------------
        # Secrets Manager — webhook signing secret
        # -----------------------------------------------------------------
        self.webhook_signing_secret = secretsmanager.Secret(
            self,
            "WebhookSigningSecret",
            secret_name="opencode/webhook-signing-secret",
            description="Webhook signing secret for callback URL verification",
            encryption_key=self.cmk,
        )

        # -----------------------------------------------------------------
        # Cognito User Pool — custom:role attribute for Cedar policies
        # -----------------------------------------------------------------
        self.user_pool = cognito.UserPool(
            self,
            "OpenCodeUserPool",
            user_pool_name="opencode-user-pool",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=12,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
            ),
            standard_threat_protection_mode=cognito.StandardThreatProtectionMode.FULL_FUNCTION,
            custom_attributes={
                "role": cognito.StringAttribute(
                    min_len=1,
                    max_len=20,
                    mutable=True,
                ),
            },
            removal_policy=RemovalPolicy.RETAIN,
        )

        self.user_pool_client = self.user_pool.add_client(
            "OpenCodeAppClient",
            user_pool_client_name="opencode-app-client",
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
            ),
            id_token_validity=cdk.Duration.hours(24),
            access_token_validity=cdk.Duration.hours(24),
            refresh_token_validity=cdk.Duration.days(30),
        )

        # Stable CfnOutput exports for Cognito resources
        cdk.CfnOutput(
            self,
            "UserPoolId",
            value=self.user_pool.user_pool_id,
            export_name="opencode-user-pool-id",
        )
        cdk.CfnOutput(
            self,
            "UserPoolClientId",
            value=self.user_pool_client.user_pool_client_id,
            export_name="opencode-user-pool-client-id",
        )

        # Cognito User Pool groups for role-based access
        for group_name, desc in [
            ("admin", "Platform administrators with full access"),
            ("developer", "Developers who can submit and manage tasks"),
            ("readonly", "Read-only users who can view job status"),
        ]:
            cognito.CfnUserPoolGroup(
                self,
                f"{group_name.capitalize()}Group",
                group_name=group_name,
                user_pool_id=self.user_pool.user_pool_id,
                description=desc,
            )

        # -----------------------------------------------------------------
        # Optional CloudTrail
        # -----------------------------------------------------------------
        if context_bool(self, "enable_cloudtrail"):
            trail_bucket = s3.Bucket(
                self,
                "CloudTrailBucket",
                bucket_name=f"opencode-cloudtrail-{self.account}-{self.region}",
                encryption=s3.BucketEncryption.KMS,
                encryption_key=self.cmk,
                block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                enforce_ssl=True,
                versioned=True,
                removal_policy=RemovalPolicy.RETAIN,
                auto_delete_objects=False,
                object_ownership=s3.ObjectOwnership.BUCKET_OWNER_ENFORCED,
            )

            trail_bucket.add_to_resource_policy(
                iam.PolicyStatement(
                    sid="AWSCloudTrailAclCheck",
                    effect=iam.Effect.ALLOW,
                    principals=[iam.ServicePrincipal("cloudtrail.amazonaws.com")],
                    actions=["s3:GetBucketAcl"],
                    resources=[trail_bucket.bucket_arn],
                )
            )
            trail_bucket.add_to_resource_policy(
                iam.PolicyStatement(
                    sid="AWSCloudTrailWrite",
                    effect=iam.Effect.ALLOW,
                    principals=[iam.ServicePrincipal("cloudtrail.amazonaws.com")],
                    actions=["s3:PutObject"],
                    resources=[f"{trail_bucket.bucket_arn}/AWSLogs/{self.account}/*"],
                    conditions={
                        "StringEquals": {
                            "s3:x-amz-acl": "bucket-owner-full-control"
                        }
                    },
                )
            )

            trail_log_group = logs.LogGroup(
                self,
                "CloudTrailLogGroup",
                retention=retention_days(log_retention),
                encryption_key=self.cmk,
                removal_policy=RemovalPolicy.RETAIN,
            )

            self.trail = cloudtrail.Trail(
                self,
                "OpenCodeTrail",
                trail_name="opencode-trail",
                bucket=trail_bucket,
                is_multi_region_trail=False,
                include_global_service_events=True,
                enable_file_validation=True,
                send_to_cloud_watch_logs=True,
                cloud_watch_log_group=trail_log_group,
                encryption_key=self.cmk,
            )

            cdk_nag.NagSuppressions.add_resource_suppressions(
                trail_bucket,
                [cdk_nag.NagPackSuppression(
                    id="AwsSolutions-S1",
                    reason=(
                        "CloudTrail bucket is the audit-log destination itself; "
                        "enabling server access logging on it would create a "
                        "recursive logging chain with no additional audit value. "
                        "Aligned with AWS Well-Architected SEC04-BP02 guidance "
                        "on logging destinations."
                    ),
                )],
            )
            cdk_nag.NagSuppressions.add_resource_suppressions(
                self.trail,
                [cdk_nag.NagPackSuppression(
                    id="AwsSolutions-IAM5",
                    reason=(
                        "CloudTrail service-linked CloudWatch Logs role uses a "
                        "wildcard on log-stream ARN within a log group owned by "
                        "this stack; the log group ARN itself is pinned. "
                        "Wildcard scope: 'log-stream:*' within 'log-group:/aws/"
                        "cloudtrail/opencode/*'."
                    ),
                )],
                apply_to_children=True,
            )

        # -----------------------------------------------------------------
        # cdk-nag suppressions
        # -----------------------------------------------------------------
        cdk_nag.NagSuppressions.add_resource_suppressions(
            self.webhook_signing_secret,
            [cdk_nag.NagPackSuppression(
                id="AwsSolutions-SMG4",
                reason="Webhook signing secret is externally managed. Automatic rotation deferred to Phase 2.",
            )],
        )

        cdk_nag.NagSuppressions.add_resource_suppressions(
            self.cmk,
            [cdk_nag.NagPackSuppression(
                id="AwsSolutions-KMS5",
                reason=(
                    "Key rotation is enabled via enable_key_rotation=True; "
                    "AWS KMS rotates the key material annually. Key "
                    "management strategy is documented in "
                    "docs/HARDENING.md#key-management-strategy."
                ),
            )],
        )

        cdk_nag.NagSuppressions.add_resource_suppressions(
            self.user_pool,
            [
                cdk_nag.NagPackSuppression(
                    id="AwsSolutions-COG2",
                    reason=(
                        "MFA is not enforced on the sample user pool because "
                        "this is a demo-scoped deployment. Production adopters "
                        "are expected to enable MFA per Cognito documentation; "
                        "the residual risk is called out in "
                        "docs/HARDENING.md#known-limitations."
                    ),
                ),
                cdk_nag.NagPackSuppression(
                    id="AwsSolutions-COG1",
                    reason="Password policy is configured with min_length=12 and all complexity requirements.",
                ),
                cdk_nag.NagPackSuppression(
                    id="AwsSolutions-COG8",
                    reason="Plus tier not required for sample/dev deployment. Standard threat protection is enabled.",
                ),
            ],
        )
