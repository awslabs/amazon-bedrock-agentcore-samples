#!/usr/bin/env python3
"""
Cognito M2M Setup Script using AWS boto3 SDK
Converts the bash/AWS CLI script to Python boto3 equivalent
"""

import boto3
import json
import time
from datetime import datetime
from botocore.exceptions import ClientError

# Configuration
REGION = "us-west-2"
POOL_NAME = "M2MUserPool"
RESOURCE_SERVER_IDENTIFIER = "https://api.myapp.com"
RESOURCE_SERVER_NAME = "MyApp API"
CLIENT_NAME = "M2MClient"

def create_m2m_pool():
    # Initialize Cognito IDP client
    cognito_client = boto3.client('cognito-idp', region_name=REGION)
    
    try:
        # Step 1: Create User Pool
        print("Creating User Pool...")
        user_pool_response = cognito_client.create_user_pool(
            PoolName=POOL_NAME,
            Policies={
                'PasswordPolicy': {
                    'MinimumLength': 8
                }
            }
        )
        
        pool_id = user_pool_response['UserPool']['Id']
        print(f"✅ User Pool created with ID: {pool_id}")
        
        # Save pool details to file
        with open('pool.json', 'w') as f:
            json.dump(user_pool_response, f, indent=2, default=str)
        
        # Step 2: Create Resource Server with custom scopes
        print("Creating Resource Server with custom scopes...")
        resource_server_response = cognito_client.create_resource_server(
            UserPoolId=pool_id,
            Identifier=RESOURCE_SERVER_IDENTIFIER,
            Name=RESOURCE_SERVER_NAME,
            Scopes=[
                {
                    'ScopeName': 'read',
                    'ScopeDescription': 'Read access to API resources'
                },
                {
                    'ScopeName': 'write',
                    'ScopeDescription': 'Write access to API resources'
                },
                {
                    'ScopeName': 'admin',
                    'ScopeDescription': 'Administrative access to API resources'
                }
            ]
        )
        
        resource_server_id = resource_server_response['ResourceServer']['Identifier']
        print(f"✅ Resource Server created with ID: {resource_server_id}")
        
        # Save resource server details to file
        with open('resource_server.json', 'w') as f:
            json.dump(resource_server_response, f, indent=2, default=str)
        
        # Step 3: Create Machine-to-Machine App Client with OAuth Client Credentials flow
        print("Creating M2M App Client...")
        client_response = cognito_client.create_user_pool_client(
            UserPoolId=pool_id,
            ClientName=CLIENT_NAME,
            GenerateSecret=True,
            ExplicitAuthFlows=['ALLOW_ADMIN_USER_PASSWORD_AUTH'],
            SupportedIdentityProviders=['COGNITO'],
            AllowedOAuthFlows=['client_credentials'],
            AllowedOAuthScopes=[
                f'{RESOURCE_SERVER_IDENTIFIER}/read',
                f'{RESOURCE_SERVER_IDENTIFIER}/write',
                f'{RESOURCE_SERVER_IDENTIFIER}/admin'
            ],
            AllowedOAuthFlowsUserPoolClient=True
        )
        
        client_id = client_response['UserPoolClient']['ClientId']
        client_secret = client_response['UserPoolClient']['ClientSecret']
        print(f"✅ M2M Client created with ID: {client_id}")
        
        # Save client details to file
        with open('m2m_client.json', 'w') as f:
            json.dump(client_response, f, indent=2, default=str)
        
        # Step 4: Create User Pool Domain
        domain_name = f"m2m-domain-{str(int(time.time()))[-5:]}"
        print(f"Creating User Pool Domain: {domain_name}")
        
        try:
            cognito_client.create_user_pool_domain(
                Domain=domain_name,
                UserPoolId=pool_id
            )
            print(f"✅ Domain created: {domain_name}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'InvalidParameterException':
                print(f"⚠️  Domain {domain_name} might already exist, continuing...")
            else:
                raise
        
        # Step 5: Create test user
        print("Creating test user...")
        try:
            cognito_client.admin_create_user(
                UserPoolId=pool_id,
                Username="m2m-test-user",
                TemporaryPassword="TempPass123!",
                MessageAction='SUPPRESS'
            )
            
            # Set permanent password
            cognito_client.admin_set_user_password(
                UserPoolId=pool_id,
                Username="m2m-test-user",
                Password="TestPass123!",
                Permanent=True
            )
            print("✅ Test user created: m2m-test-user / TestPass123!")
        except ClientError as e:
            if e.response['Error']['Code'] == 'UsernameExistsException':
                print("⚠️  Test user already exists, continuing...")
            else:
                raise
        
        # Step 6: Display results
        print("\n" + "="*50)
        print("Machine-to-Machine Client Created Successfully!")
        print("="*50)
        print(f"User Pool ID: {pool_id}")
        print(f"Resource Server ID: {resource_server_id}")
        print(f"Client ID: {client_id}")
        #print(f"Client Secret: {client_secret}")
        print("="*50)
        
        # Step 7: Save credentials to JSON file
        credentials = {
            "userPoolId": pool_id,
            "resourceServerId": resource_server_id,
            "clientId": client_id,
            "clientSecret": client_secret,
            "region": REGION,
            "scopes": [
                f"{RESOURCE_SERVER_IDENTIFIER}/read",
                f"{RESOURCE_SERVER_IDENTIFIER}/write",
                f"{RESOURCE_SERVER_IDENTIFIER}/admin"
            ]
        }
        
        with open('m2m_credentials.json', 'w') as f:
            json.dump(credentials, f, indent=2)
        
        print("Credentials saved to: m2m_credentials.json")
        
        
        
        return {
            'pool_id': pool_id,
            'client_id': client_id,
            'client_secret': client_secret,
            'domain_name': domain_name,
            'resource_server_id': resource_server_id
        }
        
    except ClientError as e:
        print(f"❌ AWS Error: {e.response['Error']['Code']} - {e.response['Error']['Message']}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return None

def test_client_credentials_flow(domain_name, client_id, client_secret):
    """
    Optional function to test the Client Credentials flow programmatically
    """
    import requests
    
    token_url = f"https://{domain_name}.auth.{REGION}.amazoncognito.com/oauth2/token"
    
    data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': f'{RESOURCE_SERVER_IDENTIFIER}/read {RESOURCE_SERVER_IDENTIFIER}/write'
    }
    
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    try:
        response = requests.post(token_url, data=data, headers=headers)
        if response.status_code == 200:
            token_data = response.json()
            print(f"\n✅ Successfully obtained access token!")
            print(f"Access Token: {token_data.get('access_token', 'N/A')[:50]}...")
            print(f"Token Type: {token_data.get('token_type', 'N/A')}")
            print(f"Expires In: {token_data.get('expires_in', 'N/A')} seconds")
            return token_data
        else:
            print(f"\n❌ Failed to obtain token: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"\n❌ Error testing token endpoint: {str(e)}")
        return None

if __name__ == "__main__":
    print("🚀 Starting Cognito M2M setup with boto3...")
    result = create_m2m_pool()
    
    if result:
        print("\n🎉 Setup completed successfully!")
        
        # Uncomment the line below to test the Client Credentials flow
        # test_client_credentials_flow(result['domain_name'], result['client_id'], result['client_secret'])
    else:
        print("\n❌ Setup failed!")
