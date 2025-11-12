#!/usr/bin/env python3
"""Get fresh OAuth token from Cognito using client credentials flow."""

import requests
import json
from datetime import datetime, timedelta
import base64

# Load config from deployment_info.json
with open('deployment_info.json', 'r') as f:
    deployment_info = json.load(f)
    cognito_config = deployment_info['cognito_config']

client_id = cognito_config['client_id']
user_pool_id = cognito_config['user_pool_id']

# Get client secret from AWS
import boto3
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
        exit(1)
    
    region = user_pool_id.split('_')[0]
    token_endpoint = f"https://{domain}.auth.{region}.amazoncognito.com/oauth2/token"
    
    print(f"Token endpoint: {token_endpoint}")
    print(f"Client ID: {client_id}")
    
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
        }
    )
    
    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data['access_token']
        expires_in = token_data['expires_in']
        
        # Calculate expiration time
        expires_at = datetime.now() + timedelta(seconds=expires_in)
        
        # Save to files
        with open('.bearer_token', 'w') as f:
            f.write(access_token)
        
        with open('bearer_token.json', 'w') as f:
            json.dump({
                'access_token': access_token,
                'token_type': token_data['token_type'],
                'expires_in': expires_in,
                'expires_at': expires_at.isoformat()
            }, f, indent=2)
        
        print(f"✅ Token generated successfully!")
        print(f"Expires in: {expires_in} seconds ({expires_in//60} minutes)")
        print(f"Expires at: {expires_at}")
        print(f"Token (first 50 chars): {access_token[:50]}...")
        
    else:
        print(f"✗ Error: {response.status_code}")
        print(response.text)
        
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
