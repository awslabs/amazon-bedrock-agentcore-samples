# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for Gateway stack (stacks/gateway_stack.py).

Feature: 15-cdk-native-gateway-target

These deterministic template-level tests pin the synthesized CloudFormation
template for ``OpenCodeGateway`` after the MCP ``GatewayTarget`` and
``PolicyEngineConfiguration`` migrate from a post-deploy boto3 script
into CDK.

The ``_build_stacks`` helper here is a deterministic analogue of the
Hypothesis-driven harness in
``tests/property/test_gateway_stack_synthesis.py``. Fixed stub inputs
(region, account, runtime id, policy engine ARN) make these tests safe
to run on every unit-test invocation without relying on Hypothesis's
example-generation layer.

Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 3.4, 10.7
"""

from __future__ import annotations

import json
from pathlib import Path

import aws_cdk as cdk
import pytest
from aws_cdk import assertions
from aws_cdk import aws_bedrockagentcore as bedrockagentcore
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_kms as kms
from constructs import Construct

from stacks.gateway_stack import GatewayStack

# ---------------------------------------------------------------------------
# Fixed stub inputs — keep these deterministic so every assertion is
# reproducible without Hypothesis.
# ---------------------------------------------------------------------------

_REGION = "us-east-1"
_ACCOUNT = "123456789012"
_RUNTIME_ID = "ABCDEFGHIJ"
_POLICY_ENGINE_ARN = (
    f"arn:aws:bedrock-agentcore:{_REGION}:{_ACCOUNT}:policy-engine/ENGINE00001"
)

# ---------------------------------------------------------------------------
# Context loading — match what cdk.json exposes at synth time.
# ---------------------------------------------------------------------------

_CDK_JSON_PATH = Path(__file__).resolve().parents[2] / "cdk.json"


def _load_cdk_context() -> dict:
    with open(_CDK_JSON_PATH) as f:
        return json.load(f)["context"]


# ---------------------------------------------------------------------------
# Stub stacks — minimal analogues of AgentCoreStack and PolicyStack that
# expose just the attributes ``GatewayStack`` reads at synth time.
# ---------------------------------------------------------------------------


class _StubAgentCoreStack(cdk.Stack):
    """Minimal stack exposing a ``CfnRuntime`` usable as ``opencode_runtime``."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        runtime_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.runtime = bedrockagentcore.CfnRuntime(
            self,
            "StubRuntime",
            agent_runtime_name=f"stub_runtime_{runtime_id.lower()}",
            protocol_configuration="MCP",
            agent_runtime_artifact=bedrockagentcore.CfnRuntime.AgentRuntimeArtifactProperty(
                container_configuration=bedrockagentcore.CfnRuntime.ContainerConfigurationProperty(
                    container_uri=(
                        f"123456789012.dkr.ecr.us-east-1.amazonaws.com/"
                        f"opencode:{runtime_id.lower()}"
                    ),
                ),
            ),
            role_arn="arn:aws:iam::123456789012:role/stub-execution-role",
            network_configuration=bedrockagentcore.CfnRuntime.NetworkConfigurationProperty(
                network_mode="PUBLIC",
            ),
        )


