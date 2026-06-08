# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for Security stack (stacks/security_stack.py).

Validates:
- KMS CMK key policy allows expected services (S3, DynamoDB, Secrets Manager, CloudWatch Logs)
- Cognito User Pool has required custom attributes (custom:team_id, custom:role)
- CloudTrail is conditionally created based on enable_cloudtrail feature flag
"""

import json
from pathlib import Path

import aws_cdk as cdk
from aws_cdk import assertions
import pytest

from stacks.security_stack import SecurityStack

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CDK_JSON_PATH = Path(__file__).resolve().parents[2] / "cdk.json"


def _load_cdk_context() -> dict:
    with open(CDK_JSON_PATH) as f:
        return json.load(f)["context"]


def _build_security_template(context_overrides: dict | None = None) -> assertions.Template:
    ctx = _load_cdk_context()
    if context_overrides:
        ctx.update(context_overrides)
    app = cdk.App(context=ctx)
    env = cdk.Environment(account="123456789012", region="us-east-1")
    stack = SecurityStack(app, "TestSecurity", env=env)
    return assertions.Template.from_stack(stack)


# ---------------------------------------------------------------------------
# KMS CMK tests (Requirement 10.4)
# ---------------------------------------------------------------------------

class TestKmsCmk:
    """Verify KMS customer-managed key configuration."""

    def test_kms_key_exists(self):
        template = _build_security_template()
        template.resource_count_is("AWS::KMS::Key", 1)

    def test_kms_key_rotation_enabled(self):
        template = _build_security_template()
        template.has_resource_properties(
            "AWS::KMS::Key",
            {"EnableKeyRotation": True},
        )

    def test_kms_key_alias(self):
        template = _build_security_template()
        template.has_resource_properties(
            "AWS::KMS::Alias",
            {"AliasName": "alias/opencode-cmk"},
        )

    def test_kms_key_policy_allows_s3(self):
        """KMS key policy grants encrypt/decrypt to s3.amazonaws.com."""
        template = _build_security_template()
        tpl = template.to_json()
        key_policy = _extract_kms_key_policy(tpl)
        assert _policy_has_service_principal(key_policy, "s3.amazonaws.com"), (
            "KMS key policy missing grant for s3.amazonaws.com"
        )

    def test_kms_key_policy_allows_dynamodb(self):
        template = _build_security_template()
        tpl = template.to_json()
        key_policy = _extract_kms_key_policy(tpl)
        assert _policy_has_service_principal(key_policy, "dynamodb.amazonaws.com"), (
            "KMS key policy missing grant for dynamodb.amazonaws.com"
        )

    def test_kms_key_policy_does_not_grant_sqs(self):
        template = _build_security_template()
        tpl = template.to_json()
        key_policy = _extract_kms_key_policy(tpl)
        assert not _policy_has_service_principal(key_policy, "sqs.amazonaws.com"), (
            "KMS key policy should not grant sqs.amazonaws.com — SQS is no longer used"
        )

    def test_kms_key_policy_allows_secrets_manager(self):
        template = _build_security_template()
        tpl = template.to_json()
        key_policy = _extract_kms_key_policy(tpl)
        assert _policy_has_service_principal(key_policy, "secretsmanager.amazonaws.com"), (
            "KMS key policy missing grant for secretsmanager.amazonaws.com"
        )

    def test_kms_key_policy_allows_cloudwatch_logs(self):
        """CloudWatch Logs uses a condition-based policy statement."""
        template = _build_security_template()
        tpl = template.to_json()
        key_policy = _extract_kms_key_policy(tpl)
        found = False
        for stmt in key_policy.get("Statement", []):
            principals = _flatten_principals(stmt)
            if any("logs" in p and "amazonaws.com" in p for p in principals):
                found = True
                break
        assert found, "KMS key policy missing grant for CloudWatch Logs"

    def test_kms_key_retained_on_delete(self):
        template = _build_security_template()
        tpl = template.to_json()
        for lid, res in tpl["Resources"].items():
            if res["Type"] == "AWS::KMS::Key":
                assert res.get("DeletionPolicy") == "Retain" or res.get("UpdateReplacePolicy") == "Retain", (
                    "KMS key should have Retain removal policy"
                )
                break


# ---------------------------------------------------------------------------
# Secrets Manager tests (Requirement 11.1)
# ---------------------------------------------------------------------------

class TestSecretsManager:
    """Verify Secrets Manager secrets are created with KMS encryption."""

    def test_secrets_created(self):
        """1 secret: webhook-signing-secret only (M2M secret removed)."""
        template = _build_security_template()
        template.resource_count_is("AWS::SecretsManager::Secret", 1)

    def test_webhook_signing_secret_exists(self):
        template = _build_security_template()
        template.has_resource_properties(
            "AWS::SecretsManager::Secret",
            {"Name": "opencode/webhook-signing-secret"},
        )

    def test_all_secrets_encrypted_with_cmk(self):
        """Every secret must reference the KMS key (not use default encryption)."""
        template = _build_security_template()
        tpl = template.to_json()
        secrets = {
            lid: res for lid, res in tpl["Resources"].items()
            if res["Type"] == "AWS::SecretsManager::Secret"
        }
        assert len(secrets) == 1
        for lid, res in secrets.items():
            kms_key_id = res["Properties"].get("KmsKeyId")
            assert kms_key_id is not None, (
                f"Secret {lid} is missing KmsKeyId (not encrypted with CMK)"
            )


# ---------------------------------------------------------------------------
# Cognito User Pool tests (Requirement 6.1, 6.2)
# ---------------------------------------------------------------------------

class TestCognitoUserPool:
    """Verify Cognito User Pool with custom attributes and groups."""

    def test_user_pool_exists(self):
        """1 user pool — Pool A only (M2M Pool B removed)."""
        template = _build_security_template()
        template.resource_count_is("AWS::Cognito::UserPool", 1)

    def test_user_pool_name(self):
        template = _build_security_template()
        template.has_resource_properties(
            "AWS::Cognito::UserPool",
            {"UserPoolName": "opencode-user-pool"},
        )

    def test_custom_role_attribute_only(self):
        """User pool has custom:role string attribute."""
        template = _build_security_template()
        template.has_resource_properties(
            "AWS::Cognito::UserPool",
            {
                "UserPoolName": "opencode-user-pool",
                "Schema": assertions.Match.array_with([
                    assertions.Match.object_like({
                        "Name": "role",
                        "AttributeDataType": "String",
                    }),
                ]),
            },
        )

    def test_custom_role_attribute(self):
        """User pool has custom:role string attribute."""
        template = _build_security_template()
        template.has_resource_properties(
            "AWS::Cognito::UserPool",
            {
                "Schema": assertions.Match.array_with([
                    assertions.Match.object_like({
                        "Name": "role",
                        "AttributeDataType": "String",
                    }),
                ]),
            },
        )

    def test_self_sign_up_disabled(self):
        template = _build_security_template()
        tpl = template.to_json()
        for lid, res in tpl["Resources"].items():
            if res["Type"] == "AWS::Cognito::UserPool":
                pool_name = res["Properties"].get("UserPoolName", "")
                if pool_name == "opencode-user-pool":
                    admin_create = res["Properties"].get("AdminCreateUserConfig", {})
                    assert admin_create.get("AllowAdminCreateUserOnly") is True, (
                        "Self sign-up should be disabled on Pool A"
                    )
                    break

    def test_three_user_pool_groups(self):
        """Three groups: admin, developer, readonly."""
        template = _build_security_template()
        template.resource_count_is("AWS::Cognito::UserPoolGroup", 3)

    def test_admin_group_exists(self):
        template = _build_security_template()
        template.has_resource_properties(
            "AWS::Cognito::UserPoolGroup",
            {"GroupName": "admin"},
        )

    def test_developer_group_exists(self):
        template = _build_security_template()
        template.has_resource_properties(
            "AWS::Cognito::UserPoolGroup",
            {"GroupName": "developer"},
        )

    def test_readonly_group_exists(self):
        template = _build_security_template()
        template.has_resource_properties(
            "AWS::Cognito::UserPoolGroup",
            {"GroupName": "readonly"},
        )

    def test_password_policy_min_length(self):
        template = _build_security_template()
        template.has_resource_properties(
            "AWS::Cognito::UserPool",
            {
                "Policies": assertions.Match.object_like({
                    "PasswordPolicy": assertions.Match.object_like({
                        "MinimumLength": 12,
                    }),
                }),
            },
        )


# ---------------------------------------------------------------------------
# Stable CfnOutput export tests (Requirement H5 — stable export names)
# ---------------------------------------------------------------------------

class TestStableCfnOutputExports:
    """Verify CfnOutput resources with stable export names for Cognito resources."""

    def test_user_pool_id_export(self):
        """Template contains a CfnOutput with Export.Name = opencode-user-pool-id."""
        template = _build_security_template()
        tpl = template.to_json()
        found = any(
            res.get("Type") == "AWS::CloudFormation::Output"
            or (
                "Value" in res.get("Properties", {})
                and res.get("Properties", {}).get("Export", {}).get("Name") == "opencode-user-pool-id"
            )
            for res in tpl.get("Resources", {}).values()
        )
        # CfnOutputs appear in the Outputs section, not Resources
        outputs = tpl.get("Outputs", {})
        export_names = [
            out.get("Export", {}).get("Name")
            for out in outputs.values()
        ]
        assert "opencode-user-pool-id" in export_names, (
            f"Expected export name 'opencode-user-pool-id' in template outputs. "
            f"Found export names: {export_names}"
        )

    def test_user_pool_client_id_export(self):
        """Template contains a CfnOutput with Export.Name = opencode-user-pool-client-id."""
        template = _build_security_template()
        tpl = template.to_json()
        outputs = tpl.get("Outputs", {})
        export_names = [
            out.get("Export", {}).get("Name")
            for out in outputs.values()
        ]
        assert "opencode-user-pool-client-id" in export_names, (
            f"Expected export name 'opencode-user-pool-client-id' in template outputs. "
            f"Found export names: {export_names}"
        )


# ---------------------------------------------------------------------------
# CloudTrail conditional tests (Requirement 12.4)
# ---------------------------------------------------------------------------

class TestCloudTrailConditional:
    """Verify CloudTrail is conditionally created based on feature flag."""

    def test_no_cloudtrail_when_disabled(self):
        """Default cdk.json has enable_cloudtrail=false — no trail resources."""
        template = _build_security_template({"enable_cloudtrail": False})
        template.resource_count_is("AWS::CloudTrail::Trail", 0)

    def test_cloudtrail_created_when_enabled(self):
        template = _build_security_template({"enable_cloudtrail": True})
        template.resource_count_is("AWS::CloudTrail::Trail", 1)

    def test_cloudtrail_name_when_enabled(self):
        template = _build_security_template({"enable_cloudtrail": True})
        template.has_resource_properties(
            "AWS::CloudTrail::Trail",
            {"TrailName": "opencode-trail"},
        )

    def test_cloudtrail_file_validation_enabled(self):
        template = _build_security_template({"enable_cloudtrail": True})
        template.has_resource_properties(
            "AWS::CloudTrail::Trail",
            {"EnableLogFileValidation": True},
        )

    def test_cloudtrail_sends_to_cloudwatch(self):
        template = _build_security_template({"enable_cloudtrail": True})
        template.has_resource_properties(
            "AWS::CloudTrail::Trail",
            {
                "CloudWatchLogsLogGroupArn": assertions.Match.any_value(),
                "CloudWatchLogsRoleArn": assertions.Match.any_value(),
            },
        )

    def test_cloudtrail_bucket_encrypted_with_kms(self):
        """CloudTrail S3 bucket uses KMS encryption."""
        template = _build_security_template({"enable_cloudtrail": True})
        tpl = template.to_json()
        trail_buckets = [
            res for lid, res in tpl["Resources"].items()
            if res["Type"] == "AWS::S3::Bucket"
        ]
        assert len(trail_buckets) >= 1, "No S3 bucket found for CloudTrail"
        bucket = trail_buckets[0]
        enc_config = bucket["Properties"].get("BucketEncryption", {})
        rules = enc_config.get("ServerSideEncryptionConfiguration", [])
        assert len(rules) > 0, "CloudTrail bucket missing encryption configuration"

    def test_cloudtrail_bucket_blocks_public_access(self):
        """CloudTrail S3 bucket must have all four Block Public Access flags set.

        Verifies the PCSR Holmes finding (Rule 9, S3 Security Fundamentals)
        that the bucket blocks public ACLs, public policies, and ignores
        any that slip through. All four flags are required - a missing
        flag here means the CloudTrail audit log can leak.
        """
        template = _build_security_template({"enable_cloudtrail": True})
        tpl = template.to_json()
        trail_buckets = [
            res for lid, res in tpl["Resources"].items()
            if res["Type"] == "AWS::S3::Bucket"
        ]
        assert len(trail_buckets) >= 1, "No S3 bucket found for CloudTrail"
        props = trail_buckets[0]["Properties"]
        pab = props.get("PublicAccessBlockConfiguration", {})
        for key in (
            "BlockPublicAcls",
            "BlockPublicPolicy",
            "IgnorePublicAcls",
            "RestrictPublicBuckets",
        ):
            assert pab.get(key) is True, (
                f"CloudTrail bucket must set {key}=true; got {pab}"
            )

    def test_cloudtrail_bucket_enforces_ssl(self):
        """CloudTrail S3 bucket policy must deny non-TLS requests.

        ``enforce_ssl=True`` on the CDK Bucket emits a bucket policy
        statement with ``Condition: {Bool: {aws:SecureTransport: false}}``
        and ``Effect: Deny``. Without this, clients can read or write
        the bucket over plain HTTP.
        """
        template = _build_security_template({"enable_cloudtrail": True})
        tpl = template.to_json()
        bucket_policies = [
            res for lid, res in tpl["Resources"].items()
            if res["Type"] == "AWS::S3::BucketPolicy"
        ]
        assert len(bucket_policies) >= 1, "No S3 bucket policy attached to CloudTrail bucket"
        found_tls_deny = False
        for bp in bucket_policies:
            stmts = bp["Properties"].get("PolicyDocument", {}).get("Statement", [])
            for stmt in stmts:
                if stmt.get("Effect") != "Deny":
                    continue
                cond = stmt.get("Condition", {})
                secure = cond.get("Bool", {}).get("aws:SecureTransport")
                if secure in ("false", False):
                    found_tls_deny = True
                    break
            if found_tls_deny:
                break
        assert found_tls_deny, (
            "CloudTrail bucket policy must Deny any request where "
            "aws:SecureTransport is false (enforce_ssl=True on the "
            "underlying Bucket)."
        )

    def test_cloudtrail_bucket_versioned(self):
        """CloudTrail S3 bucket must have versioning enabled.

        Versioning protects the audit log from accidental or malicious
        overwrite. Without it, a compromised caller with S3 PutObject
        permission on an existing log key can rewrite history in-place.
        """
        template = _build_security_template({"enable_cloudtrail": True})
        tpl = template.to_json()
        trail_buckets = [
            res for lid, res in tpl["Resources"].items()
            if res["Type"] == "AWS::S3::Bucket"
        ]
        assert len(trail_buckets) >= 1, "No S3 bucket found for CloudTrail"
        versioning = trail_buckets[0]["Properties"].get("VersioningConfiguration", {})
        assert versioning.get("Status") == "Enabled", (
            f"CloudTrail bucket must have VersioningConfiguration.Status=Enabled; "
            f"got {versioning}"
        )

    def test_no_s3_bucket_when_cloudtrail_disabled(self):
        """No S3 bucket created when CloudTrail is disabled."""
        template = _build_security_template({"enable_cloudtrail": False})
        template.resource_count_is("AWS::S3::Bucket", 0)

    def test_cloudtrail_created_when_enabled_string_true(self):
        """CLI override: -c enable_cloudtrail=true (string) creates trail."""
        template = _build_security_template({"enable_cloudtrail": "true"})
        template.resource_count_is("AWS::CloudTrail::Trail", 1)

    def test_no_cloudtrail_when_disabled_string_false(self):
        """CLI override: -c enable_cloudtrail=false (string) creates no trail."""
        template = _build_security_template({"enable_cloudtrail": "false"})
        template.resource_count_is("AWS::CloudTrail::Trail", 0)


# ---------------------------------------------------------------------------
# Helpers for KMS key policy inspection
# ---------------------------------------------------------------------------

def _extract_kms_key_policy(tpl: dict) -> dict:
    """Extract the KMS key policy document from the synthesized template."""
    for lid, res in tpl["Resources"].items():
        if res["Type"] == "AWS::KMS::Key":
            policy = res["Properties"].get("KeyPolicy", {})
            return policy
    raise AssertionError("No AWS::KMS::Key found in template")


def _flatten_principals(statement: dict) -> list[str]:
    """Extract all principal strings from a policy statement."""
    principal = statement.get("Principal", {})
    if isinstance(principal, str):
        return [principal]
    results = []
    for key in ("AWS", "Service", "Federated"):
        val = principal.get(key, [])
        if isinstance(val, str):
            results.append(val)
        elif isinstance(val, list):
            results.extend(val)
        elif isinstance(val, dict):
            # Handle Fn::Join or other intrinsics — stringify
            results.append(json.dumps(val))
    return results


def _policy_has_service_principal(policy: dict, service: str) -> bool:
    """Check if any statement in the policy grants access to the given service principal."""
    for stmt in policy.get("Statement", []):
        principals = _flatten_principals(stmt)
        if any(service in p for p in principals):
            return True
    return False
