"""Create the AgentCore Gateway and register Databricks Genie as an MCP target.

Steps performed:
    1. Verify AWS credentials
    2. Create the gateway with a Cognito authorizer (inbound auth)
    3. Create the Databricks OAuth2 M2M credential provider (outbound auth)
    4. Grant the gateway role permission to use that provider
    5. Register the Databricks-managed Genie MCP endpoint as a gateway target
    6. Wait for the target and synchronize the tool surface
    7. Write gateway_config.json for invoke.py / genie_agent.py / cleanup.py

Usage:
    python deploy.py
"""

import json
import time

import boto3
from config import (
    AWS_REGION,
    CREDENTIAL_PROVIDER_NAME,
    DATABRICKS_CLIENT_ID,
    DATABRICKS_CLIENT_SECRET,
    DATABRICKS_HOST,
    GATEWAY_NAME,
    GENIE_SPACE_ID,
    IAM_POLICY_NAME,
    STATE_FILE,
    TARGET_NAME,
    genie_mcp_url,
    require_databricks_config,
)
from gateway_setup import GatewaySetup


def banner(step: str) -> None:
    print("=" * 60)
    print(step)
    print("=" * 60)


def create_gateway(setup: GatewaySetup) -> dict:
    """Create the Cognito authorizer, the IAM role and the MCP gateway."""
    print("Creating Cognito authorizer (inbound auth)...")
    client_info = setup.create_cognito_authorizer(GATEWAY_NAME)

    print("Creating gateway execution role...")
    role_arn = setup.create_gateway_role(GATEWAY_NAME)

    print("Creating gateway...")
    gateway = setup.create_mcp_gateway(GATEWAY_NAME, role_arn, client_info)
    print("  Waiting 30s for IAM propagation...")
    time.sleep(30)
    return {"gateway": gateway, "client_info": client_info, "role_arn": role_arn}


def create_credential_provider(agentcore) -> tuple:
    """Register Databricks OAuth2 client-credentials as an outbound provider."""
    token_endpoint = f"{DATABRICKS_HOST}/oidc/v1/token"

    print("Creating Databricks OAuth2 credential provider...")
    provider = agentcore.create_oauth2_credential_provider(
        name=CREDENTIAL_PROVIDER_NAME,
        credentialProviderVendor="CustomOauth2",
        oauth2ProviderConfigInput={
            "customOauth2ProviderConfig": {
                "oauthDiscovery": {
                    "authorizationServerMetadata": {
                        "issuer": DATABRICKS_HOST,
                        "tokenEndpoint": token_endpoint,
                        "authorizationEndpoint": token_endpoint,
                    }
                },
                "clientId": DATABRICKS_CLIENT_ID,
                "clientSecret": DATABRICKS_CLIENT_SECRET,
            }
        },
    )
    provider_arn = provider["credentialProviderArn"]
    secret_arn = provider.get("secretArn") or provider.get("clientSecretArn", {}).get("secretArn", "")
    print(f"  Credential provider ARN: {provider_arn}")
    return provider_arn, secret_arn


def grant_gateway_permissions(setup: GatewaySetup, role_arn: str, provider_arn: str, secret_arn: str) -> None:
    """Allow the gateway role to mint workload tokens and read the DB secret."""
    print("Updating gateway role permissions...")
    setup.grant_oauth_permissions(role_arn, IAM_POLICY_NAME, provider_arn, secret_arn)


def register_genie_target(agentcore, gateway_id: str, provider_arn: str) -> str:
    """Register the Databricks-managed Genie MCP server as a gateway target."""
    mcp_url = genie_mcp_url()
    print(f"Registering Genie MCP target: {mcp_url}")

    target = agentcore.create_gateway_target(
        gatewayIdentifier=gateway_id,
        name=TARGET_NAME,
        description=f"Databricks Genie space {GENIE_SPACE_ID} as MCP tool",
        targetConfiguration={"mcp": {"mcpServer": {"endpoint": mcp_url}}},
        credentialProviderConfigurations=[
            {
                "credentialProviderType": "OAUTH",
                "credentialProvider": {
                    "oauthCredentialProvider": {
                        "providerArn": provider_arn,
                        "grantType": "CLIENT_CREDENTIALS",
                        # Scope the token to Genie only, not all-apis.
                        "scopes": ["genie"],
                    }
                },
            }
        ],
    )
    target_id = target["targetId"]
    print(f"  Target ID: {target_id}")

    # The API reports status in upper case (CREATING / READY / FAILED), so
    # compare case-insensitively — SynchronizeGatewayTargets rejects a target
    # that is still CREATING.
    print("Waiting for target to be ready...")
    status = ""
    for _ in range(60):
        status = agentcore.get_gateway_target(gatewayIdentifier=gateway_id, targetId=target_id).get("status") or ""
        if status.upper() not in ("CREATING", "UPDATING", "SYNCHRONIZING"):
            break
        time.sleep(5)
    print(f"  Target status: {status}")

    if status.upper() != "READY":
        raise SystemExit(
            f"Target did not reach READY (status: {status}). Check the gateway "
            "role permissions from step 4 and the Databricks service principal "
            "credentials, then re-run."
        )

    print("Synchronizing tools from Databricks...")
    agentcore.synchronize_gateway_targets(gatewayIdentifier=gateway_id, targetIdList=[target_id])
    print("  Tools synchronized.")
    return target_id


def deploy() -> None:
    require_databricks_config()

    banner("STEP 1: Verify AWS Credentials")
    identity = boto3.client("sts").get_caller_identity()
    print(f"  Account: {identity['Account']}")
    print(f"  ARN:     {identity['Arn']}")
    print(f"  Region:  {AWS_REGION}")

    setup = GatewaySetup(AWS_REGION)
    agentcore = setup.client

    banner("STEP 2: Create AgentCore Gateway")
    created = create_gateway(setup)
    gateway = created["gateway"]
    gateway_id = gateway["gatewayId"]

    banner("STEP 3: Create Databricks OAuth2 Credential Provider")
    provider_arn, secret_arn = create_credential_provider(agentcore)

    banner("STEP 4: Grant Gateway Role Permissions")
    grant_gateway_permissions(setup, created["role_arn"], provider_arn, secret_arn)

    banner("STEP 5: Register Databricks Genie MCP Target")
    target_id = register_genie_target(agentcore, gateway_id, provider_arn)

    banner("STEP 6: Save Configuration")
    config = {
        "gateway_id": gateway_id,
        "gateway_url": gateway["gatewayUrl"],
        "target_id": target_id,
        "provider_arn": provider_arn,
        "genie_space_id": GENIE_SPACE_ID,
        "region": AWS_REGION,
        # Cognito inbound-auth client; mints the gateway bearer token.
        "client_info": created["client_info"],
        "role_arn": created["role_arn"],
        "databricks_host": DATABRICKS_HOST,
    }
    with open(STATE_FILE, "w") as f:
        json.dump(config, f, indent=2)
    print(f"  Wrote {STATE_FILE}")

    print()
    print("Deployment complete. Next: python invoke.py")


if __name__ == "__main__":
    deploy()