class _StubPolicyStack(cdk.Stack):
    """Minimal stack exposing ``policy_engine.attr_policy_engine_arn``."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.policy_engine = bedrockagentcore.CfnPolicyEngine(
            self,
            "StubPolicyEngine",
            name="stub_policy_engine",
            description="Stub policy engine for synthesis-level unit tests",
        )


# ---------------------------------------------------------------------------
# Deterministic stack factory
# ---------------------------------------------------------------------------


def _build_stacks(
    *,
    region: str = _REGION,
    account: str = _ACCOUNT,
    runtime_id: str = _RUNTIME_ID,
    policy_engine_arn: str | None = _POLICY_ENGINE_ARN,
) -> tuple[cdk.App, GatewayStack]:
    """Build a fresh ``cdk.App`` with stub AgentCore + Policy + real Gateway.

    When ``policy_engine_arn`` is ``None``, the stub PolicyEngine's
    ``attr_policy_engine_arn`` attribute is threaded through instead so the
    synthesized template contains a cross-stack reference shape. Pass a
    literal string (the default) to pin the flat resource shape.
    """
    ctx = _load_cdk_context()
    app = cdk.App(context=ctx)
    env = cdk.Environment(account=account, region=region)

    agentcore_stack = _StubAgentCoreStack(
        app,
        "StubAgentCore",
        runtime_id=runtime_id,
        env=env,
    )

    policy_stack = _StubPolicyStack(app, "StubPolicy", env=env)

    # Helper stack for the Cognito user pool reference — keeps the Gateway
    # stack's ``cognito_user_pool`` kwarg satisfied without standing up a
    # full SecurityStack.
    helper_stack = cdk.Stack(app, "HelperStack", env=env)
    user_pool = cognito.UserPool.from_user_pool_id(
        helper_stack,
        "StubUserPool",
        f"{region}_abcdefghi",
    )

    pe_arn = (
        policy_engine_arn
        if policy_engine_arn is not None
        else policy_stack.policy_engine.attr_policy_engine_arn
    )

    # Stub KMS key for CMK encryption
    cmk_stack = cdk.Stack(app, "StubCmkStack", env=env)
    stub_cmk = kms.Key(cmk_stack, "StubCmk")

    gateway_stack = GatewayStack(
        app,
        "OpenCodeGateway",
        cognito_user_pool=user_pool,
        cognito_client_id="abcdefghijklmnopqrstuvwxyz",
        opencode_runtime=agentcore_stack.runtime,
        policy_engine_arn=pe_arn,
        cmk=stub_cmk,
        env=env,
    )
    gateway_stack.add_dependency(agentcore_stack)
    gateway_stack.add_dependency(policy_stack)

    return app, gateway_stack


def _get_single_gateway_target(template: assertions.Template) -> dict:
    tpl = template.to_json()
    targets = {
        lid: res
        for lid, res in tpl.get("Resources", {}).items()
        if res.get("Type") == "AWS::BedrockAgentCore::GatewayTarget"
    }
    assert len(targets) == 1, (
        f"Expected exactly 1 GatewayTarget resource, found {len(targets)}: "
        f"{sorted(targets)!r}"
    )
    return next(iter(targets.values()))


def _get_single_gateway(template: assertions.Template) -> dict:
    tpl = template.to_json()
    gateways = {
        lid: res
        for lid, res in tpl.get("Resources", {}).items()
        if res.get("Type") == "AWS::BedrockAgentCore::Gateway"
    }
    assert len(gateways) == 1, (
        f"Expected exactly 1 Gateway resource, found {len(gateways)}: "
        f"{sorted(gateways)!r}"
    )
    return next(iter(gateways.values()))


# ---------------------------------------------------------------------------
# Task 2.1 — Unit test: template contains MCP target with GATEWAY_IAM_ROLE
# ---------------------------------------------------------------------------


class TestMcpGatewayTarget:
    """Verify the synthesized template contains the CDK-native MCP target."""

    def test_template_contains_one_mcp_gateway_target(self) -> None:
        _app, gateway_stack = _build_stacks()
        template = assertions.Template.from_stack(gateway_stack)
        template.resource_count_is("AWS::BedrockAgentCore::GatewayTarget", 1)

    def test_target_credential_provider_is_gateway_iam_role(self) -> None:
        _app, gateway_stack = _build_stacks()
        template = assertions.Template.from_stack(gateway_stack)
        target = _get_single_gateway_target(template)
        props = target.get("Properties", {})

        cred_configs = props.get("CredentialProviderConfigurations", [])
        assert len(cred_configs) >= 1
        first = cred_configs[0]
        assert first.get("CredentialProviderType") == "GATEWAY_IAM_ROLE"

    def test_target_mcp_endpoint_is_non_empty(self) -> None:
        _app, gateway_stack = _build_stacks()
        template = assertions.Template.from_stack(gateway_stack)
        target = _get_single_gateway_target(template)
        props = target.get("Properties", {})
        endpoint = (
            props.get("TargetConfiguration", {})
            .get("Mcp", {})
            .get("McpServer", {})
            .get("Endpoint")
        )
        assert endpoint not in (None, "", {})

    def test_target_name_is_opencode(self) -> None:
        _app, gateway_stack = _build_stacks()
        template = assertions.Template.from_stack(gateway_stack)
        target = _get_single_gateway_target(template)
        assert target.get("Properties", {}).get("Name") == "opencode"

    def test_target_description_matches_literal(self) -> None:
        _app, gateway_stack = _build_stacks()
        template = assertions.Template.from_stack(gateway_stack)
        target = _get_single_gateway_target(template)
        description = target.get("Properties", {}).get("Description")

        expected = "OpenCode unified runtime - GATEWAY_IAM_ROLE SigV4 auth"
        assert description == expected
        assert "\u2014" not in (description or "")


# ---------------------------------------------------------------------------
# Task 2.2 — Unit test: Gateway carries PolicyEngineConfiguration
# ---------------------------------------------------------------------------


class TestPolicyEngineConfiguration:
    """Verify the synthesized Gateway carries the CDK-native Cedar link."""

    def test_template_contains_exactly_one_gateway(self) -> None:
        _app, gateway_stack = _build_stacks()
        template = assertions.Template.from_stack(gateway_stack)
        template.resource_count_is("AWS::BedrockAgentCore::Gateway", 1)

    def test_policy_engine_configuration_mode_is_log_only(self) -> None:
        _app, gateway_stack = _build_stacks()
        template = assertions.Template.from_stack(gateway_stack)
        gateway = _get_single_gateway(template)
        pe_config = gateway.get("Properties", {}).get("PolicyEngineConfiguration")
        assert pe_config is not None
        assert pe_config.get("Mode") == "LOG_ONLY"

    def test_policy_engine_configuration_arn_matches_input(self) -> None:
        _app, gateway_stack = _build_stacks()
        template = assertions.Template.from_stack(gateway_stack)
        gateway = _get_single_gateway(template)
        pe_config = gateway.get("Properties", {}).get("PolicyEngineConfiguration")
        assert pe_config is not None
        assert pe_config.get("Arn") == _POLICY_ENGINE_ARN


# ---------------------------------------------------------------------------
# Task 2.3 — Unit test: missing policy_engine_arn raises TypeError
# ---------------------------------------------------------------------------


class TestMissingPolicyEngineArnRaisesTypeError:
    """Verify GatewayStack fails fast when policy_engine_arn is omitted."""

    def test_gateway_stack_rejects_missing_policy_engine_arn(self) -> None:
        ctx = _load_cdk_context()
        app = cdk.App(context=ctx)
        env = cdk.Environment(account=_ACCOUNT, region=_REGION)

        agentcore_stack = _StubAgentCoreStack(
            app, "StubAgentCore", runtime_id=_RUNTIME_ID, env=env,
        )
        helper_stack = cdk.Stack(app, "HelperStack", env=env)
        user_pool = cognito.UserPool.from_user_pool_id(
            helper_stack, "StubUserPool", f"{_REGION}_abcdefghi",
        )
        cmk_stack = cdk.Stack(app, "StubCmkStack", env=env)
        stub_cmk = kms.Key(cmk_stack, "StubCmk")

        with pytest.raises(TypeError):
            GatewayStack(
                app,
                "OpenCodeGateway",
                cognito_user_pool=user_pool,
                cognito_client_id="abcdefghijklmnopqrstuvwxyz",
                opencode_runtime=agentcore_stack.runtime,
                cmk=stub_cmk,
                # policy_engine_arn intentionally omitted
                env=env,
            )


# ---------------------------------------------------------------------------
# H7 — All log groups encrypted with CMK
# ---------------------------------------------------------------------------


class TestLogGroupsEncryptedWithCmk:
    """Verify every AWS::Logs::LogGroup in GatewayStack has a KmsKeyId."""

    def test_all_log_groups_have_kms_key_id(self) -> None:
        _app, gateway_stack = _build_stacks()
        template = assertions.Template.from_stack(gateway_stack)
        tpl = template.to_json()

        log_groups = {
            lid: res
            for lid, res in tpl.get("Resources", {}).items()
            if res.get("Type") == "AWS::Logs::LogGroup"
        }
        assert len(log_groups) > 0, "Expected at least one LogGroup resource"

        for lid, res in log_groups.items():
            props = res.get("Properties", {})
            assert "KmsKeyId" in props, (
                f"LogGroup {lid} is missing KmsKeyId property"
            )
