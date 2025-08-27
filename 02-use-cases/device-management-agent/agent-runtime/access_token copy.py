import os
from dotenv import load_dotenv
from bedrock_agentcore.identity.auth import requires_access_token

load_dotenv()

@requires_access_token(
    provider_name="vgs-identity-provider",
    scopes=[],
    auth_flow="M2M",
 )

def get_gateway_access_token(access_token: str):
    print(f"Access Token: {access_token}")
    return access_token

if __name__ == "__main__":
    get_gateway_access_token()