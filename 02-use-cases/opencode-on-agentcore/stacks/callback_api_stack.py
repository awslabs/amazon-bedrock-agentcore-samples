# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""OpenCode CallbackApi stack — OAuth callback HTTP API + Lambda.

Extracted from IdentityStack so that both AgentCoreStack and IdentityStack
can depend on the callback URL without creating a circular dependency.

Requirements: 2.2, 3.3, 3.3.1, 3.4, 3.4.1
"""

import json

import aws_cdk as cdk
from aws_cdk import (
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_authorizers as apigwv2_authorizers,
    aws_apigatewayv2_integrations as apigwv2_integrations,
    aws_iam as iam,
    aws_kms as kms,
    aws_lambda as _lambda,
    aws_logs as logs,
    RemovalPolicy,
)
import cdk_nag
from constructs import Construct

from stacks import retention_days


# ---------------------------------------------------------------------------
# Inline Lambda code for the OAuth callback authorizer
# ---------------------------------------------------------------------------
AUTHORIZER_LAMBDA_CODE = """
import json
import re

_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_\\-/:.%]{10,512}$")

def handler(event, context):
    q = event.get("queryStringParameters") or {}
    session_id = q.get("session_id", "")
    state = q.get("state", "")

    print(f"Authorizer: session_id={session_id!r}, state={state!r}")
    print(f"Authorizer: all params={json.dumps(q)}")

    if not session_id or not state:
        print("DENY: missing session_id or state")
        return {"isAuthorized": False}
    if not _SESSION_ID_RE.match(session_id):
        print(f"DENY: session_id does not match regex")
        return {"isAuthorized": False}
    try:
        parsed = json.loads(state)
        if not isinstance(parsed, dict) or "user_id" not in parsed:
            print(f"DENY: state missing user_id, parsed={parsed}")
            return {"isAuthorized": False}
    except (json.JSONDecodeError, TypeError):
        print(f"DENY: state not valid JSON")
        return {"isAuthorized": False}
    print("ALLOW")
    return {"isAuthorized": True}
