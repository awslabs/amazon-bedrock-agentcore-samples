"""Create GitHub OAuth2 credential provider.

Creates the credential provider and outputs the callback URL
that must be registered with your GitHub OAuth App.

Requires GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET in environment.

Usage:
    uv run python scripts/github-auth-code/deploy_credential.py
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

    github_client_id = get_required_env("GITHUB_CLIENT_ID")
    github_client_secret = get_required_env("GITHUB_CLIENT_SECRET")

    region = boto3.Session().region_name
    client = boto3.client("bedrock-agentcore-control", region_name=region)

    print("--- Creating GitHub OAuth2 credential provider ---")
    response = client.create_oauth2_credential_provider(
        name="github-oauth-credential",
        credentialProviderVendor="GithubOauth2",
        oauth2ProviderConfigInput={
            "githubOauth2ProviderConfig": {
                "clientId": github_client_id,
                "clientSecret": github_client_secret,
            }
        },
    )
    cred_provider_arn = response["credentialProviderArn"]
    identity_callback = response["callbackUrl"]

    print(f"  Credential ARN: {cred_provider_arn}")
    print(f"  Callback URL:   {identity_callback}")
    print()
    print("  *** ACTION REQUIRED ***")
    print("  Go to https://github.com/settings/apps and update your GitHub App's")
    print(f"  'Authorization callback URL' to:\n\n    {identity_callback}\n")

    env_path = os.path.join(os.path.dirname(__file__), ".env")
    env_vars: dict[str, str] = {}
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    env_vars[key] = value
    env_vars["CRED_PROVIDER_ARN"] = cred_provider_arn
    env_vars["CALLBACK_URL"] = identity_callback
    with open(env_path, "w") as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    print("  Saved to .env")


if __name__ == "__main__":
    main()
