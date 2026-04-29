# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Property tests: GatewayStack inbound auth and interceptor preservation.

General regression guard for the ``OpenCodeGateway`` synthesized template.
Originally written as part of spec 14 (restore GATEWAY_IAM_ROLE) to pin
that the M2M migration did not break Cognito inbound auth or the REQUEST
interceptor; kept as a permanent invariant suite because the same
assertions catch accidental regressions from future changes to
``stacks/gateway_stack.py``.

For any valid constructor inputs the synthesized template MUST have:

- A ``CustomJWTAuthorizer`` whose discovery URL is the Cognito User Pool
  A OIDC endpoint and whose ``AllowedAudience`` contains the configured
  client id.
- A REQUEST interceptor Lambda named ``opencode-identity-interceptor``
  attached via ``InterceptorConfigurations``.
- Gateway ``Name == "opencode-gateway"`` and
  ``ExceptionLevel == "DEBUG"``.

Uses Hypothesis to generate random valid Cognito user pool IDs, client
IDs, and runtime references, then synthesizes the gateway stack and
asserts the preservation invariants above.
"""

from __future__ import annotations

import json
from pathlib import Path

import aws_cdk as cdk
from aws_cdk import assertions
from aws_cdk import aws_bedrockagentcore as bedrockagentcore
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_kms as kms
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from stacks.gateway_stack import GatewayStack

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CDK_JSON_PATH = Path(__file__).resolve().parents[2] / "cdk.json"


def _load_cdk_context() -> dict:
    with open(CDK_JSON_PATH) as f:
        return json.load(f)["context"]


def _build_gateway_template(
    user_pool_id: str,
    client_id: str,
    region: str = "us-east-1",
) -> assertions.Template:
    """Synthesize the GatewayStack and return the CloudFormation template.

    Creates mock CfnRuntime objects to satisfy the constructor, then returns
    the synthesized CloudFormation template for assertion.
    """
    ctx = _load_cdk_context()
    app = cdk.App(context=ctx)
    env = cdk.Environment(account="123456789012", region=region)

    # Helper stack to hold mock runtimes and user pool
    helper_stack = cdk.Stack(app, "HelperStack", env=env)

    user_pool = cognito.UserPool.from_user_pool_id(
        helper_stack, "MockUserPool", user_pool_id,
    )

    mock_network_config = bedrockagentcore.CfnRuntime.NetworkConfigurationProperty(
        network_mode="PUBLIC",
    )

    opencode_runtime = bedrockagentcore.CfnRuntime(
        helper_stack,
        "MockOpenCodeRuntime",
        agent_runtime_name="opencode_runtime",
        agent_runtime_artifact=bedrockagentcore.CfnRuntime.AgentRuntimeArtifactProperty(
            container_configuration=bedrockagentcore.CfnRuntime.ContainerConfigurationProperty(
                container_uri="123456789012.dkr.ecr.us-east-1.amazonaws.com/opencode:latest",
            ),
        ),
        role_arn="arn:aws:iam::123456789012:role/mock-role",
        network_configuration=mock_network_config,
    )

    stub_policy_engine_arn = (
        f"arn:aws:bedrock-agentcore:{region}:123456789012:policy-engine/STUB000001"
    )

    cmk_stack = cdk.Stack(app, "StubCmkStack", env=env)
    stub_cmk = kms.Key(cmk_stack, "StubCmk")

    gateway_stack = GatewayStack(
        app,
        "TestGatewayStack",
        cognito_user_pool=user_pool,
        cognito_client_id=client_id,
        opencode_runtime=opencode_runtime,
        policy_engine_arn=stub_policy_engine_arn,
        cmk=stub_cmk,
        env=env,
    )

    return assertions.Template.from_stack(gateway_stack)


# ---------------------------------------------------------------------------
# Strategies — generate random valid Cognito user pool IDs and client IDs
# ---------------------------------------------------------------------------

# AWS regions where AgentCore is available
_REGIONS = ["us-east-1", "us-east-1", "eu-west-1", "eu-central-1", "ap-northeast-1"]

# Cognito user pool ID format: {region}_{alphanumeric}
cognito_pool_id_strategy = st.builds(
    lambda region, suffix: f"{region}_{suffix}",
    region=st.sampled_from(_REGIONS),
    suffix=st.from_regex(r"[a-zA-Z0-9]{9}", fullmatch=True),
)

# Cognito client ID: alphanumeric, 26 characters
cognito_client_id_strategy = st.from_regex(r"[a-z0-9]{26}", fullmatch=True)


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestGatewayPreservation:
    """Property 2: Preservation — Inbound Auth and Interceptor Unchanged.

    **Validates: Requirements 3.1, 3.2, 3.3, 3.6**

    For any valid constructor inputs, the Gateway's inbound authorizer,
    REQUEST interceptor, and gateway identity SHALL remain unchanged.

    These tests PASS on UNFIXED code — they capture baseline behavior.
    """

    @given(
        user_pool_id=cognito_pool_id_strategy,
        client_id=cognito_client_id_strategy,
        region=st.sampled_from(_REGIONS),
    )
    @settings(
        max_examples=5,
        deadline=30_000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_inbound_authorizer_uses_cognito_discovery_url_and_audience(
        self,
        user_pool_id: str,
        client_id: str,
        region: str,
    ):
        """**Validates: Requirements 3.1**

        For all valid constructor inputs, the Gateway's inbound authorizer
        SHALL use the inbound Cognito User Pool A discovery URL format
        https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration
        and the provided cognito_client_id as audience.
        """
        template = _build_gateway_template(user_pool_id, client_id, region)
        tpl = template.to_json()

        # Find the Gateway resource (AWS::BedrockAgentCore::Gateway)
        gateways = {
            lid: res
            for lid, res in tpl["Resources"].items()
            if res["Type"] == "AWS::BedrockAgentCore::Gateway"
        }

        assert len(gateways) == 1, (
            f"Expected exactly 1 Gateway resource, found {len(gateways)}"
        )

        _lid, gateway = next(iter(gateways.items()))
        props = gateway.get("Properties", {})
        auth_config = props.get("AuthorizerConfiguration", {})
        custom_jwt = auth_config.get("CustomJWTAuthorizer", {})

        # Verify discovery URL matches the expected Cognito format
        expected_discovery_url = (
            f"https://cognito-idp.{region}.amazonaws.com"
            f"/{user_pool_id}/.well-known/openid-configuration"
        )
        actual_discovery_url = custom_jwt.get("DiscoveryUrl", "")
        assert actual_discovery_url == expected_discovery_url, (
            f"Discovery URL mismatch.\n"
            f"  Expected: {expected_discovery_url}\n"
            f"  Actual:   {actual_discovery_url}"
        )

        # Verify allowed audience contains the provided client_id
        allowed_audience = custom_jwt.get("AllowedAudience", [])
        assert client_id in allowed_audience, (
            f"Expected client_id '{client_id}' in AllowedAudience, "
            f"got {allowed_audience}"
        )

    @given(
        user_pool_id=cognito_pool_id_strategy,
        client_id=cognito_client_id_strategy,
    )
    @settings(
        max_examples=5,
        deadline=30_000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_request_interceptor_lambda_attached(
        self,
        user_pool_id: str,
        client_id: str,
    ):
        """**Validates: Requirements 3.2**

        For all valid constructor inputs, the REQUEST interceptor Lambda
        (opencode-identity-interceptor) SHALL be attached to the Gateway.
        """
        template = _build_gateway_template(user_pool_id, client_id)
        tpl = template.to_json()

        # Verify the interceptor Lambda function exists with the correct name
        lambdas = {
            lid: res
            for lid, res in tpl["Resources"].items()
            if res["Type"] == "AWS::Lambda::Function"
        }

        interceptor_found = False
        for _lid, fn in lambdas.items():
            fn_name = fn.get("Properties", {}).get("FunctionName", "")
            if fn_name == "opencode-identity-interceptor":
                interceptor_found = True
                break

        assert interceptor_found, (
            "Expected Lambda function 'opencode-identity-interceptor' not found. "
            f"Found Lambda functions: {[fn.get('Properties', {}).get('FunctionName', 'unnamed') for fn in lambdas.values()]}"
        )

        # Verify the Gateway has interceptor configuration
        gateways = {
            lid: res
            for lid, res in tpl["Resources"].items()
            if res["Type"] == "AWS::BedrockAgentCore::Gateway"
        }

        assert len(gateways) == 1, (
            f"Expected exactly 1 Gateway resource, found {len(gateways)}"
        )

        _lid, gateway = next(iter(gateways.items()))
        props = gateway.get("Properties", {})

        # The L2 Gateway construct uses InterceptorConfigurations (plural)
        # Each entry has InterceptionPoints (array) and Interceptor.Lambda.Arn
        interceptor_configs = props.get("InterceptorConfigurations", [])

        # There should be at least one interceptor with REQUEST interception point
        request_interceptors = [
            ic for ic in interceptor_configs
            if "REQUEST" in ic.get("InterceptionPoints", [])
        ]
        assert len(request_interceptors) >= 1, (
            f"Expected at least 1 REQUEST interceptor, found {len(request_interceptors)}. "
            f"All interceptor configs: {interceptor_configs}"
        )

        # Verify the interceptor references a Lambda function
        for ic in request_interceptors:
            lambda_config = ic.get("Interceptor", {}).get("Lambda", {})
            assert lambda_config.get("Arn"), (
                f"REQUEST interceptor missing Lambda ARN: {ic}"
            )

    @given(
        user_pool_id=cognito_pool_id_strategy,
        client_id=cognito_client_id_strategy,
    )
    @settings(
        max_examples=5,
        deadline=30_000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_gateway_name_and_exception_level(
        self,
        user_pool_id: str,
        client_id: str,
    ):
        """**Validates: Requirements 3.6**

        For all valid constructor inputs, the gateway name SHALL be
        'opencode-gateway' and exception level SHALL be 'DEBUG'.
        """
        template = _build_gateway_template(user_pool_id, client_id)
        tpl = template.to_json()

        gateways = {
            lid: res
            for lid, res in tpl["Resources"].items()
            if res["Type"] == "AWS::BedrockAgentCore::Gateway"
        }

        assert len(gateways) == 1, (
            f"Expected exactly 1 Gateway resource, found {len(gateways)}"
        )

        _lid, gateway = next(iter(gateways.items()))
        props = gateway.get("Properties", {})

        # Verify gateway name
        gateway_name = props.get("Name", "")
        assert gateway_name == "opencode-gateway", (
            f"Expected gateway name 'opencode-gateway', got '{gateway_name}'"
        )

        # Verify exception level is DEBUG
        exception_level = props.get("ExceptionLevel", "")
        assert exception_level == "DEBUG", (
            f"Expected exception level 'DEBUG', got '{exception_level}'"
        )
