#!/usr/bin/env python3
"""
Boto3 script to set up a Cognito User Pool with the same configuration as the CLI script.
This script creates a user pool, app client, and test users with authentication.
"""

import boto3
import json
import os
from botocore.exceptions import ClientError


def get_aws_region():
    """Get AWS region from environment variable or boto3 session."""
    region = os.environ.get('AWS_REGION')
    
    if not region:
        try:
            # Try to get region from boto3 session
            session = boto3.Session()
            region = session.region_name
        except Exception:
            pass
    
    if not region:
        region = 'us-east-1'
        print(f"Warning: No region configured. Using default: {region}")
    
    return region


def create_user_pool(cognito_client, pool_name="DemoUserPool"):
    """Create a Cognito User Pool with password policy."""
    try:
        response = cognito_client.create_user_pool(
            PoolName=pool_name,
            Policies={
                'PasswordPolicy': {
                    'MinimumLength': 8
                }
            }
        )
        
        pool_id = response['UserPool']['Id']
        print(f"Created User Pool: {pool_name} (ID: {pool_id})")
        return pool_id
        
    except ClientError as e:
        print(f"Error creating user pool: {e}")
        raise


def create_app_client(cognito_client, pool_id, client_name="DemoClient"):
    """Create a Cognito App Client."""
    try:
        response = cognito_client.create_user_pool_client(
            UserPoolId=pool_id,
            ClientName=client_name,
            GenerateSecret=False,
            ExplicitAuthFlows=[
                'ALLOW_USER_PASSWORD_AUTH',
                'ALLOW_REFRESH_TOKEN_AUTH'
            ]
        )
        
        client_id = response['UserPoolClient']['ClientId']
        print(f"Created App Client: {client_name} (ID: {client_id})")
        return client_id
        
    except ClientError as e:
        print(f"Error creating app client: {e}")
        raise


def create_user(cognito_client, pool_id, username, temp_password="Temp123!", permanent_password="MyPassword123!"):
    """Create a user and set permanent password."""
    try:
        # Create user with temporary password
        cognito_client.admin_create_user(
            UserPoolId=pool_id,
            Username=username,
            TemporaryPassword=temp_password,
            MessageAction='SUPPRESS'
        )
        print(f"Created user: {username}")
        
        # Set permanent password
        cognito_client.admin_set_user_password(
            UserPoolId=pool_id,
            Username=username,
            Password=permanent_password,
            Permanent=True
        )
        
        
    except ClientError as e:
        print(f"Error creating user {username}: {e}")
        raise


def authenticate_user(cognito_client, client_id, username, password="MyPassword123!"):
    """Authenticate user and return access token."""
    try:
        response = cognito_client.initiate_auth(
            ClientId=client_id,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': username,
                'PASSWORD': password
            }
        )
        
        access_token = response['AuthenticationResult']['AccessToken']
        print(f"Successfully authenticated user: {username}")
        return access_token
        
    except ClientError as e:
        print(f"Error authenticating user {username}: {e}")
        raise


def create_spa_pool():
    """Main function to set up Cognito User Pool."""
    # Get AWS region
    region = get_aws_region()
    print(f"Using AWS Region: {region}")
    print()
    
    # Initialize Cognito client
    cognito_client = boto3.client('cognito-idp', region_name=region)
    
    try:
        # Create User Pool
        pool_id = create_user_pool(cognito_client)
        
        # Create App Client
        client_id = create_app_client(cognito_client, pool_id)
        
        # Create and authenticate first user
        print("\nCreating testuser1...")
        create_user(cognito_client, pool_id, "testuser1")
        access_token_1 = authenticate_user(cognito_client, client_id, "testuser1")
        
        # Create and authenticate second user
        print("\nCreating testuser2...")
        create_user(cognito_client, pool_id, "testuser2")
        access_token_2 = authenticate_user(cognito_client, client_id, "testuser2")
        
        # Generate discovery URL
        discovery_url = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration"
        
        
        # Return configuration for potential use
        return {
            'pool_id': pool_id,
            'client_id': client_id,
            'discovery_url': discovery_url,
            'region': region,
            'user1': {'username':'testuser1', 'password':'MyPassword123!'},
            'user2': {'username':'testuser2', 'password':'MyPassword123!'},
            'access_tokens': {
                'testuser1': access_token_1,
                'testuser2': access_token_2
            }
        }
        
    except Exception as e:
        print(f"Setup failed: {e}")
        raise


if __name__ == "__main__":
    config = main()
