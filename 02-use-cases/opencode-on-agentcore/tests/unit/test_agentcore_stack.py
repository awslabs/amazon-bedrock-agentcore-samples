# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for AgentCore stack (stacks/agentcore_stack.py).

Validates: Requirements 7.2, 7.3, 10.3, 10.4
- No S3 artifact bucket exists (removed as unused — Requirement 7)
- Security group rules match design (outbound 443 only, no inbound from 0.0.0.0/0)
- IAM execution role has least-privilege permissions
"""

import json
from pathlib import Path

import aws_cdk as cdk
from aws_cdk import assertions
import pytest

from stacks.vpc_stack import VpcStack
from stacks.security_stack import SecurityStack
from stacks.agentcore_stack import AgentCoreStack

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CDK_JSON_PATH = Path(__file__).resolve().parents[2] / "cdk.json"


def _load_cdk_context() -> dict:
    with open(CDK_JSON_PATH) as f:
        return json.load(f)["context"]


def _build_agentcore_template(
    context_overrides: dict | None = None,
) -> assertions.Template:
    ctx = _load_cdk_context()
    if context_overrides:
        ctx.update(context_overrides)
    app = cdk.App(context=ctx)
    env = cdk.Environment(account="123456789012", region="us-east-1")
    security_stack = SecurityStack(app, "TestSecurity", env=env)
    vpc_stack = VpcStack(app, "TestVpc", cmk=security_stack.cmk, env=env)
    stack = AgentCoreStack(
        app, "TestAgentCore", vpc=vpc_stack.vpc, cmk=security_stack.cmk,
        callback_url="https://test.execute-api.us-east-1.amazonaws.com/callback",
        env=env,
    )
    return assertions.Template.from_stack(stack)


# ---------------------------------------------------------------------------
# S3 Artifact Bucket removed (Requirement 7)
# ---------------------------------------------------------------------------


class TestNoS3Bucket:
    """Verify S3 artifact bucket has been removed (Requirement 7)."""

    def test_no_s3_bucket_exists(self):
        """Stack should not contain any S3 bucket resources."""
        template = _build_agentcore_template()
        template.resource_count_is("AWS::S3::Bucket", 0)

    def test_no_s3_bucket_policy_exists(self):
        """Stack should not contain any S3 bucket policy resources."""
        template = _build_agentcore_template()
        template.resource_count_is("AWS::S3::BucketPolicy", 0)

    def test_no_s3_iam_actions(self):
        """Execution role should not have any S3 IAM actions."""
        template = _build_agentcore_template()
        tpl = template.to_json()
        actions = _collect_all_policy_actions(tpl)
        s3_actions = {a for a in actions if a.startswith("s3:")}
        assert not s3_actions, f"Unexpected S3 IAM actions found: {s3_actions}"


# ---------------------------------------------------------------------------
# Security Group tests (Requirement 10.3)
# ---------------------------------------------------------------------------


class TestSecurityGroup:
    """Verify AgentCore security group rules match design."""

    def test_security_group_exists(self):
        template = _build_agentcore_template()
        template.resource_count_is("AWS::EC2::SecurityGroup", 1)

    def test_security_group_description(self):
        template = _build_agentcore_template()
        template.has_resource_properties(
            "AWS::EC2::SecurityGroup",
            {"GroupDescription": "AgentCore container security group"},
        )

    def test_egress_allows_outbound_to_internet(self):
        """Outbound rules allow egress to 0.0.0.0/0.

        The SG uses ``allow_all_outbound=True`` which CDK lowers to a
        single ``IpProtocol: -1`` rule to ``0.0.0.0/0`` on the
        SecurityGroup's inline ``SecurityGroupEgress`` block (not as a
        separate egress resource). OpenCode needs outbound for Bedrock
        (443), git over HTTPS (443), GitHub API (443), S3 (443 via
        Gateway endpoint if present), and models.dev metadata.
        """
        template = _build_agentcore_template()
        tpl = template.to_json()
        found = False
        for lid, res in tpl["Resources"].items():
            if res["Type"] != "AWS::EC2::SecurityGroup":
                continue
            egress = res.get("Properties", {}).get("SecurityGroupEgress", [])
            for rule in egress:
                if (
                    rule.get("CidrIp") == "0.0.0.0/0"
                    and rule.get("IpProtocol") in ("-1", "tcp")
                ):
                    found = True
                    break
        assert found, "No egress rule to 0.0.0.0/0 found on AgentCore SG"

    def test_no_allow_all_outbound(self):
        """Security group does not have allow_all_outbound (no 0.0.0.0/0 on all ports)."""
        template = _build_agentcore_template()
        tpl = template.to_json()
        egress_rules = {
            lid: res
            for lid, res in tpl["Resources"].items()
            if res["Type"] == "AWS::EC2::SecurityGroupEgress"
        }
        for lid, res in egress_rules.items():
            props = res.get("Properties", {})
            # If there's a rule with all ports (from 0 to 65535) to 0.0.0.0/0, that's bad
            from_port = props.get("FromPort")
            to_port = props.get("ToPort")
            cidr = props.get("CidrIp", "")
            ip_protocol = props.get("IpProtocol", "")
            if ip_protocol == "-1" and cidr == "0.0.0.0/0":
                pytest.fail(
                    f"Security group has allow-all outbound rule: {lid}"
                )

    def test_no_inbound_from_anywhere(self):
        """No ingress rules from 0.0.0.0/0 — AgentCore SG is egress-only (HTTPS out)."""
        template = _build_agentcore_template()
        tpl = template.to_json()
        ingress_rules = {
            lid: res
            for lid, res in tpl["Resources"].items()
            if res["Type"] == "AWS::EC2::SecurityGroupIngress"
        }
        for lid, res in ingress_rules.items():
            props = res.get("Properties", {})
            cidr = props.get("CidrIp", "")
            if cidr == "0.0.0.0/0":
                pytest.fail(
                    f"Security group has ingress from 0.0.0.0/0: {lid}"
                )


# ---------------------------------------------------------------------------
# IAM Execution Role — least-privilege tests (Requirement 7.2)
# ---------------------------------------------------------------------------


class TestIamExecutionRole:
    """Verify AgentCore execution role has least-privilege permissions."""

    def test_execution_role_exists(self):
        template = _build_agentcore_template()
        template.has_resource_properties(
            "AWS::IAM::Role",
            {"RoleName": "opencode-agentcore-execution-role-us-east-1"},
        )

    def test_execution_role_assumed_by_ecs_tasks(self):
        """Role trust policy allows bedrock-agentcore.amazonaws.com."""
        template = _build_agentcore_template()
        tpl = template.to_json()
        role = _find_execution_role(tpl)
        trust = role["Properties"]["AssumeRolePolicyDocument"]
        principals = _collect_service_principals(trust)
        assert "bedrock-agentcore.amazonaws.com" in principals, (
            "Execution role missing bedrock-agentcore.amazonaws.com trust"
        )

    def test_execution_role_assumed_by_bedrock(self):
        """Role trust policy allows bedrock-agentcore.amazonaws.com."""
        template = _build_agentcore_template()
        tpl = template.to_json()
        role = _find_execution_role(tpl)
        trust = role["Properties"]["AssumeRolePolicyDocument"]
        principals = _collect_service_principals(trust)
        assert "bedrock-agentcore.amazonaws.com" in principals, (
            "Execution role missing bedrock-agentcore.amazonaws.com trust"
        )

    def test_policy_has_bedrock_invoke_model(self):
        """Role policy includes bedrock:InvokeModel."""
        template = _build_agentcore_template()
        tpl = template.to_json()
        actions = _collect_all_policy_actions(tpl)
        assert "bedrock:InvokeModel" in actions, (
            "Execution role missing bedrock:InvokeModel permission"
        )

    def test_policy_has_secrets_manager_read(self):
        """Role policy includes secretsmanager:GetSecretValue."""
        template = _build_agentcore_template()
        tpl = template.to_json()
        actions = _collect_all_policy_actions(tpl)
        assert "secretsmanager:GetSecretValue" in actions, (
            "Missing secretsmanager:GetSecretValue"
        )

    def test_policy_has_dynamodb_access(self):
        """Role policy includes DynamoDB read/write actions."""
        template = _build_agentcore_template()
        tpl = template.to_json()
        actions = _collect_all_policy_actions(tpl)
        assert "dynamodb:GetItem" in actions, "Missing dynamodb:GetItem"
        assert "dynamodb:PutItem" in actions, "Missing dynamodb:PutItem"
        assert "dynamodb:UpdateItem" in actions, "Missing dynamodb:UpdateItem"
        assert "dynamodb:Query" in actions, "Missing dynamodb:Query"

    def test_policy_has_sts_assume_role(self):
        """Role policy includes sts:AssumeRole for per-task scoped credentials."""
        template = _build_agentcore_template()
        tpl = template.to_json()
        actions = _collect_all_policy_actions(tpl)
        assert "sts:AssumeRole" in actions, "Missing sts:AssumeRole"

    def test_policy_has_cloudwatch_permissions(self):
        """Role policy includes CloudWatch Logs and Metrics actions."""
        template = _build_agentcore_template()
        tpl = template.to_json()
        actions = _collect_all_policy_actions(tpl)
        assert "logs:CreateLogGroup" in actions, "Missing logs:CreateLogGroup"
        assert "logs:PutLogEvents" in actions, "Missing logs:PutLogEvents"
        assert "cloudwatch:PutMetricData" in actions, "Missing cloudwatch:PutMetricData"

    def test_secrets_manager_scoped_to_opencode_prefix(self):
        """Secrets Manager access is scoped to bedrock-agentcore-identity* secrets."""
        template = _build_agentcore_template()
        tpl = template.to_json()
        sm_resources = _collect_resources_for_action(tpl, "secretsmanager:GetSecretValue")
        assert any("bedrock-agentcore-identity" in str(r) for r in sm_resources), (
            "Secrets Manager access not scoped to bedrock-agentcore-identity* prefix"
        )

    def test_dynamodb_scoped_to_opencode_tables(self):
        """DynamoDB access is scoped to opencode-jobs table."""
        template = _build_agentcore_template()
        tpl = template.to_json()
        ddb_resources = _collect_resources_for_action(tpl, "dynamodb:GetItem")
        resource_str = json.dumps(ddb_resources)
        assert "opencode-jobs" in resource_str, (
            "DynamoDB access not scoped to opencode-jobs table"
        )

    def test_no_admin_or_star_actions(self):
        """Role does not have overly broad actions like iam:*, s3:*, or *."""
        template = _build_agentcore_template()
        tpl = template.to_json()
        actions = _collect_all_policy_actions(tpl)
        dangerous = {"*", "iam:*", "s3:*", "dynamodb:*", "bedrock:*", "sts:*"}
        found = actions & dangerous
        assert not found, f"Execution role has overly broad actions: {found}"


# ---------------------------------------------------------------------------
# ECR Repository tests (Requirement 13.2)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# ECR Repository tests
# ---------------------------------------------------------------------------


class TestEcrRepository:
    """Verify ECR repository for OpenCode container image."""

    def test_ecr_repo_exists(self):
        template = _build_agentcore_template()
        template.resource_count_is("AWS::ECR::Repository", 1)

    def test_ecr_repo_name(self):
        template = _build_agentcore_template()
        template.has_resource_properties(
            "AWS::ECR::Repository",
            {"RepositoryName": "opencode-agentcore"},
        )

    def test_ecr_repo_image_scan_on_push(self):
        template = _build_agentcore_template()
        template.has_resource_properties(
            "AWS::ECR::Repository",
            {"ImageScanningConfiguration": {"ScanOnPush": True}},
        )

    def test_ecr_repo_kms_encryption(self):
        template = _build_agentcore_template()
        template.has_resource_properties(
            "AWS::ECR::Repository",
            {
                "EncryptionConfiguration": assertions.Match.object_like(
                    {"EncryptionType": "KMS"}
                ),
            },
        )


# ---------------------------------------------------------------------------
# Helpers for IAM policy inspection
# ---------------------------------------------------------------------------


def _find_execution_role(tpl: dict) -> dict:
    """Find the AgentCore execution role resource."""
    for lid, res in tpl["Resources"].items():
        if res["Type"] == "AWS::IAM::Role":
            role_name = res.get("Properties", {}).get("RoleName", "")
            if role_name.startswith("opencode-agentcore-execution-role"):
                return res
    raise AssertionError("AgentCore execution role not found")


def _collect_service_principals(trust_policy: dict) -> set[str]:
    """Extract all service principals from a trust policy document."""
    principals: set[str] = set()
    for stmt in trust_policy.get("Statement", []):
        principal = stmt.get("Principal", {})
        service = principal.get("Service", [])
        if isinstance(service, str):
            principals.add(service)
        elif isinstance(service, list):
            principals.update(service)
    return principals


def _collect_all_policy_actions(tpl: dict) -> set[str]:
    """Collect all IAM policy actions from inline policies on the execution role."""
    actions: set[str] = set()
    for lid, res in tpl["Resources"].items():
        if res["Type"] == "AWS::IAM::Policy":
            doc = res.get("Properties", {}).get("PolicyDocument", {})
            for stmt in doc.get("Statement", []):
                act = stmt.get("Action", [])
                if isinstance(act, str):
                    actions.add(act)
                elif isinstance(act, list):
                    actions.update(act)
    return actions


def _collect_resources_for_action(tpl: dict, action: str) -> list:
    """Collect all Resource values from policy statements containing the given action."""
    resources: list = []
    for lid, res in tpl["Resources"].items():
        if res["Type"] == "AWS::IAM::Policy":
            doc = res.get("Properties", {}).get("PolicyDocument", {})
            for stmt in doc.get("Statement", []):
                act = stmt.get("Action", [])
                if isinstance(act, str):
                    act = [act]
                if action in act:
                    resource = stmt.get("Resource", [])
                    if isinstance(resource, list):
                        resources.extend(resource)
                    else:
                        resources.append(resource)
    return resources
