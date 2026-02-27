#!/usr/bin/env python
"""
Automated Cognito User Pool Setup for A2A Authentication
Based on AWS AgentCore A2A documentation and samples
"""

import boto3
import json
import time
import sys
from botocore.exceptions import ClientError

class CognitoSetup:
    def __init__(self, region='us-east-1'):
        self.region = region
        self.cognito = boto3.client('cognito-idp', region_name=region)
        self.user_pool_name = 'a2a-realestate-agents-pool'
        self.app_client_name = 'a2a-realestate-client'
        self.resource_server_identifier = 'a2a-agents'
        
    def find_existing_user_pool(self):
        """Find existing user pool by name."""
        try:
            response = self.cognito.list_user_pools(MaxResults=60)
            for pool in response.get('UserPools', []):
                if pool['Name'] == self.user_pool_name:
                    return pool['Id']
        except Exception as e:
            print(f"Error searching for user pools: {e}")
        return None
    
    def create_user_pool(self):
        """Create Cognito User Pool with OAuth 2.0 configuration."""
        print("\n" + "="*70)
        print("STEP 1: Creating Cognito User Pool")
        print("="*70)
        
        # Check for existing pool
        existing_pool_id = self.find_existing_user_pool()
        if existing_pool_id:
            print(f"✓ Found existing user pool: {existing_pool_id}")
            return existing_pool_id
        
        try:
            response = self.cognito.create_user_pool(
                PoolName=self.user_pool_name,
                Policies={
                    'PasswordPolicy': {
                        'MinimumLength': 8,
                        'RequireUppercase': False,
                        'RequireLowercase': False,
                        'RequireNumbers': False,
                        'RequireSymbols': False
                    }
                },
                AutoVerifiedAttributes=['email'],
                Schema=[
                    {
                        'Name': 'email',
                        'AttributeDataType': 'String',
                        'Required': True,
                        'Mutable': True
                    }
                ],
                UserPoolTags={
                    'Purpose': 'A2A-Authentication',
                    'Project': 'RealEstate-Agents'
                }
            )
            
            user_pool_id = response['UserPool']['Id']
            print(f"✓ Created user pool: {user_pool_id}")
            return user_pool_id
            
        except ClientError as e:
            print(f"✗ Error creating user pool: {e}")
            sys.exit(1)
    
    def create_resource_server(self, user_pool_id):
        """Create resource server with custom scopes."""
        print("\n" + "="*70)
        print("STEP 2: Creating Resource Server")
        print("="*70)
        
        try:
            # Check if resource server exists
            try:
                self.cognito.describe_resource_server(
                    UserPoolId=user_pool_id,
                    Identifier=self.resource_server_identifier
                )
                print(f"✓ Resource server already exists: {self.resource_server_identifier}")
                return
            except ClientError as e:
                if 'ResourceNotFoundException' not in str(e):
                    raise
            
            # Create resource server
            self.cognito.create_resource_server(
                UserPoolId=user_pool_id,
                Identifier=self.resource_server_identifier,
                Name='A2A Agents Resource Server',
                Scopes=[
                    {
                        'ScopeName': 'invoke',
                        'ScopeDescription': 'Invoke agent operations'
                    },
                    {
                        'ScopeName': 'read',
                        'ScopeDescription': 'Read agent information'
                    }
                ]
            )
            print(f"✓ Created resource server: {self.resource_server_identifier}")
            print(f"  Scopes: {self.resource_server_identifier}/invoke, {self.resource_server_identifier}/read")
            
        except ClientError as e:
            if 'ResourceExistsException' in str(e):
                print(f"✓ Resource server already exists")
            else:
                print(f"✗ Error creating resource server: {e}")
                sys.exit(1)
    
    def create_app_client(self, user_pool_id):
        """Create app client with OAuth 2.0 client credentials flow."""
        print("\n" + "="*70)
        print("STEP 3: Creating App Client")
        print("="*70)
        
        try:
            # Check for existing clients
            clients = self.cognito.list_user_pool_clients(
                UserPoolId=user_pool_id,
                MaxResults=60
            )
            
            for client in clients.get('UserPoolClients', []):
                if client['ClientName'] == self.app_client_name:
                    client_id = client['ClientId']
                    # Get client details including secret
                    client_details = self.cognito.describe_user_pool_client(
                        UserPoolId=user_pool_id,
                        ClientId=client_id
                    )
                    client_secret = client_details['UserPoolClient'].get('ClientSecret')
                    print(f"✓ Found existing app client: {client_id}")
                    return client_id, client_secret
            
            # Create new app client
            response = self.cognito.create_user_pool_client(
                UserPoolId=user_pool_id,
                ClientName=self.app_client_name,
                GenerateSecret=True,
                ExplicitAuthFlows=[
                    'ALLOW_USER_PASSWORD_AUTH',
                    'ALLOW_REFRESH_TOKEN_AUTH'
                ],
                AllowedOAuthFlows=['client_credentials'],
                AllowedOAuthScopes=[
                    f'{self.resource_server_identifier}/invoke',
                    f'{self.resource_server_identifier}/read'
                ],
                AllowedOAuthFlowsUserPoolClient=True,
                SupportedIdentityProviders=['COGNITO'],
                PreventUserExistenceErrors='ENABLED'
            )
            
            client_id = response['UserPoolClient']['ClientId']
            client_secret = response['UserPoolClient']['ClientSecret']
            print(f"✓ Created app client: {client_id}")
            print(f"  OAuth Flows: client_credentials")
            print(f"  OAuth Scopes: {self.resource_server_identifier}/invoke, {self.resource_server_identifier}/read")
            
            return client_id, client_secret
            
        except ClientError as e:
            print(f"✗ Error creating app client: {e}")
            sys.exit(1)
    
    def create_domain(self, user_pool_id):
        """Create Cognito domain for OAuth endpoints."""
        print("\n" + "="*70)
        print("STEP 4: Creating Cognito Domain")
        print("="*70)
        
        # Generate unique domain name
        domain_name = f"a2a-realestate-{int(time.time())}"
        
        try:
            # Check if pool already has a domain
            try:
                pool_details = self.cognito.describe_user_pool(UserPoolId=user_pool_id)
                existing_domain = pool_details['UserPool'].get('Domain')
                if existing_domain:
                    print(f"✓ User pool already has domain: {existing_domain}")
                    return existing_domain
            except Exception:
                pass
            
            # Create domain
            self.cognito.create_user_pool_domain(
                Domain=domain_name,
                UserPoolId=user_pool_id
            )
            print(f"✓ Created domain: {domain_name}")
            print(f"  Token endpoint: https://{domain_name}.auth.{self.region}.amazoncognito.com/oauth2/token")
            
            return domain_name
            
        except ClientError as e:
            if 'InvalidParameterException' in str(e) or 'DomainExistsException' in str(e):
                print(f"⚠️  Domain already exists or invalid, continuing...")
                return None
            else:
                print(f"⚠️  Warning creating domain: {e}")
                return None
    
    def get_discovery_url(self, user_pool_id):
        """Get OpenID Connect discovery URL."""
        discovery_url = f"https://cognito-idp.{self.region}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration"
        return discovery_url
    
    def get_token_endpoint(self, user_pool_id):
        """Get OAuth token endpoint."""
        return f"https://cognito-idp.{self.region}.amazonaws.com/{user_pool_id}"
    
    def save_configuration(self, config):
        """Save configuration to file."""
        print("\n" + "="*70)
        print("STEP 5: Saving Configuration")
        print("="*70)
        
        config_file = 'cognito_config.json'
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        
        print(f"✓ Configuration saved to: {config_file}")
        return config_file
    
    def setup(self):
        """Run complete Cognito setup."""
        print("\n" + "="*70)
        print("AUTOMATED COGNITO SETUP FOR A2A AUTHENTICATION")
        print("="*70)
        print(f"Region: {self.region}")
        print(f"User Pool Name: {self.user_pool_name}")
        
        # Step 1: Create User Pool
        user_pool_id = self.create_user_pool()
        
        # Step 2: Create Resource Server
        self.create_resource_server(user_pool_id)
        
        # Step 3: Create App Client
        client_id, client_secret = self.create_app_client(user_pool_id)
        
        # Step 4: Create Domain
        domain = self.create_domain(user_pool_id)
        
        # Get URLs
        discovery_url = self.get_discovery_url(user_pool_id)
        token_endpoint = self.get_token_endpoint(user_pool_id)
        
        # Prepare configuration
        config = {
            'user_pool_id': user_pool_id,
            'client_id': client_id,
            'client_secret': client_secret,
            'region': self.region,
            'discovery_url': discovery_url,
            'token_endpoint': token_endpoint,
            'resource_server_identifier': self.resource_server_identifier,
            'scopes': [
                f'{self.resource_server_identifier}/invoke',
                f'{self.resource_server_identifier}/read'
            ]
        }
        
        if domain:
            config['domain'] = domain
            config['oauth_token_url'] = f"https://{domain}.auth.{self.region}.amazoncognito.com/oauth2/token"
        
        # Save configuration
        config_file = self.save_configuration(config)
        
        # Print summary
        print("\n" + "="*70)
        print("✅ COGNITO SETUP COMPLETE")
        print("="*70)
        print(f"\nConfiguration saved to: {config_file}")
        print("\n⚠️  SECURITY NOTE: Client secret has been saved to cognito_config.json")
        print("    Keep this file secure and never commit it to version control!")
        
        print("\n" + "="*70)
        print("NEXT STEPS")
        print("="*70)
        print("\n1. Deploy agents with OAuth authentication:")
        print("   python deploy_agents_with_oauth.py")
        print("\n2. Test OAuth token generation:")
        print("   python get_bearer_token.py")
        print("\n3. Invoke agents with bearer token:")
        print("   python test_a2a_with_oauth.py")
        
        return config


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Setup Cognito for A2A Authentication')
    parser.add_argument('--region', default='us-east-1', help='AWS region (default: us-east-1)')
    args = parser.parse_args()
    
    setup = CognitoSetup(region=args.region)
    config = setup.setup()
    
    return config


if __name__ == "__main__":
    main()
