# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Property tests: GatewayStack CloudFormation synthesis.

Feature: 15-cdk-native-gateway-target

These Hypothesis-driven properties pin the synthesized CloudFormation
template for ``OpenCodeGateway`` after the MCP ``GatewayTarget`` and
``PolicyEngineConfiguration`` migrate from a post-deploy boto3 script
into CDK.

The shared ``_build_stacks`` helper builds a fresh ``cdk.App`` with a
stub AgentCore stack (exposing ``runtime`` as a ``CfnRuntime``) and a
stub PolicyStack (exposing ``policy_engine.attr_policy_engine_arn``),
then wires the ARN into ``GatewayStack`` so each property draw
synthesizes end-to-end.
"""

from __future__ import annotations

import json
from pathlib import Path

import aws_cdk as cdk
from aws_cdk import assertions
from aws_cdk import aws_bedrockagentcore as bedrockagentcore
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_kms as kms
from constructs import Construct
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from stacks.gateway_stack import GatewayStack

# ---------------------------------------------------------------------------
# Context loading — match what cdk.json exposes at synth time
# ---------------------------------------------------------------------------

_CDK_JSON_PATH = Path(__file__).resolve().parents[2] / "cdk.json"


def _load_cdk_context() -> dict:
    with open(_CDK_JSON_PATH) as f:
        return json.load(f)["context"]


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

_REGIONS = [
    "us-east-1",
    "us-east-1",
    "eu-west-1",
    "eu-central-1",
    "ap-northeast-1",
]

region_strategy = st.sampled_from(_REGIONS)
account_id_strategy = st.from_regex(r"[0-9]{12}", fullmatch=True)
runtime_id_strategy = st.from_regex(r"[A-Z0-9]{10}", fullmatch=True)

policy_engine_arn_strategy = st.builds(
    lambda region, account, engine_id: (
        f"arn:aws:bedrock-agentcore:{region}:{account}:policy-engine/{engine_id}"
    ),
    region=region_strategy,
    account=account_id_strategy,
    engine_id=st.from_regex(r"[A-Z0-9]{10}", fullmatch=True),
)


# ---------------------------------------------------------------------------
# Stub stacks
# ---------------------------------------------------------------------------


class _StubAgentCoreStack(cdk.Stack):
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
            description="Stub policy engine for synthesis-level property tests",
        )


# ---------------------------------------------------------------------------
# Stack factory
# ---------------------------------------------------------------------------


def _build_stacks(
    *,
    region: str,
    account: str,
    runtime_id: str,
    policy_engine_arn: str | None = None,
) -> tuple[cdk.App, GatewayStack, _StubPolicyStack, _StubAgentCoreStack]:
    ctx = _load_cdk_context()
    app = cdk.App(context=ctx)
    env = cdk.Environment(account=account, region=region)

    agentcore_stack = _StubAgentCoreStack(
        app, "StubAgentCore", runtime_id=runtime_id, env=env,
    )
    policy_stack = _StubPolicyStack(app, "StubPolicy", env=env)

    helper_stack = cdk.Stack(app, "HelperStack", env=env)
    user_pool = cognito.UserPool.from_user_pool_id(
        helper_stack, "StubUserPool", f"{region}_abcdefghi",
    )

    pe_arn = (
        policy_engine_arn
        if policy_engine_arn is not None
        else policy_stack.policy_engine.attr_policy_engine_arn
    )

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

    return app, gateway_stack, policy_stack, agentcore_stack


# ---------------------------------------------------------------------------
# Property 1: exactly one MCP GatewayTarget with IAM credential provider
# ---------------------------------------------------------------------------


class TestMcpGatewayTargetProperties:
    """Property 1: exactly one MCP GatewayTarget with IAM credential provider."""

    @given(
        region=region_strategy,
        account=account_id_strategy,
        runtime_id=runtime_id_strategy,
        policy_engine_arn=policy_engine_arn_strategy,
    )
    @settings(
        max_examples=25,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_exactly_one_iam_mcp_target(
        self,
        region: str,
        account: str,
        runtime_id: str,
        policy_engine_arn: str,
    ) -> None:
        _app, gateway_stack, _policy_stack, _ac = _build_stacks(
            region=region,
            account=account,
            runtime_id=runtime_id,
            policy_engine_arn=policy_engine_arn,
        )

        template = assertions.Template.from_stack(gateway_stack)
        template.resource_count_is("AWS::BedrockAgentCore::GatewayTarget", 1)

        tpl = template.to_json()
        targets = {
            lid: res
            for lid, res in tpl["Resources"].items()
            if res["Type"] == "AWS::BedrockAgentCore::GatewayTarget"
        }
        assert len(targets) == 1
        _lid, target = next(iter(targets.items()))
        props = target.get("Properties", {})

        endpoint = (
            props.get("TargetConfiguration", {})
            .get("Mcp", {})
            .get("McpServer", {})
            .get("Endpoint")
        )
        assert endpoint not in (None, "", {})

        cred_configs = props.get("CredentialProviderConfigurations", [])
        assert len(cred_configs) >= 1
        first = cred_configs[0]
        assert first.get("CredentialProviderType") == "GATEWAY_IAM_ROLE"


# ---------------------------------------------------------------------------
# Property 2: PolicyEngineConfiguration attached with LOG_ONLY
# ---------------------------------------------------------------------------


def _contains_intrinsic_reference(value: object) -> bool:
    if isinstance(value, dict):
        for key in ("Ref", "Fn::GetAtt", "Fn::ImportValue"):
            if key in value:
                return True
        return any(_contains_intrinsic_reference(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_intrinsic_reference(item) for item in value)
    return False


class TestPolicyEngineConfigurationProperties:
    """Property 2: PolicyEngineConfiguration attached with LOG_ONLY."""

    @given(
        region=region_strategy,
        account=account_id_strategy,
        runtime_id=runtime_id_strategy,
    )
    @settings(
        max_examples=25,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_policy_engine_log_only_on_gateway(
        self,
        region: str,
        account: str,
        runtime_id: str,
    ) -> None:
        # Do NOT pass policy_engine_arn; use the stub policy stack's
        # attr_policy_engine_arn so the template contains a cross-stack
        # reference shape.
        _app, gateway_stack, _policy_stack, _ac = _build_stacks(
            region=region,
            account=account,
            runtime_id=runtime_id,
        )

        template = assertions.Template.from_stack(gateway_stack)
        template.resource_count_is("AWS::BedrockAgentCore::Gateway", 1)

        tpl = template.to_json()
        gateways = {
            lid: res
            for lid, res in tpl["Resources"].items()
            if res["Type"] == "AWS::BedrockAgentCore::Gateway"
        }
        assert len(gateways) == 1
        _lid, gateway = next(iter(gateways.items()))
        props = gateway.get("Properties", {})

        pe_config = props.get("PolicyEngineConfiguration")
        assert pe_config is not None
        assert pe_config.get("Mode") == "LOG_ONLY"

        arn = pe_config.get("Arn")
        assert arn not in (None, "", {}, [])
        assert _contains_intrinsic_reference(arn)


# ---------------------------------------------------------------------------
# Property 3: synthesis is idempotent for logical IDs
# ---------------------------------------------------------------------------


def _collect_logical_ids(template_json: dict, resource_type: str) -> list[str]:
    return sorted(
        lid
        for lid, res in template_json.get("Resources", {}).items()
        if res.get("Type") == resource_type
    )


class TestSynthesisIdempotenceProperties:
    """Property 3: idempotent logical IDs across successive synths."""

    @given(
        region=region_strategy,
        account=account_id_strategy,
        runtime_id=runtime_id_strategy,
        policy_engine_arn=policy_engine_arn_strategy,
    )
    @settings(
        max_examples=10,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_logical_ids_are_stable_across_synths(
        self,
        region: str,
        account: str,
        runtime_id: str,
        policy_engine_arn: str,
    ) -> None:
        _app1, gs1, ps1, _ac1 = _build_stacks(
            region=region, account=account, runtime_id=runtime_id,
            policy_engine_arn=policy_engine_arn,
        )
        gw_tpl_1 = assertions.Template.from_stack(gs1).to_json()
        pol_tpl_1 = assertions.Template.from_stack(ps1).to_json()

        _app2, gs2, ps2, _ac2 = _build_stacks(
            region=region, account=account, runtime_id=runtime_id,
            policy_engine_arn=policy_engine_arn,
        )
        gw_tpl_2 = assertions.Template.from_stack(gs2).to_json()
        pol_tpl_2 = assertions.Template.from_stack(ps2).to_json()

        assert _collect_logical_ids(gw_tpl_1, "AWS::BedrockAgentCore::Gateway") == \
               _collect_logical_ids(gw_tpl_2, "AWS::BedrockAgentCore::Gateway")
        assert _collect_logical_ids(gw_tpl_1, "AWS::BedrockAgentCore::GatewayTarget") == \
               _collect_logical_ids(gw_tpl_2, "AWS::BedrockAgentCore::GatewayTarget")
        assert _collect_logical_ids(pol_tpl_1, "AWS::BedrockAgentCore::PolicyEngine") == \
               _collect_logical_ids(pol_tpl_2, "AWS::BedrockAgentCore::PolicyEngine")


# ---------------------------------------------------------------------------
# Property 4: MCP endpoint URL shape
# ---------------------------------------------------------------------------


_ENDPOINT_REGEX = (
    r"https://bedrock-agentcore\.[a-z0-9-]+\.amazonaws\.com/runtimes/"
    r"arn%3Aaws%3Abedrock-agentcore%3A[a-z0-9-]+%3A[0-9]+"
    r"%3Aruntime%2F[A-Z0-9_-]+/invocations"
)


def _resolve_endpoint(
    value: object,
    *,
    region: str,
    account: str,
    runtime_id: str,
) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if "Ref" in value:
            ref = value["Ref"]
            if ref == "AWS::Region":
                return region
            if ref == "AWS::AccountId":
                return account
            return f"<Ref:{ref}>"
        if "Fn::ImportValue" in value:
            export_name = value["Fn::ImportValue"]
            if isinstance(export_name, str) and "AgentRuntimeId" in export_name:
                return runtime_id
            return f"<ImportValue:{export_name!r}>"
        if "Fn::GetAtt" in value:
            parts = value["Fn::GetAtt"]
            if isinstance(parts, list) and len(parts) == 2 and parts[1] == "AgentRuntimeId":
                return runtime_id
            return f"<GetAtt:{parts!r}>"
        if "Fn::Join" in value:
            sep, items = value["Fn::Join"]
            return sep.join(
                _resolve_endpoint(item, region=region, account=account, runtime_id=runtime_id)
                for item in items
            )
        return f"<Intrinsic:{sorted(value.keys())!r}>"
    return f"<Unsupported:{type(value).__name__}>"


class TestMcpEndpointUrlShapeProperties:
    """Property 4: MCP endpoint URL is well-formed after token resolution."""

    @given(
        region=region_strategy,
        account=account_id_strategy,
        runtime_id=runtime_id_strategy,
        policy_engine_arn=policy_engine_arn_strategy,
    )
    @settings(
        max_examples=25,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_endpoint_url_shape(
        self,
        region: str,
        account: str,
        runtime_id: str,
        policy_engine_arn: str,
    ) -> None:
        import re

        _app, gateway_stack, _ps, _ac = _build_stacks(
            region=region,
            account=account,
            runtime_id=runtime_id,
            policy_engine_arn=policy_engine_arn,
        )

        template = assertions.Template.from_stack(gateway_stack)
        tpl = template.to_json()

        targets = {
            lid: res
            for lid, res in tpl["Resources"].items()
            if res["Type"] == "AWS::BedrockAgentCore::GatewayTarget"
        }
        assert len(targets) == 1
        _lid, target = next(iter(targets.items()))

        endpoint_value = (
            target.get("Properties", {})
            .get("TargetConfiguration", {})
            .get("Mcp", {})
            .get("McpServer", {})
            .get("Endpoint")
        )
        assert endpoint_value is not None

        resolved = _resolve_endpoint(
            endpoint_value, region=region, account=account, runtime_id=runtime_id,
        )
        assert re.fullmatch(_ENDPOINT_REGEX, resolved), (
            f"Resolved endpoint did not match regex.\n"
            f"  regex: {_ENDPOINT_REGEX}\n"
            f"  resolved: {resolved!r}\n"
            f"  raw: {endpoint_value!r}"
        )
