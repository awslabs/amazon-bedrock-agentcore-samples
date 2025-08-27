import os
import boto3
import requests
import json
from dotenv import load_dotenv
from bedrock_agentcore.identity.auth import requires_access_token

load_dotenv()

def get_cognito_token_direct():
    """
    Direct Cognito token retrieval for container runtime fallback
    """
    try:
        # Get Cognito configuration from environment
        cognito_domain = os.getenv("COGNITO_DOMAIN")
        client_id = os.getenv("COGNITO_CLIENT_ID")
        client_secret = os.getenv("COGNITO_CLIENT_SECRET")
        
        print(f"Debug - Cognito Domain: {cognito_domain}")
        print(f"Debug - Client ID: {client_id}")
        print(f"Debug - Client Secret: {'***' if client_secret else 'None'}")
        
        if not all([cognito_domain, client_id, client_secret]):
            missing = []
            if not cognito_domain: missing.append("COGNITO_DOMAIN")
            if not client_id: missing.append("COGNITO_CLIENT_ID")
            if not client_secret: missing.append("COGNITO_CLIENT_SECRET")
            raise ValueError(f"Missing Cognito configuration: {', '.join(missing)}")
        
        # Prepare token request
        token_url = f"{cognito_domain}/oauth2/token"
        print(f"Debug - Token URL: {token_url}")
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = {
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret,
            'scope': 'device-management-oauth/invoke'
        }
        
        print("Debug - Making token request...")
        # Make token request
        response = requests.post(token_url, headers=headers, data=data)
        print(f"Debug - Response status: {response.status_code}")
        print(f"Debug - Response headers: {dict(response.headers)}")
        
        if response.status_code != 200:
            print(f"Debug - Response text: {response.text}")
            response.raise_for_status()
        
        token_data = response.json()
        print(f"Debug - Token data keys: {list(token_data.keys())}")
        access_token = token_data.get('access_token')
        print(f"Debug - Access token received: {'Yes' if access_token else 'No'}")
        return access_token
        
    except Exception as e:
        print(f"Error getting Cognito token directly: {e}")
        import traceback
        traceback.print_exc()
        return None

@requires_access_token(
    provider_name="vgs-identity-provider",
    scopes=[],
    auth_flow="M2M",
)
def get_gateway_access_token_bedrock(access_token: str):
    """
    Bedrock AgentCore token retrieval (works when workload identity is set)
    """
    print(f"Access Token from Bedrock AgentCore: {access_token}")
    return access_token

def get_gateway_access_token():
    """
    Main function that tries bedrock_agentcore first, then falls back to direct Cognito
    """
    try:
        # Try bedrock_agentcore method first
        print("Trying bedrock_agentcore authentication...")
        return get_gateway_access_token_bedrock()
    except ValueError as e:
        if "Workload access token has not been set" in str(e):
            print("Workload access token not available, falling back to direct Cognito authentication...")
            # Fall back to direct Cognito token retrieval
            token = get_cognito_token_direct()
            if token:
                print("Successfully obtained token via direct Cognito authentication")
                return token
            else:
                raise Exception("Failed to obtain token via both bedrock_agentcore and direct Cognito methods")
        else:
            raise e
    except Exception as e:
        print(f"Error with bedrock_agentcore authentication: {e}")
        print("Falling back to direct Cognito authentication...")
        # Fall back to direct Cognito token retrieval
        token = get_cognito_token_direct()
        if token:
            print("Successfully obtained token via direct Cognito authentication")
            return token
        else:
            raise Exception("Failed to obtain token via both bedrock_agentcore and direct Cognito methods")

if __name__ == "__main__":
    token = get_gateway_access_token()
    print(f"Final token: {token}")