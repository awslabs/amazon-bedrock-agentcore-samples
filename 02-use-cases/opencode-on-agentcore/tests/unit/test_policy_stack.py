# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for Policy stack (stacks/policy_stack.py).

Validates: Requirement 9.1, 9.3
- CfnPolicyEngine resource exists with correct name
- CfnOutputs for PolicyEngineId and PolicyEngineArn exist

Note: Cedar policies are created post-deploy via scripts/create-policies.py
because the CfnPolicy CloudFormation resource handler has stabilization issues.

After spec 15 (cdk-native-gateway-target), PolicyStack no longer accepts
``gateway_id`` / ``gateway_arn`` constructor parameters and no longer emits
``GatewayId`` / ``GatewayArn`` outputs. Those outputs moved to
``GatewayStack`` (see ``tests/unit/test_gateway_stack.py``) because the
Gateway now owns the PolicyEngine link via ``PolicyEngineConfiguration``.
"""

import aws_cdk as cdk
from aws_cdk import assertions
import pytest

from stacks.policy_stack import PolicyStack


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_policy_template() -> assertions.Template:
    app = cdk.App()
    env = cdk.Environment(account="123456789012", region="us-east-1")
    stack = PolicyStack(
        app,
        "TestPolicy",
        env=env,
    )
    return assertions.Template.from_stack(stack)


# ---------------------------------------------------------------------------
# CfnPolicyEngine tests (Requirement 9.1)
# ---------------------------------------------------------------------------


class TestCfnPolicyEngine:
    """Verify CfnPolicyEngine resource is created correctly."""

    def test_policy_engine_exists(self):
        """Stack should contain exactly one CfnPolicyEngine resource."""
        template = _build_policy_template()
        template.resource_count_is("AWS::BedrockAgentCore::PolicyEngine", 1)

    def test_policy_engine_name(self):
        """Policy engine should be named 'opencode_policy_engine'."""
        template = _build_policy_template()
        template.has_resource_properties(
            "AWS::BedrockAgentCore::PolicyEngine",
            {"Name": "opencode_policy_engine"},
        )

    def test_policy_engine_has_description(self):
        """Policy engine should have a description."""
        template = _build_policy_template()
        template.has_resource_properties(
            "AWS::BedrockAgentCore::PolicyEngine",
            {
                "Description": assertions.Match.string_like_regexp(
                    ".*Cedar.*policy.*"
                ),
            },
        )


# ---------------------------------------------------------------------------
# CfnOutput tests (Requirement 9.3)
# ---------------------------------------------------------------------------


class TestPolicyOutputs:
    """Verify CfnOutputs for policy engine ID and ARN.

    After spec 15 (cdk-native-gateway-target), PolicyStack no longer
    emits ``GatewayId`` / ``GatewayArn`` outputs; those moved to
    ``GatewayStack``. Coverage for the relocated outputs lives in
    ``tests/unit/test_gateway_stack.py``.
    """

    def test_policy_engine_id_output(self):
        """Stack should output the PolicyEngineId."""
        template = _build_policy_template()
        tpl = template.to_json()
        outputs = tpl.get("Outputs", {})
        matching = [k for k in outputs if "PolicyEngineId" in k]
        assert matching, "PolicyEngineId output not found"

    def test_policy_engine_arn_output(self):
        """Stack should output the PolicyEngineArn."""
        template = _build_policy_template()
        tpl = template.to_json()
        outputs = tpl.get("Outputs", {})
        matching = [k for k in outputs if "PolicyEngineArn" in k]
        assert matching, "PolicyEngineArn output not found"

    def test_no_gateway_id_output(self):
        """Stack MUST NOT output GatewayId (moved to GatewayStack per spec 15)."""
        template = _build_policy_template()
        tpl = template.to_json()
        outputs = tpl.get("Outputs", {})
        matching = [k for k in outputs if "GatewayId" in k]
        assert not matching, (
            f"PolicyStack should not emit GatewayId output after spec 15; "
            f"found: {matching}"
        )

    def test_no_gateway_arn_output(self):
        """Stack MUST NOT output GatewayArn (moved to GatewayStack per spec 15)."""
        template = _build_policy_template()
        tpl = template.to_json()
        outputs = tpl.get("Outputs", {})
        matching = [k for k in outputs if "GatewayArn" in k]
        assert not matching, (
            f"PolicyStack should not emit GatewayArn output after spec 15; "
            f"found: {matching}"
        )
