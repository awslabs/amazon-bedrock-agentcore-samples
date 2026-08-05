"""Gateway, IAM and Cognito helpers built directly on the bedrock-agentcore SDKs.

Uses `boto3` clients for `bedrock-agentcore-control`, `iam` and `cognito-idp`
rather than the deprecated starter toolkit. Follows the same approach as
01-features/07-centralize-and-govern-your-ai-infrastructure/01-gateway.
"""

import json
import secrets
import time

import boto3
import requests

MCP_PROTOCOL_VERSION = "2025-11-25"


class GatewaySetup:
    """Thin wrapper around the bedrock-agentcore-control boto3 client."""

    def __init__(self, region: str):
        self.region = region
        self.client = boto3.client("bedrock-agentcore-control", region_name=region)
        self.iam = boto3.client("iam")
        self.sts = boto3.client("sts")
        self.cognito = boto3.client("cognito-idp", region_name=region)
        self.account_id = self.sts.get_caller_identity()["Account"]

    # --- inbound auth (Cognito) --------------------------------------------

    def create_cognito_authorizer(self, name: str) -> dict:
        """Create a Cognito user pool + M2M client for inbound gateway auth.

        Returns the values needed to configure a CUSTOM_JWT authorizer and to
        mint access tokens for calling the gateway.
        """
        pool = self.cognito.create_user_pool(PoolName=f"{name}-pool")
        pool_id = pool["UserPool"]["Id"]

        domain = f"{name.lower()}-{secrets.token_hex(4)}"
        self.cognito.create_user_pool_domain(Domain=domain, UserPoolId=pool_id)

        # A resource server defines the scope the M2M client requests.
        scope_name = "invoke"
        resource_server_id = f"{name.lower()}-api"
        self.cognito.create_resource_server(
            UserPoolId=pool_id,
            Identifier=resource_server_id,
            Name=f"{name} API",
            Scopes=[{"ScopeName": scope_name, "ScopeDescription": "Invoke gateway"}],
        )
        scope = f"{resource_server_id}/{scope_name}"

        client = self.cognito.create_user_pool_client(
            UserPoolId=pool_id,
            ClientName=f"{name}-client",
            GenerateSecret=True,
            AllowedOAuthFlows=["client_credentials"],
            AllowedOAuthScopes=[scope],
            AllowedOAuthFlowsUserPoolClient=True,
            SupportedIdentityProviders=["COGNITO"],
            ExplicitAuthFlows=["ALLOW_REFRESH_TOKEN_AUTH"],
        )["UserPoolClient"]

        discovery_url = (
            f"https://cognito-idp.{self.region}.amazonaws.com/{pool_id}"
            "/.well-known/openid-configuration"
        )
        client_info = {
            "user_pool_id": pool_id,
            "domain": domain,
            "client_id": client["ClientId"],
            "client_secret": client["ClientSecret"],
            "token_endpoint": f"https://{domain}.auth.{self.region}.amazoncognito.com/oauth2/token",
            "scope": scope,
            "discovery_url": discovery_url,
        }
        print(f"  Cognito user pool: {pool_id}")
        return client_info

    @staticmethod
    def get_access_token(client_info: dict) -> str:
        """Mint a client-credentials access token for calling the gateway."""
        response = requests.post(
            client_info["token_endpoint"],
            data={
                "grant_type": "client_credentials",
                "client_id": client_info["client_id"],
                "client_secret": client_info["client_secret"],
                "scope": client_info["scope"],
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["access_token"]

    # --- IAM ---------------------------------------------------------------

    def create_gateway_role(self, gateway_name: str) -> str:
        """Create the gateway execution role, scoped to OAuth outbound targets."""
        role_name = f"agentcore-{gateway_name}-role"
        assume_role_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                    "Condition": {
                        "StringEquals": {"aws:SourceAccount": self.account_id},
                        "ArnLike": {
                            "aws:SourceArn": f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:*"
                        },
                    },
                }
            ],
        }

        try:
            role = self.iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(assume_role_policy),
            )
            print(f"  Created IAM role: {role_name}")
            time.sleep(10)  # let the role propagate
            return role["Role"]["Arn"]
        except self.iam.exceptions.EntityAlreadyExistsException:
            self.iam.update_assume_role_policy(
                RoleName=role_name, PolicyDocument=json.dumps(assume_role_policy)
            )
            print(f"  IAM role already exists: {role_name} (trust policy refreshed)")
            return self.iam.get_role(RoleName=role_name)["Role"]["Arn"]

    def grant_oauth_permissions(
        self, role_arn: str, policy_name: str, provider_arn: str, secret_arn: str
    ) -> None:
        """Allow the gateway role to fetch the Databricks token and its secret.

        Without this the target still reaches READY, but every tool call fails.
        """
        role_name = role_arn.split("/")[-1]
        policy_doc = json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "bedrock-agentcore:GetWorkloadAccessToken",
                            "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                        ],
                        "Resource": [
                            f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}"
                            ":workload-identity-directory/default",
                            f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}"
                            ":workload-identity-directory/default/workload-identity/*",
                        ],
                    },
                    {
                        # GetResourceOauth2Token is authorized against several
                        # resources in turn — the credential provider, the token
                        # vault that holds it, AND the gateway's workload identity.
                        # Scoping it to the provider alone fails at tool-invocation
                        # time with a 403 from AgentCredentialProvider.
                        "Effect": "Allow",
                        "Action": "bedrock-agentcore:GetResourceOauth2Token",
                        "Resource": [
                            provider_arn,
                            f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}"
                            ":token-vault/default",
                            f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}"
                            ":workload-identity-directory/default",
                            f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}"
                            ":workload-identity-directory/default/workload-identity/*",
                        ],
                    },
                    {
                        "Effect": "Allow",
                        "Action": "secretsmanager:GetSecretValue",
                        "Resource": secret_arn or "*",
                    },
                ],
            }
        )
        self.iam.put_role_policy(
            RoleName=role_name, PolicyName=policy_name, PolicyDocument=policy_doc
        )
        print(f"  Updated role: {role_name}")
        time.sleep(10)

    # --- gateway -----------------------------------------------------------

    def create_mcp_gateway(self, name: str, role_arn: str, client_info: dict) -> dict:
        """Create an MCP gateway with a Cognito CUSTOM_JWT inbound authorizer."""
        gateway = self.client.create_gateway(
            name=name,
            roleArn=role_arn,
            protocolType="MCP",
            description="Databricks Genie exposed as a governed MCP tool",
            protocolConfiguration={
                "mcp": {"supportedVersions": [MCP_PROTOCOL_VERSION]}
            },
            authorizerType="CUSTOM_JWT",
            authorizerConfiguration={
                "customJWTAuthorizer": {
                    "allowedClients": [client_info["client_id"]],
                    "discoveryUrl": client_info["discovery_url"],
                }
            },
            exceptionLevel="DEBUG",
        )
        print(f"  Gateway URL: {gateway['gatewayUrl']}")
        print(f"  Gateway ID:  {gateway['gatewayId']}")
        return gateway
