#!/usr/bin/env python3

import boto3
import json
import sys
import subprocess
from utils import get_token, load_config


def main():
    if len(sys.argv) < 2:
        print("Usage: python invoke_with_token.py '<prompt>'")
        print("Example: python invoke_with_token.py 'Hello'")
        sys.exit(1)
    
    prompt = sys.argv[1]
    
    # Load config
    config_data = load_config('config.yaml')
    if not config_data:
        print("❌ Failed to load config.yaml")
        sys.exit(1)
    
    # Get IDP setup from config
    idp_setup = config_data.get('idp_setup', {})
    user_pool_id = idp_setup.get('user_pool_id')
    client_id = idp_setup.get('client_id')
    client_secret = idp_setup.get('client_secret')
    
    if not all([user_pool_id, client_id, client_secret]):
        print("❌ Missing IDP configuration in config.yaml")
        sys.exit(1)
    
    # Define scope for monitoring agent gateway
    scope_string = "operations-agentcore-gateway-id/gateway:read operations-agentcore-gateway-id/gateway:write"
    
    print("🔐 Getting OAuth token...")
    
    # Get token
    token_response = get_token(user_pool_id, client_id, client_secret, scope_string, boto3.session.Session().region_name)
    
    if "error" in token_response:
        print(f"❌ Token request failed: {token_response['error']}")
        sys.exit(1)
    
    if "access_token" not in token_response:
        print(f"❌ No access_token in response: {token_response}")
        sys.exit(1)
    
    access_token = token_response["access_token"]
    print("✅ Successfully obtained access token")
    
    # Create payload
    payload = {"prompt": prompt}
    payload_json = json.dumps(payload)
    
    # Build agentcore command with bearer token
    cmd = [
        "agentcore", "invoke",
        "--bearer-token", access_token,
        payload_json
    ]
    
    print(f"🚀 Invoking agent with prompt: {prompt}")
    
    # Execute command
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("✅ Invocation successful!")
        print("\n" + "="*50)
        print("RESPONSE:")
        print("="*50)
        print(result.stdout)
        if result.stderr:
            print("\n" + "="*50)
            print("STDERR:")
            print("="*50)
            print(result.stderr)
    except subprocess.CalledProcessError as e:
        print(f"❌ Invocation failed with exit code {e.returncode}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error running command: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()