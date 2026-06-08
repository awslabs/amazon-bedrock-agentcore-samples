# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""OpenCode Gateway stack — Managed AgentCore Gateway with interceptor.

Serverless MCP gateway with per-user identity via REQUEST interceptor.
The interceptor extracts user_id from the JWT and injects it into tool arguments.

The single MCP ``GatewayTarget`` (``opencode``) and the Gateway to
``PolicyEngine`` association are both expressed in CloudFormation via the
``aws_cdk.aws_bedrock_agentcore_alpha`` L2 and a property-override escape hatch.

Requirements: 13.1, 13.2, 13.3, 13.4, 19.1, 19.3
"""

import aws_cdk as cdk
from aws_cdk import (
    aws_bedrockagentcore as bedrockagentcore,
    aws_cognito as cognito,
    aws_kms as kms,
    aws_lambda as _lambda,
    aws_logs as logs,
    RemovalPolicy,
)
import aws_cdk.aws_bedrock_agentcore_alpha as agentcore
import cdk_nag
from constructs import Construct

from stacks import retention_days


class GatewayStack(cdk.Stack):
    """Gateway stack — Gateway, MCP target, and Cedar PolicyEngine link."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        cognito_user_pool: cognito.IUserPool,
        cognito_client_id: str,
        opencode_runtime: bedrockagentcore.CfnRuntime,
        policy_engine_arn: str,
        cmk: kms.IKey,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        log_retention = self.node.try_get_context("cloudwatch_log_retention_days") or 90

        discovery_url = (
            f"https://cognito-idp.{self.region}.amazonaws.com"
            f"/{cognito_user_pool.user_pool_id}/.well-known/openid-configuration"
        )

        self.gateway = agentcore.Gateway(
            self,
            "OpenCodeGateway",
            gateway_name="opencode-gateway",
            description="OpenCode MCP Gateway with per-user identity",
            authorizer_configuration=agentcore.CustomJwtAuthorizer(
                discovery_url=discovery_url,
                allowed_audience=[cognito_client_id],
            ),
            exception_level=agentcore.GatewayExceptionLevel.DEBUG,
        )

        # -----------------------------------------------------------------
        # REQUEST interceptor — extracts user_id from JWT, injects into tool args
        # -----------------------------------------------------------------
        interceptor_log_group = logs.LogGroup(
            self, "InterceptorLogGroup",
            retention=retention_days(log_retention),
            removal_policy=RemovalPolicy.RETAIN,
            encryption_key=cmk,
        )

        interceptor_fn = _lambda.Function(
            self,
            "IdentityInterceptor",
            function_name="opencode-identity-interceptor",
            runtime=_lambda.Runtime.PYTHON_3_14,
            handler="interceptor.index.handler",
            code=_lambda.Code.from_asset(
                "lambda",
                exclude=[
                    "oauth_callback", "__pycache__", "**/__pycache__",
                ],
            ),
            timeout=cdk.Duration.seconds(5),
            memory_size=128,
            log_group=interceptor_log_group,
        )

        self.gateway.add_interceptor(
            agentcore.LambdaInterceptor.for_request(
                interceptor_fn,
                pass_request_headers=True,
            ),
        )

        # -----------------------------------------------------------------
        # Grant Gateway IAM role permission to invoke runtimes via SigV4.
        # Required for the GATEWAY_IAM_ROLE credential provider on the target.
        # -----------------------------------------------------------------
        import aws_cdk.aws_iam as iam

        opencode_runtime_arn = (
            f"arn:aws:bedrock-agentcore:{self.region}:{self.account}"
            f":runtime/{opencode_runtime.ref}"
        )

        self.gateway.role.add_to_principal_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock-agentcore:InvokeAgentRuntime",
                    "bedrock-agentcore:InvokeGateway",
                    "bedrock-agentcore:GetWorkloadAccessToken",
                    "bedrock-agentcore:GetResourceOauth2Token",
                    "bedrock-agentcore:GetPolicyEngine",
                    "bedrock-agentcore:AuthorizeAction",
                    "bedrock-agentcore:PartiallyAuthorizeActions",
                ],
                resources=[
                    opencode_runtime_arn,
                    f"{opencode_runtime_arn}/*",
                    f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:gateway/*",
                    f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:workload-identity-directory/*",
                    f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:token-vault/*",
                    f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:policy-engine/*",
                ],
            )
        )

        # 3LO token vault: Gateway needs to read AgentCore identity secrets
        # for OAuth token vault operations (3LO credential providers)
        self.gateway.role.add_to_principal_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=[
                    f"arn:aws:secretsmanager:{self.region}:{self.account}:secret:bedrock-agentcore-identity*",
                ],
            )
        )

        # -----------------------------------------------------------------
        # MCP GatewayTarget — opencode runtime via GATEWAY_IAM_ROLE (SigV4).
        #
        # The runtime ARN must be URL-encoded in the endpoint path, so the
        # ``%3A`` / ``%2F`` separators are baked in as literals and joined
        # with the CFN runtime-id token via ``Fn::Join``.
        # -----------------------------------------------------------------
        encoded_runtime_arn = cdk.Fn.join(
            "",
            [
                "arn%3Aaws%3Abedrock-agentcore%3A",
                self.region,
                "%3A",
                self.account,
                "%3Aruntime%2F",
                opencode_runtime.attr_agent_runtime_id,
            ],
        )

        mcp_endpoint = cdk.Fn.join(
            "",
            [
                "https://bedrock-agentcore.",
                self.region,
                ".amazonaws.com/runtimes/",
                encoded_runtime_arn,
                "/invocations",
            ],
        )

        self.opencode_target = self.gateway.add_mcp_server_target(
            "OpenCodeTarget",
            gateway_target_name="opencode",
            description="OpenCode unified runtime - GATEWAY_IAM_ROLE SigV4 auth",
            endpoint=mcp_endpoint,
            credential_provider_configurations=[
                agentcore.GatewayCredentialProvider.from_iam_role(),
            ],
        )

        # The alpha L2 ``GatewayCredentialProvider.from_iam_role()`` emits
        # only ``{"CredentialProviderType": "GATEWAY_IAM_ROLE"}`` in the
        # synthesized template, but the CFN resource handler requires the
        # sibling ``CredentialProvider.IamCredentialProvider`` sub-object
        # (see the CFN docs for
        # ``AWS::BedrockAgentCore::GatewayTarget.CredentialProviderConfiguration``).
        # Without it, CFN returns
        # ``IamCredentialProvider is required for mcpServer targets using
        # IAM authentication`` and the stack rolls back. Patch via an
        # escape hatch until the alpha module catches up.
        cfn_target: bedrockagentcore.CfnGatewayTarget = self.opencode_target.node.default_child  # type: ignore[assignment]
        cfn_target.add_property_override(
            "CredentialProviderConfigurations.0.CredentialProvider",
            {"IamCredentialProvider": {"Service": "bedrock-agentcore"}},
        )

        # -----------------------------------------------------------------
        # PolicyEngineConfiguration — link Cedar PolicyEngine in LOG_ONLY mode.
        #
        # The alpha L2 ``Gateway`` does not expose ``policy_engine_configuration``
        # as a typed prop, so reach the underlying ``CfnGateway`` and attach
        # the configuration via ``add_property_override``.
        #
        # The CFN handler for ``AWS::BedrockAgentCore::Gateway`` validates the
        # policy-engine reference by calling ``GetPolicyEngine`` using the
        # Gateway's service role. That role's ``DefaultPolicy`` (which grants
        # ``bedrock-agentcore:GetPolicyEngine``) is a sibling resource in the
        # same stack, and CFN's default ordering creates them in parallel —
        # which races and results in ``AccessDenied`` at gateway-create time.
        # Force the Gateway resource to wait for the DefaultPolicy.
        # -----------------------------------------------------------------
        cfn_gateway: bedrockagentcore.CfnGateway = self.gateway.node.default_child  # type: ignore[assignment]
        cfn_gateway.add_property_override(
            "PolicyEngineConfiguration",
            {"Arn": policy_engine_arn, "Mode": "LOG_ONLY"},
        )

        # Make the Gateway explicitly depend on the Gateway role's
        # DefaultPolicy so ``GetPolicyEngine`` is grantable before the CFN
        # handler validates the PolicyEngineConfiguration.
        gateway_role_default_policy = self.gateway.role.node.try_find_child("DefaultPolicy")
        if gateway_role_default_policy is not None:
            cfn_default_policy = gateway_role_default_policy.node.default_child
            if cfn_default_policy is not None:
                cfn_gateway.add_depends_on(cfn_default_policy)

        # -----------------------------------------------------------------
        # Outputs
        # -----------------------------------------------------------------
        cdk.CfnOutput(self, "GatewayId", value=self.gateway.gateway_id)
        cdk.CfnOutput(self, "GatewayUrl", value=self.gateway.gateway_url or "pending")
        cdk.CfnOutput(self, "GatewayArn", value=self.gateway.gateway_arn)

        # -----------------------------------------------------------------
        # cdk-nag suppressions
        # -----------------------------------------------------------------
        cdk_nag.NagSuppressions.add_stack_suppressions(
            self,
            [
                cdk_nag.NagPackSuppression(
                    id="AwsSolutions-IAM5",
                    reason=(
                        "Gateway role uses two wildcard patterns: "
                        "(1) bedrock-agentcore resource ARNs scoped to the "
                        "account/region with resource-type prefixes "
                        "(gateway/*, workload-identity-directory/*, "
                        "token-vault/*, policy-engine/*, runtime/<id>/*); "
                        "each path segment that matters is pinned, only "
                        "instance IDs are wildcarded. "
                        "(2) Secrets Manager 'bedrock-agentcore-identity*' "
                        "matches the naming pattern AgentCore Identity uses "
                        "for OAuth token-vault secrets in the customer's "
                        "account; these are created and managed by AgentCore "
                        "Identity and cannot be pinned at CDK synth time. "
                        "See docs/THREAT-MODEL.md section 'Gateway → Runtime (SigV4)' "
                        "and the 'Runtime execution role' section for the "
                        "threat-to-control mapping."
                    ),
                ),
                cdk_nag.NagPackSuppression(
                    id="AwsSolutions-IAM4",
                    reason="Gateway L2 construct and Lambda use managed policies.",
                ),
                cdk_nag.NagPackSuppression(
                    id="AwsSolutions-L1",
                    reason="Python 3.14 is current stable runtime.",
                ),
            ],
        )