"""


class CallbackApiStack(cdk.Stack):
    """OAuth callback HTTP API — fronts the callback Lambda."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        cmk: kms.IKey,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        log_retention = self.node.try_get_context("cloudwatch_log_retention_days") or 90

        # -----------------------------------------------------------------
        # OAuth2 Callback Lambda (fronted by API Gateway HTTP API)
        # Replaces the disabled Function URL — PalisadeTicket-122296 (Sev-2)
        # -----------------------------------------------------------------
        callback_log_group = logs.LogGroup(
            self, "OAuthCallbackLogGroup",
            retention=retention_days(log_retention),
            removal_policy=RemovalPolicy.RETAIN,
            encryption_key=cmk,
        )

        self.callback_fn = _lambda.Function(
            self,
            "OAuthCallbackFn",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=_lambda.Code.from_asset("lambda/oauth_callback"),
            timeout=cdk.Duration.seconds(15),
            log_group=callback_log_group,
        )
        self.callback_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock-agentcore:CompleteResourceTokenAuth"],
                resources=["*"],
            )
        )
        # CompleteResourceTokenAuth needs to read the OAuth client secret
        # from Secrets Manager (managed by AgentCore Identity).
        self.callback_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=[
                    f"arn:aws:secretsmanager:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:secret:bedrock-agentcore-identity*",
                ],
            )
        )

        # -----------------------------------------------------------------
        # Lambda Authorizer -- validates session_id format and state JSON
        # structure.  This is a structural validator, not full
        # authentication, because the callback URL must remain publicly
        # reachable for OAuth providers.
        # Satisfies Palisade apigatewayv2.route.no_auth slat.
        # -----------------------------------------------------------------
        authorizer_log_group = logs.LogGroup(
            self, "OAuthCallbackAuthorizerLogGroup",
            retention=retention_days(log_retention),
            removal_policy=RemovalPolicy.RETAIN,
            encryption_key=cmk,
        )

        authorizer_fn = _lambda.Function(
            self,
            "OAuthCallbackAuthorizerFn",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=_lambda.Code.from_inline(AUTHORIZER_LAMBDA_CODE),
            timeout=cdk.Duration.seconds(5),
            log_group=authorizer_log_group,
        )

        authorizer = apigwv2_authorizers.HttpLambdaAuthorizer(
            "OAuthCallbackAuthorizer",
            handler=authorizer_fn,
            response_types=[apigwv2_authorizers.HttpLambdaResponseType.SIMPLE],
            results_cache_ttl=cdk.Duration.seconds(0),
            identity_source=[
                "$request.querystring.session_id",
                "$request.querystring.state",
            ],
        )

        # -----------------------------------------------------------------
        # API Gateway HTTP API — fronts the callback Lambda
        # -----------------------------------------------------------------
        callback_integration = apigwv2_integrations.HttpLambdaIntegration(
            "OAuthCallbackIntegration",
            handler=self.callback_fn,
        )

        self.http_api = apigwv2.HttpApi(
            self, "OAuthCallbackApi",
            api_name="opencode-oauth-callback-api",
            description="Fronts OAuth callback Lambda — replaces Function URL",
        )

        self.http_api.add_routes(
            path="/callback",
            methods=[apigwv2.HttpMethod.GET],
            integration=callback_integration,
            authorizer=authorizer,
        )

        # Ensure the HTTP API route is created after both Lambda functions exist.
        # Without this, CloudFormation may try to create the Lambda Permission
        # (apigateway → lambda:InvokeFunction) before the Lambda is ready.
        self.http_api.node.add_dependency(self.callback_fn)
        self.http_api.node.add_dependency(authorizer_fn)

        # Build the callback URL from the HTTP API invoke URL
        self.callback_url_value = f"{self.http_api.url}callback"

        # -----------------------------------------------------------------
        # CloudWatch access logging for the HTTP API $default stage
        # -----------------------------------------------------------------
        api_access_log_group = logs.LogGroup(
            self, "OAuthCallbackApiAccessLogs",
            retention=retention_days(log_retention),
            removal_policy=RemovalPolicy.RETAIN,
            encryption_key=cmk,
        )

        default_stage = self.http_api.default_stage.node.default_child
        default_stage.access_log_settings = apigwv2.CfnStage.AccessLogSettingsProperty(
            destination_arn=api_access_log_group.log_group_arn,
            format=json.dumps({
                "requestId": "$context.requestId",
                "ip": "$context.identity.sourceIp",
                "requestTime": "$context.requestTime",
                "httpMethod": "$context.httpMethod",
                "path": "$context.path",
                "status": "$context.status",
                "responseLength": "$context.responseLength",
                "integrationError": "$context.integrationErrorMessage",
            }),
        )

        # -----------------------------------------------------------------
        # Outputs
        # -----------------------------------------------------------------
        cdk.CfnOutput(
            self, "OAuthCallbackUrl",
            value=self.callback_url_value,
            description="OAuth callback URL (API Gateway HTTP API)",
        )

        # -----------------------------------------------------------------
        # cdk-nag suppressions
        # -----------------------------------------------------------------
        # Callback Lambda
        cdk_nag.NagSuppressions.add_resource_suppressions(
            self.callback_fn,
            [
                cdk_nag.NagPackSuppression(
                    id="AwsSolutions-IAM5",
                    reason=(
                        "bedrock-agentcore:CompleteResourceTokenAuth does not "
                        "support resource-level permissions in the IAM Service "
                        "Authorization Reference today; the action must be "
                        "granted on Resource: '*'. The Lambda is a "
                        "short-lived authorizer invoked only from the OAuth "
                        "callback HTTP API route (Lambda authorizer gated). "
                        "See docs/THREAT-MODEL.md section 'OAuth 3LO callback' "
                        "for the compensating controls."
                    ),
                ),
                cdk_nag.NagPackSuppression(
                    id="AwsSolutions-IAM4",
                    reason="Lambda basic execution role is AWS managed.",
                    applies_to=["Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"],
                ),
                cdk_nag.NagPackSuppression(
                    id="AwsSolutions-L1",
                    reason="Python 3.12 is the latest stable runtime for this Lambda.",
                ),
            ],
            apply_to_children=True,
        )
        # Authorizer Lambda
        cdk_nag.NagSuppressions.add_resource_suppressions(
            authorizer_fn,
            [
                cdk_nag.NagPackSuppression(
                    id="AwsSolutions-IAM4",
                    reason="Lambda basic execution role is AWS managed — lightweight authorizer.",
                    applies_to=["Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"],
                ),
                cdk_nag.NagPackSuppression(
                    id="AwsSolutions-L1",
                    reason="Python 3.12 is the latest stable runtime for this Lambda.",
                ),
            ],
            apply_to_children=True,
        )
        # Log retention Lambda (CDK-managed)
        cdk_nag.NagSuppressions.add_stack_suppressions(
            self,
            [
                cdk_nag.NagPackSuppression(
                    id="AwsSolutions-IAM4",
                    reason="CDK log retention Lambda uses AWS managed execution policy.",
                    applies_to=["Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"],
                ),
                cdk_nag.NagPackSuppression(
                    id="AwsSolutions-IAM5",
                    reason="CDK log retention Lambda requires wildcard log permissions.",
                ),
            ],
        )
