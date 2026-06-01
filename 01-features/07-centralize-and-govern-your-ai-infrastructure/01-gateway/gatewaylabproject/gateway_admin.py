"""Admin client for AgentCore Gateway control plane operations.

Wraps boto3 bedrock-agentcore-control calls for gateway, target, and
credential provider lifecycle. Used by tutorial scripts when the
AgentCore CLI does not yet support the needed feature (streaming,
sessions, dynamic listing, resource priority, header propagation, etc.).

Usage from scripts:

    from gateway_admin import GatewayBoto3Client

    admin = GatewayBoto3Client()
    gw = admin.create_gateway(
        name="my-gateway",
        authorizer_type="CUSTOM_JWT",
        discovery_url="https://...",
        allowed_clients=["client-id"],
        protocol_config={
            "mcp": {
                "supportedVersions": ["2025-11-25"],
                "streamingConfiguration": {"enableResponseStreaming": True},
            }
        },
    )
    print(gw["gatewayUrl"])
"""

from __future__ import annotations

import json
import time
from typing import Any

import boto3


class GatewayBoto3Client:
    """Thin wrapper around the bedrock-agentcore-control boto3 client."""

    def __init__(self, region: str | None = None):
        self.region = region or boto3.Session().region_name
        self.client = boto3.client("bedrock-agentcore-control", region_name=self.region)
        self.iam = boto3.client("iam")
        self.sts = boto3.client("sts")
        self._account_id: str | None = None

    @property
    def account_id(self) -> str:
        if self._account_id is None:
            self._account_id = self.sts.get_caller_identity()["Account"]
        return self._account_id

    def create_gateway_role(
        self,
        gateway_name: str,
        *,
        oauth_targets: bool = False,
        api_key_targets: bool = False,
        lambda_targets: bool = False,
        s3_schemas: bool = False,
        policy_engine_arn: str | None = None,
    ) -> str:
        """Create a least-privilege IAM role for the gateway.

        Mirrors the CDK L3 construct behavior: starts with the assume-role
        trust policy, then adds only the permissions needed based on the
        target types configured.
        """
        role_name = f"agentcore-{gateway_name}-role"
        gateway_arn = (
            f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:gateway/*"
        )
        identity_arn = f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:workload-identity-directory/default"  # noqa: F841

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
            self.iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(assume_role_policy),
            )
            print(f"  Created IAM role: {role_name}")
            time.sleep(10)
        except self.iam.exceptions.EntityAlreadyExistsException:
            print(f"  IAM role already exists: {role_name}")

        statements: list[dict[str, Any]] = []

        if oauth_targets:
            statements.append(
                {
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:GetResourceOauth2Token",
                        "bedrock-agentcore:GetWorkloadAccessToken",
                        "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                        "secretsmanager:GetSecretValue",
                    ],
                    "Resource": "*",
                }
            )

        if api_key_targets:
            statements.append(
                {
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:GetApiKeyCredential",
                        "bedrock-agentcore:GetResourceApiKey",
                        "secretsmanager:GetSecretValue",
                    ],
                    "Resource": "*",
                }
            )

        if lambda_targets:
            statements.append(
                {
                    "Effect": "Allow",
                    "Action": ["lambda:InvokeFunction"],
                    "Resource": "*",
                }
            )

        if s3_schemas:
            statements.append(
                {
                    "Effect": "Allow",
                    "Action": ["s3:GetObject"],
                    "Resource": "*",
                }
            )

        if policy_engine_arn:
            statements.append(
                {
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:GetPolicyEngine",
                        "bedrock-agentcore:CheckAuthorizePermissions",
                        "bedrock-agentcore:AuthorizeAction",
                        "bedrock-agentcore:PartiallyAuthorizeActions",
                    ],
                    "Resource": [policy_engine_arn, gateway_arn],
                }
            )

        if statements:
            self.iam.put_role_policy(
                RoleName=role_name,
                PolicyName="AgentCorePolicy",
                PolicyDocument=json.dumps(
                    {"Version": "2012-10-17", "Statement": statements}
                ),
            )

        return self.iam.get_role(RoleName=role_name)["Role"]["Arn"]

    def create_gateway(
        self,
        name: str,
        *,
        authorizer_type: str = "NONE",
        discovery_url: str | None = None,
        allowed_clients: list[str] | None = None,
        protocol_config: dict[str, Any] | None = None,
        description: str = "",
        oauth_targets: bool = False,
        api_key_targets: bool = False,
        lambda_targets: bool = False,
        s3_schemas: bool = False,
        policy_engine_arn: str | None = None,
    ) -> dict[str, Any]:
        role_arn = self.create_gateway_role(
            name,
            oauth_targets=oauth_targets,
            api_key_targets=api_key_targets,
            lambda_targets=lambda_targets,
            s3_schemas=s3_schemas,
            policy_engine_arn=policy_engine_arn,
        )

        kwargs: dict[str, Any] = {
            "name": name,
            "roleArn": role_arn,
            "protocolType": "MCP",
            "description": description,
        }

        if protocol_config:
            kwargs["protocolConfiguration"] = protocol_config
        else:
            kwargs["protocolConfiguration"] = {
                "mcp": {"supportedVersions": ["2025-11-25"]}
            }

        kwargs["exceptionLevel"] = "DEBUG"

        kwargs["authorizerType"] = authorizer_type
        if authorizer_type == "CUSTOM_JWT" and discovery_url:
            kwargs["authorizerConfiguration"] = {
                "customJWTAuthorizer": {
                    "allowedClients": allowed_clients or [],
                    "discoveryUrl": discovery_url,
                }
            }

        response = self.client.create_gateway(**kwargs)
        print(f"  Created gateway: {name}")
        print(f"    ID:  {response['gatewayId']}")
        print(f"    URL: {response['gatewayUrl']}")
        return response

    def create_target(
        self,
        gateway_id: str,
        name: str,
        endpoint: str,
        *,
        credential_provider_arn: str | None = None,
        scopes: list[str] | None = None,
        resource_priority: int | None = None,
        listing_mode: str | None = None,
        metadata_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        mcp_server_config: dict[str, Any] = {"endpoint": endpoint}
        if resource_priority is not None:
            mcp_server_config["resourcePriority"] = resource_priority
        if listing_mode:
            mcp_server_config["listingMode"] = listing_mode

        kwargs: dict[str, Any] = {
            "name": name,
            "gatewayIdentifier": gateway_id,
            "targetConfiguration": {"mcp": {"mcpServer": mcp_server_config}},
        }

        if credential_provider_arn:
            kwargs["credentialProviderConfigurations"] = [
                {
                    "credentialProviderType": "OAUTH",
                    "credentialProvider": {
                        "oauthCredentialProvider": {
                            "providerArn": credential_provider_arn,
                            "scopes": scopes or [],
                        }
                    },
                },
            ]

        if metadata_config:
            kwargs["metadataConfiguration"] = metadata_config

        response = self.client.create_gateway_target(**kwargs)
        print(f"  Created target: {name} (ID: {response['targetId']})")
        return response

    def create_credential_provider(
        self,
        name: str,
        discovery_url: str,
        client_id: str,
        client_secret: str,
    ) -> dict[str, Any]:
        response = self.client.create_oauth2_credential_provider(
            name=name,
            credentialProviderVendor="CustomOauth2",
            oauth2ProviderConfigInput={
                "customOauth2ProviderConfig": {
                    "oauthDiscovery": {"discoveryUrl": discovery_url},
                    "clientId": client_id,
                    "clientSecret": client_secret,
                }
            },
        )
        print(f"  Created credential provider: {name}")
        return response

    def delete_gateway(self, gateway_id: str) -> None:
        targets = self.client.list_gateway_targets(
            gatewayIdentifier=gateway_id, maxResults=20
        )
        for item in targets.get("items", []):
            target_id = item["targetId"]
            print(f"  Deleting target: {target_id}")
            self.client.delete_gateway_target(
                gatewayIdentifier=gateway_id, targetId=target_id
            )
            time.sleep(5)
        print(f"  Deleting gateway: {gateway_id}")
        self.client.delete_gateway(gatewayIdentifier=gateway_id)

    def delete_credential_provider(self, name: str) -> None:
        try:
            self.client.delete_oauth2_credential_provider(name=name)
            print(f"  Deleted credential provider: {name}")
        except Exception as e:
            print(f"  Could not delete credential provider {name}: {e}")

    def delete_gateway_role(self, gateway_name: str) -> None:
        role_name = f"agentcore-{gateway_name}-role"
        try:
            for p in self.iam.list_attached_role_policies(RoleName=role_name)[
                "AttachedPolicies"
            ]:
                self.iam.detach_role_policy(
                    RoleName=role_name, PolicyArn=p["PolicyArn"]
                )
            for name in self.iam.list_role_policies(RoleName=role_name)["PolicyNames"]:
                self.iam.delete_role_policy(RoleName=role_name, PolicyName=name)
            self.iam.delete_role(RoleName=role_name)
            print(f"  Deleted IAM role: {role_name}")
        except self.iam.exceptions.NoSuchEntityException:
            print(f"  IAM role not found: {role_name}")

    def synchronize_targets(
        self, gateway_id: str, target_ids: list[str]
    ) -> dict[str, Any]:
        response = self.client.synchronize_gateway_targets(
            gatewayIdentifier=gateway_id,
            targetIdList=target_ids,
        )
        print(f"  Synchronized {len(target_ids)} target(s)")
        return response

    def update_target(
        self,
        gateway_id: str,
        target_id: str,
        name: str,
        endpoint: str,
        *,
        credential_provider_arn: str | None = None,
        scopes: list[str] | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "gatewayIdentifier": gateway_id,
            "targetId": target_id,
            "name": name,
            "targetConfiguration": {"mcp": {"mcpServer": {"endpoint": endpoint}}},
        }
        if credential_provider_arn:
            kwargs["credentialProviderConfigurations"] = [
                {
                    "credentialProviderType": "OAUTH",
                    "credentialProvider": {
                        "oauthCredentialProvider": {
                            "providerArn": credential_provider_arn,
                            "scopes": scopes or [],
                        }
                    },
                },
            ]
        response = self.client.update_gateway_target(**kwargs)
        print(f"  Updated target: {name}")
        return response
