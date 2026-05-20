"""Create GitHub MCP Server target with schema upfront (Method 2).

No interactive authorization needed during creation. Users will be
prompted to authorize on first tool invocation.

Requires GATEWAY_ID, CRED_PROVIDER_ARN in environment or .env.

Usage:
    uv run python scripts/github-auth-code/deploy_target_schema.py
"""

import os
import sys

import boto3


def load_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key, value)


def get_required_env(key):
    val = os.environ.get(key)
    if not val:
        print(f"ERROR: {key} not set. Export it or add to the script .env")
        sys.exit(1)
    return val


def main():
    load_env()

    gateway_id = get_required_env("GATEWAY_ID")
    cred_provider_arn = get_required_env("CRED_PROVIDER_ARN")

    region = boto3.Session().region_name
    client = boto3.client("bedrock-agentcore-control", region_name=region)

    schema_path = os.path.join(os.path.dirname(__file__), "github-tools.json")
    with open(schema_path) as f:
        tool_schema = f.read()

    print("--- Creating GitHub target (Method 2: schema upfront) ---")
    print("  No browser authorization needed during creation.\n")

    target_response = client.create_gateway_target(
        gatewayIdentifier=gateway_id,
        name="github-mcp-server-schema-target",
        description="GitHub MCP Server with authorization code flow - schema upfront",
        targetConfiguration={
            "mcp": {
                "mcpServer": {
                    "endpoint": "https://api.githubcopilot.com/mcp",
                    "mcpToolSchema": {"inlinePayload": tool_schema},
                }
            }
        },
        credentialProviderConfigurations=[
            {
                "credentialProviderType": "OAUTH",
                "credentialProvider": {
                    "oauthCredentialProvider": {
                        "providerArn": cred_provider_arn,
                        "grantType": "AUTHORIZATION_CODE",
                        "defaultReturnUrl": "http://localhost:8080/callback",
                        "scopes": ["repo", "user", "workflow"],
                    }
                },
            }
        ],
    )

    target_id = target_response["targetId"]
    print(f"  Target ID: {target_id}")
    print(f"  Status: {target_response['status']}")
    print("  Users will be prompted to authorize GitHub on first tool invocation.")

    env_path = os.path.join(os.path.dirname(__file__), ".env")
    env_vars: dict[str, str] = {}
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    env_vars[key] = value
    env_vars["SCHEMA_TARGET_ID"] = target_id
    with open(env_path, "w") as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    print("  Saved to .env")


if __name__ == "__main__":
    main()
