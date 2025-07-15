import json
import os
import sys
from bedrock_agentcore.services.identity import IdentityClient
from utils import get_aws_region

CREDENTIALS_FILE = "credentials.json"

# ----- 1. Check and Read credentials.json -----
if not os.path.isfile(CREDENTIALS_FILE):
    print(f"❌ Error: '{CREDENTIALS_FILE}' file not found.")
    sys.exit(1)

print(f"📄 Reading credentials from {CREDENTIALS_FILE}...")
with open(CREDENTIALS_FILE, "r") as f:
    try:
        data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing JSON: {e}")
        sys.exit(1)

web_config = data.get("web")
if not web_config:
    print("❌ Error: 'web' section missing in credentials.json.")
    sys.exit(1)

client_id = web_config.get("client_id")
client_secret = web_config.get("client_secret")

if not client_id:
    print("❌ Error: 'client_id' not found in credentials.json.")
    sys.exit(1)

if not client_secret:
    print("❌ Error: 'client_secret' not found in credentials.json.")
    sys.exit(1)

print("✅ Client ID and Secret loaded from credentials.json.")

# ----- 2. Initialize IdentityClient -----
region = get_aws_region()
print(f"🌎 Using AWS region: {region}")
identity_client = IdentityClient(region)

# ----- 3. Create OAuth2 Credential Provider -----
print("🔧 Creating Google OAuth2 credential provider...")
cognito_provider = identity_client.create_oauth2_credential_provider(
    {
        "name": "customersupports-google-calendar",
        "credentialProviderVendor": "GoogleOauth2",
        "oauth2ProviderConfigInput": {
            "googleOauth2ProviderConfig": {
                "clientId": client_id,
                "clientSecret": client_secret,
            }
        },
    }
)

print("✅ Google OAuth2 credential provider created successfully:")
print(json.dumps(cognito_provider, indent=2))
