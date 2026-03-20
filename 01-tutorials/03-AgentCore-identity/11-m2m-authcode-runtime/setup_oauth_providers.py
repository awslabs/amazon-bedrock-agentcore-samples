"""
Setup script: Creates AgentCore Identity credential providers for:
  1. M2M (machine-to-machine): OAuth2 client credentials grant
  2. Auth Code (3LO): Authorization code grant (Google Calendar example)

The M2M provider can be created with the CLI:
    agentcore add identity --name M2MProvider --type oauth ...

The 3LO Google provider requires the bedrock_agentcore SDK (vendor-specific config).
This script creates both programmatically for convenience.

Usage:
    python setup_oauth_providers.py

Prerequisites:
    - For M2M:  Any OAuth2 server supporting client_credentials grant
    - For 3LO:  A Google Cloud project with Calendar API enabled and
                OAuth 2.0 credentials (Web application type).
                See README.md Step 4 for Google setup instructions.

Environment variables (or .env file):
    M2M_CLIENT_ID       OAuth2 client ID for M2M service account
    M2M_CLIENT_SECRET   OAuth2 client secret for M2M service account
    M2M_DISCOVERY_URL   OIDC discovery URL of the M2M authorization server
    GOOGLE_CLIENT_ID    Google OAuth2 client ID
    GOOGLE_CLIENT_SECRET Google OAuth2 client secret

Outputs:
    oauth_config.json   Provider names and callback URLs
"""

import os
import json
import boto3
from boto3.session import Session

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass  # python-dotenv is optional

try:
    from bedrock_agentcore.services.identity import IdentityClient
except ImportError:
    raise SystemExit(
        "bedrock-agentcore package not found.\n"
        "Install it with: pip install -r requirements.txt"
    )


def create_m2m_provider(identity_client: IdentityClient, region: str) -> dict:
    """
    Create a credential provider for M2M (client credentials) flow.

    This can also be created with the CLI:
        agentcore add identity \\
          --name M2MProvider \\
          --type oauth \\
          --discovery-url $M2M_DISCOVERY_URL \\
          --client-id $M2M_CLIENT_ID \\
          --client-secret $M2M_CLIENT_SECRET \\
          --scopes api:read,api:write
    """
    client_id = os.environ.get("M2M_CLIENT_ID", "")
    client_secret = os.environ.get("M2M_CLIENT_SECRET", "")
    discovery_url = os.environ.get("M2M_DISCOVERY_URL", "")

    if not all([client_id, client_secret, discovery_url]):
        print("  Skipping M2M provider (M2M_CLIENT_ID/SECRET/DISCOVERY_URL not set).")
        print("  Create it manually with:")
        print("    agentcore add identity --name M2MProvider --type oauth \\")
        print("      --discovery-url YOUR_DISCOVERY_URL \\")
        print("      --client-id YOUR_CLIENT_ID \\")
        print("      --client-secret YOUR_CLIENT_SECRET")
        return {"name": "M2MProvider", "skipped": True}

    print("Creating M2M (client credentials) credential provider...")
    provider = identity_client.create_oauth2_credential_provider(
        name="M2MProvider",
        credentialProviderVendor="CustomOauth2",
        oauth2ProviderConfigInput={
            "customOauth2ProviderConfig": {
                "clientId": client_id,
                "clientSecret": client_secret,
                "authorizationServerMetadata": {
                    "issuer": discovery_url.replace(
                        "/.well-known/openid-configuration", ""
                    )
                },
            }
        },
    )
    print(f"  Created: {provider.get('name')}")
    return {"name": "M2MProvider", "provider": provider}


def create_google_3lo_provider(identity_client: IdentityClient) -> dict:
    """
    Create a credential provider for Google OAuth2 3-legged (auth code) flow.

    AgentCore Identity handles:
    - Generating the authorization URL for user consent
    - Exchanging the auth code for tokens
    - Storing and refreshing tokens securely
    - Session binding to prevent CSRF
    """
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")

    if not all([client_id, client_secret]):
        print("  Skipping Google 3LO provider (GOOGLE_CLIENT_ID/SECRET not set).")
        print("  Set them in a .env file and re-run this script.")
        return {"name": "Google3LOProvider", "skipped": True}

    print("Creating Google OAuth2 (authorization code / 3LO) credential provider...")
    provider = identity_client.create_oauth2_credential_provider(
        name="Google3LOProvider",
        credentialProviderVendor="GoogleOauth2",
        oauth2ProviderConfigInput={
            "googleOauth2ProviderConfig": {
                "clientId": client_id,
                "clientSecret": client_secret,
            }
        },
    )
    callback_url = provider.get("callbackUrl", "")
    print(f"  Created: {provider.get('name')}")
    print(f"\n  IMPORTANT: Register this callback URL in Google Cloud Console:")
    print(f"  Callback URL: {callback_url}")
    print(f"  (APIs & Services > Credentials > OAuth 2.0 Client IDs > Authorised redirect URIs)")

    return {"name": "Google3LOProvider", "callback_url": callback_url, "provider": provider}


def main():
    session = Session()
    region = session.region_name
    identity_client = IdentityClient(region=region)

    results = {}

    print("=== M2M Credential Provider ===")
    results["m2m"] = create_m2m_provider(identity_client, region)

    print("\n=== Google 3LO Credential Provider ===")
    results["google_3lo"] = create_google_3lo_provider(identity_client)

    with open("oauth_config.json", "w") as f:
        # Only save non-sensitive metadata
        json.dump(
            {
                "m2m_provider_name": results["m2m"]["name"],
                "google_3lo_provider_name": results["google_3lo"]["name"],
                "google_callback_url": results["google_3lo"].get("callback_url", ""),
            },
            f,
            indent=2,
        )

    print("\nOAuth provider configuration saved to oauth_config.json")


if __name__ == "__main__":
    main()
