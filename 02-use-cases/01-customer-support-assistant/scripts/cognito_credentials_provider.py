from bedrock_agentcore.services.identity import IdentityClient
from utils import get_ssm_parameter, read_config, get_aws_region
import json

print("🔧 Reading gateway configuration...")
gateway_config = read_config("gateway.config")
print("✅ Gateway configuration loaded.")

print("🔐 Initializing IdentityClient...")
identity_client = IdentityClient(region=get_aws_region())

# Fetch parameters
print("📥 Fetching Cognito client ID from SSM...")
client_id = get_ssm_parameter("/app/customersupport/agentcore/machine_client_id")
print(f"✅ Retrieved client ID: {client_id}")

print("📥 Reading Cognito client secret from config...")
client_secret = gateway_config["cognito"]["secret"]
print(f"✅ Retrieved client secret: {client_secret[:4]}***")  # Masked for safety

print("🌐 Fetching OAuth2 discovery URLs from SSM...")
issuer = get_ssm_parameter("/app/customersupport/agentcore/cognito_discovery_url")
auth_url = get_ssm_parameter("/app/customersupport/agentcore/cognito_auth_url")
token_url = get_ssm_parameter("/app/customersupport/agentcore/cognito_token_url")

print(f"✅ Issuer: {issuer}")
print(f"✅ Authorization Endpoint: {auth_url}")
print(f"✅ Token Endpoint: {token_url}")

# Configure Cognito OAuth2 Provider - 2LO Example
print("⚙️ Creating OAuth2 credential provider...")
cognito_provider = identity_client.create_oauth2_credential_provider(
    {
        "name": "customersupport-gateways",
        "credentialProviderVendor": "CustomOauth2",
        "oauth2ProviderConfigInput": {
            "customOauth2ProviderConfig": {
                "clientId": client_id,
                "clientSecret": client_secret,
                "oauthDiscovery": {
                    "authorizationServerMetadata": {
                        "issuer": issuer,
                        "authorizationEndpoint": auth_url,
                        "tokenEndpoint": token_url,
                        "responseTypes": ["code", "token"],
                    }
                },
            }
        },
    }
)
print("✅ OAuth2 credential provider created successfully:")
print(json.dumps(cognito_provider, indent=2))
