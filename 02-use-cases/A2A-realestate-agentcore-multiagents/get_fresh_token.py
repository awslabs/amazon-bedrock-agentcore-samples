#!/usr/bin/env python3
"""Get fresh OAuth token from Cognito using client credentials flow."""

import requests
import json
import sys
from datetime import datetime, timedelta
import base64
import boto3


def generate_fresh_token(deployment_info_path='deployment_info.json'):
    """
    Generate a fresh OAuth token from Cognito.
    
    Args:
        deployment_info_path: Path to deployment_info.json file
        
    Returns:
        tuple: (access_token, expires_at) or (None, None) on error
    """
    # Load config from deployment_info.json
    with open(deployment_info_path, 'r', encoding='utf-8') as f:
        deployment_info = json.load(f)
        cognito_config = deployment_info['cognito_config']

    client_id = cognito_config['client_id']
    user_pool_id = cognito_config['user_pool_id']

    # Get client secret from AWS
    cognito_client = boto3.client('cognito-idp', region_name='us-east-1')

    try:
        # Get client secret
        client_response = cognito_client.describe_user_pool_client(
            UserPoolId=user_pool_id,
            ClientId=client_id
        )
        client_secret = client_response['UserPoolClient']['ClientSecret']
        
        # Get domain
        pool_response = cognito_client.describe_user_pool(UserPoolId=user_pool_id)
        domain = pool_response['UserPool'].get('Domain')
        
        if not domain:
            print("✗ No domain configured for user pool")
            return None, None
        
        region = user_pool_id.split('_')[0]
        token_endpoint = f"https://{domain}.auth.{region}.amazoncognito.com/oauth2/token"
        
        # Create Basic Auth header
        auth_string = f"{client_id}:{client_secret}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        # Request token using client credentials flow
        response = requests.post(
            token_endpoint,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Authorization': f'Basic {auth_b64}'
            },
            data={
                'grant_type': 'client_credentials',
                'scope': 'a2a-agents/invoke'
            },
            timeout=30
        )
        
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data['access_token']
            expires_in = token_data['expires_in']
            
            # Calculate expiration time
            expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            # Save to files
            with open('.bearer_token', 'w', encoding='utf-8') as f:
                f.write(access_token)
            
            with open('bearer_token.json', 'w', encoding='utf-8') as f:
                json.dump({
                    'access_token': access_token,
                    'token_type': token_data['token_type'],
                    'expires_in': expires_in,
                    'expires_at': expires_at.isoformat()
                }, f, indent=2)
            
            return access_token, expires_at
            
        else:
            print(f"✗ Error: {response.status_code}")
            print(response.text)
            return None, None
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def main():
    """Main entry point for command-line usage."""
    access_token, expires_at = generate_fresh_token()
    
    if access_token:
        print(f"✅ Token generated successfully!")
        print(f"Expires at: {expires_at}")
        print(f"Token (first 50 chars): {access_token[:50]}...")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
