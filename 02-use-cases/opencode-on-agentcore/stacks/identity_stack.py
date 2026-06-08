# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""OpenCode Identity stack — Workload Identity + Credential Providers for user-delegated 3LO git access.

Creates the workload identity via CloudFormation and registers OAuth2 credential
providers via a Custom Resource (Lambda-backed SDK call).

GitHub OAuth App client_id and client_secret must be stored in Secrets Manager
at 'opencode/github-oauth-app' as JSON: {"client_id": "...", "client_secret": "..."}

Requirements: 5.1, 5.2
"""

import aws_cdk as cdk
from aws_cdk import (
    aws_bedrockagentcore as bedrockagentcore,
    aws_iam as iam,
    aws_kms as kms,
    aws_lambda as _lambda,
    aws_logs as logs,
    aws_secretsmanager as secretsmanager,
    custom_resources as cr,
    RemovalPolicy,
)
import cdk_nag
from constructs import Construct

from stacks import retention_days


class IdentityStack(cdk.Stack):
    """AgentCore Identity — workload identity + credential providers per git host."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        cmk: kms.IKey,
        callback_url: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        log_retention = self.node.try_get_context("cloudwatch_log_retention_days") or 90

        # -----------------------------------------------------------------
        # Workload Identity (CloudFormation native)
        # -----------------------------------------------------------------
        self.workload_identity = bedrockagentcore.CfnWorkloadIdentity(
            self,
            "OpenCodeWorkloadIdentity",
            name="opencode_runtime",
            allowed_resource_oauth2_return_urls=[
                callback_url,
            ],
        )

        # -----------------------------------------------------------------
        # GitHub OAuth App secret (must be pre-created in Secrets Manager)
        # JSON: {"client_id": "Iv1.xxx", "client_secret": "xxx"}
        # -----------------------------------------------------------------
        github_oauth_secret = secretsmanager.Secret.from_secret_name_v2(
            self, "GitHubOAuthSecret", "opencode/github-oauth-app"
        )

        # -----------------------------------------------------------------
        # Custom Resource Lambda — registers OAuth2 credential provider
        # via the AgentCore Identity SDK (no CFN resource available)
        # -----------------------------------------------------------------
        provider_fn_log_group = logs.LogGroup(
            self, "CredentialProviderFnLogGroup",
            retention=retention_days(log_retention),
            removal_policy=RemovalPolicy.RETAIN,
            encryption_key=cmk,
        )

        provider_fn = _lambda.Function(
            self,
            "CredentialProviderFn",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="index.handler",
            timeout=cdk.Duration.seconds(60),
            log_group=provider_fn_log_group,
            code=_lambda.Code.from_inline(CREDENTIAL_PROVIDER_LAMBDA_CODE),
            environment={
                "GITHUB_OAUTH_SECRET_ARN": github_oauth_secret.secret_arn,
            },
        )

        # Grant the Lambda permission to read the secret and call Identity APIs
        github_oauth_secret.grant_read(provider_fn)
        provider_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock-agentcore:CreateOauth2CredentialProvider",
                    "bedrock-agentcore:UpdateOauth2CredentialProvider",
                    "bedrock-agentcore:DeleteOauth2CredentialProvider",
                    "bedrock-agentcore:GetOauth2CredentialProvider",
                    "bedrock-agentcore:CreateTokenVault",
                ],
                resources=["*"],
            )
        )

        provider_cr_log_group = logs.LogGroup(
            self, "CredentialProviderCRLogGroup",
            retention=retention_days(log_retention),
            removal_policy=RemovalPolicy.RETAIN,
            encryption_key=cmk,
        )

        provider = cr.Provider(
            self,
            "CredentialProviderCR",
            on_event_handler=provider_fn,
            log_group=provider_cr_log_group,
        )

        cdk.CustomResource(
            self,
            "GitHubCredentialProvider",
            service_token=provider.service_token,
            properties={
                "provider_name": "github-provider",
                "vendor": "GithubOauth2",
                "secret_arn": github_oauth_secret.secret_arn,
            },
        )

        # -----------------------------------------------------------------
        # Outputs
        # -----------------------------------------------------------------
        cdk.CfnOutput(
            self, "WorkloadIdentityName",
            value=self.workload_identity.name,
        )
        cdk.CfnOutput(
            self, "WorkloadIdentityArn",
            value=self.workload_identity.attr_workload_identity_arn,
        )

        # -----------------------------------------------------------------
        # cdk-nag suppressions
        # -----------------------------------------------------------------
        cdk_nag.NagSuppressions.add_resource_suppressions(
            provider_fn,
            [
                cdk_nag.NagPackSuppression(
                    id="AwsSolutions-IAM5",
                    reason=(
                        "AgentCore Identity credential-provider APIs "
                        "(Create/Update/Delete/GetOauth2CredentialProvider, "
                        "CreateTokenVault) do not support resource-level "
                        "permissions in the IAM Service Authorization "
                        "Reference today; they must be granted on "
                        "Resource: '*'. The Lambda runs only as a custom "
                        "resource during stack deploy/update/delete, not on "
                        "the request path. See docs/THREAT-MODEL.md section "
                        "'Runtime execution role' for context on AgentCore "
                        "Identity API scoping."
                    ),
                ),
                cdk_nag.NagPackSuppression(
                    id="AwsSolutions-IAM4",
                    reason="Lambda basic execution role is AWS managed — acceptable for custom resource.",
                    applies_to=["Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"],
                ),
                cdk_nag.NagPackSuppression(
                    id="AwsSolutions-L1",
                    reason="Python 3.12 is the latest stable runtime supported by inline code.",
                ),
            ],
            apply_to_children=True,
        )
        cdk_nag.NagSuppressions.add_resource_suppressions(
            provider.node.find_child("framework-onEvent"),
            [
                cdk_nag.NagPackSuppression(
                    id="AwsSolutions-IAM5",
                    reason="CDK Custom Resource framework Lambda requires wildcard log permissions.",
                ),
                cdk_nag.NagPackSuppression(
                    id="AwsSolutions-IAM4",
                    reason="CDK Custom Resource framework uses AWS managed Lambda execution policy.",
                    applies_to=["Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"],
                ),
                cdk_nag.NagPackSuppression(
                    id="AwsSolutions-L1",
                    reason="CDK Custom Resource framework controls its own runtime version.",
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


# ---------------------------------------------------------------------------
# Inline Lambda code for the Custom Resource
# ---------------------------------------------------------------------------
CREDENTIAL_PROVIDER_LAMBDA_CODE = """
import json
import os
import boto3

def handler(event, context):
    request_type = event["RequestType"]
    props = event["ResourceProperties"]
    provider_name = props["provider_name"]
    vendor = props["vendor"]
    secret_arn = props["secret_arn"]
    region = os.environ.get("AWS_REGION", "us-east-1")

    # Read GitHub OAuth App credentials from Secrets Manager
    # If the secret doesn't exist yet, skip registration (user will run
    # setup-oauth-app.sh later, which registers the provider directly).
    sm = boto3.client("secretsmanager", region_name=region)
    try:
        secret_value = json.loads(sm.get_secret_value(SecretId=secret_arn)["SecretString"])
        client_id = secret_value["client_id"]
        client_secret = secret_value["client_secret"]
    except sm.exceptions.ResourceNotFoundException:
        print(f"Secret {secret_arn} not found — skipping credential provider registration.")
        print("Run scripts/setup-oauth-app.sh to store credentials and register the provider.")
        return {"PhysicalResourceId": provider_name}
    except Exception as e:
        print(f"Warning: could not read secret {secret_arn}: {e}")
        print("Run scripts/setup-oauth-app.sh to store credentials and register the provider.")
        return {"PhysicalResourceId": provider_name}

    identity = boto3.client("bedrock-agentcore-control", region_name=region)

    if request_type in ("Create", "Update"):
        try:
            identity.create_oauth2_credential_provider(
                name=provider_name,
                credentialProviderVendor=vendor,
                oauth2ProviderConfigInput={
                    "githubOauth2ProviderConfig": {
                        "clientId": client_id,
                        "clientSecret": client_secret,
                    }
                },
            )
        except Exception as e:
            if "already exists" in str(e):
                print(f"Credential provider '{provider_name}' already exists — skipping.")
            else:
                raise
        return {"PhysicalResourceId": provider_name}

    if request_type == "Delete":
        try:
            identity.delete_oauth2_credential_provider(name=provider_name)
        except Exception:
            pass
        return {"PhysicalResourceId": provider_name}

    return {"PhysicalResourceId": provider_name}
"""
