"""Create GitHub MCP Server target with implicit sync (Method 1).

Admin must complete the authorization code flow during target creation.
The script opens the authorization URL and waits for session binding.

Requires GATEWAY_ID, CRED_PROVIDER_ARN in environment or .env.

Usage:
    uv run python scripts/github-auth-code/deploy_target_implicit.py
"""

import os
import sys
import time

import boto3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

AUTH_CODE_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "..",
        "01-attach-targets",
        "mcp",
        "mcp-servers",
        "01-configure-auth",
        "authorization-code-flow",
    )
)
sys.path.insert(0, os.path.join(AUTH_CODE_DIR, "utils"))


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

    print("--- Creating GitHub target (Method 1: implicit sync) ---")
    print("  This requires you to authorize in your browser.\n")

    target_response = client.create_gateway_target(
        gatewayIdentifier=gateway_id,
        name="github-mcp-server-implicit",
        description="GitHub MCP Server with authorization code flow - implicit sync",
        targetConfiguration={
            "mcp": {"mcpServer": {"endpoint": "https://api.githubcopilot.com/mcp"}}
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
    auth_url = target_response["authorizationData"]["oauth2"]["authorizationUrl"]
    user_id = target_response["authorizationData"]["oauth2"]["userId"]

    print(f"  Target ID: {target_id}")
    print(f"  Status: {target_response['status']} (Needs Authorization)")
    print("\n  Start the callback server in another terminal:")
    print(  # lgtm[py/clear-text-logging-sensitive-data]
        f"  uv run python scripts/github-auth-code/callback_server.py"  # codeql[py/clear-text-logging-sensitive-data]
        f' --user-id "{user_id}"'
        f' --auth-url "{auth_url}"'
    )
    print("\n  After authorizing, the target will become READY.")

    # Wait for target to become READY
    print("\n  Waiting for target to become READY...")
    for _ in range(12):
        time.sleep(10)
        tgt = client.get_gateway_target(
            gatewayIdentifier=gateway_id, targetId=target_id
        )
        status = tgt["status"]
        print(f"    Status: {status}")
        if status in ["READY", "FAILED", "UPDATE_UNSUCCESSFUL"]:
            break

    env_path = os.path.join(os.path.dirname(__file__), ".env")
    env_vars: dict[str, str] = {}
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    env_vars[key] = value
    env_vars["IMPLICIT_TARGET_ID"] = target_id
    with open(env_path, "w") as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    print("  Saved to .env")


if __name__ == "__main__":
    main()
