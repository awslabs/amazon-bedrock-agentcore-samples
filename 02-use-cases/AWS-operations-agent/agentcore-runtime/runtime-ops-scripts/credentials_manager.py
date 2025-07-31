#!/usr/bin/env python3
"""
Credentials Manager - CRUD operations for OAuth2 Credential Providers
"""

import boto3
import json
import sys
import os
import yaml
from datetime import datetime

# Add config directory to path
config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'config')
sys.path.append(config_path)

class CredentialsManager:
    def __init__(self, region='us-east-1'):
        self.region = region
        self.control_client = boto3.client('bedrock-agentcore-control', region_name=region)
        
    def list_providers(self):
        """List all OAuth2 credential providers"""
        try:
            print("🔍 Listing OAuth2 Credential Providers...")
            response = self.control_client.list_oauth2_credential_providers()
            providers = response.get('credentialProviders', [])
            
            if not providers:
                print("   📋 No OAuth2 credential providers found")
                return []
                
            print(f"   📋 Found {len(providers)} provider(s):")
            for provider in providers:
                print(f"      • Name: {provider.get('name')}")
                print(f"        ARN: {provider.get('credentialProviderArn')}")
                print(f"        Vendor: {provider.get('credentialProviderVendor')}")
                print(f"        Created: {provider.get('createdTime', 'Unknown')}")
                print(f"        Updated: {provider.get('lastUpdatedTime', 'Unknown')}")
                print()
                
            return providers
            
        except Exception as e:
            print(f"❌ Error listing providers: {e}")
            print(f"   🔍 Debug: Exception type: {type(e)}")
            import traceback
            print(f"   🔍 Debug: Traceback:")
            traceback.print_exc()
            return []
    
    def get_provider(self, provider_name):
        """Get details of a specific OAuth2 credential provider"""
        try:
            print(f"🔍 Getting provider details: {provider_name}")
            response = self.control_client.get_oauth2_credential_provider(
                oauth2CredentialProviderName=provider_name
            )
            
            provider = response
            print(f"   📋 Provider Details:")
            print(f"      • Name: {provider.get('name')}")
            print(f"      • ARN: {provider.get('oauth2CredentialProviderArn')}")
            print(f"      • Status: {provider.get('status')}")
            print(f"      • Domain: {provider.get('domain')}")
            print(f"      • Type: {provider.get('oauth2CredentialProviderType')}")
            print(f"      • Created: {provider.get('createdTime')}")
            print(f"      • Updated: {provider.get('updatedTime')}")
            
            # Show configuration if available
            config = provider.get('oauth2CredentialProviderConfiguration', {})
            if config:
                print(f"      • Configuration:")
                print(f"        - Client ID: {config.get('clientId', 'Not set')}")
                print(f"        - Authorization Server: {config.get('authorizationServer', 'Not set')}")
                print(f"        - Token Endpoint: {config.get('tokenEndpoint', 'Not set')}")
                print(f"        - Authorization Endpoint: {config.get('authorizationEndpoint', 'Not set')}")
                
                # Don't show sensitive fields like client_secret
                sensitive_fields = ['clientSecret', 'privateKey']
                for field in sensitive_fields:
                    if field in config:
                        print(f"        - {field}: [HIDDEN]")
            
            return provider
            
        except Exception as e:
            print(f"❌ Error getting provider: {e}")
            return None
    
    def create_okta_provider(self, name, domain, client_id, client_secret, scopes=None):
        """Create an Okta OAuth2 credential provider"""
        try:
            print(f"🆕 Creating Okta OAuth2 provider: {name}")
            
            # Default scopes if none provided
            if scopes is None:
                scopes = ["api"]
            
            # Okta configuration
            config = {
                'clientId': client_id,
                'clientSecret': client_secret,
                'authorizationServer': 'default',  # Default Okta auth server
                'tokenEndpoint': f'https://{domain}/oauth2/default/v1/token',
                'authorizationEndpoint': f'https://{domain}/oauth2/default/v1/authorize',
                'scopes': scopes
            }
            
            response = self.control_client.create_oauth2_credential_provider(
                oauth2CredentialProviderName=name,
                domain=domain,
                oauth2CredentialProviderType='OKTA',
                oauth2CredentialProviderConfiguration=config
            )
            
            print(f"   ✅ Provider created successfully!")
            print(f"      • ARN: {response.get('oauth2CredentialProviderArn')}")
            print(f"      • Domain: {domain}")
            print(f"      • Scopes: {scopes}")
            
            return response
            
        except Exception as e:
            print(f"❌ Error creating provider: {e}")
            return None
    
    def create_provider_from_config(self, name, config_file=None):
        """Create OAuth2 provider from configuration file"""
        try:
            if config_file is None:
                config_file = os.path.join(config_path, 'okta-config.yaml')
            
            print(f"🆕 Creating OAuth2 provider from config: {config_file}")
            
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
            
            okta_config = config.get('okta', {})
            domain = okta_config.get('domain')
            client_creds = okta_config.get('client_credentials', {})
            client_id = client_creds.get('client_id')
            
            # Try to get client secret from environment or config
            client_secret = os.getenv('OKTA_CLIENT_SECRET')
            if not client_secret:
                client_secret = client_creds.get('client_secret', '').replace('${OKTA_CLIENT_SECRET}', '')
            
            if not all([domain, client_id, client_secret]):
                print("❌ Missing required Okta configuration")
                print(f"   Domain: {domain}")
                print(f"   Client ID: {client_id}")
                print(f"   Client Secret: {'Set' if client_secret else 'Not set'}")
                return None
            
            scopes = [client_creds.get('scope', 'api')]
            
            return self.create_okta_provider(name, domain, client_id, client_secret, scopes)
            
        except Exception as e:
            print(f"❌ Error creating provider from config: {e}")
            return None
    
    def delete_provider(self, provider_name):
        """Delete an OAuth2 credential provider"""
        try:
            print(f"🗑️  Deleting OAuth2 provider: {provider_name}")
            
            self.control_client.delete_oauth2_credential_provider(
                oauth2CredentialProviderName=provider_name
            )
            print(f"   ✅ Provider deletion initiated: {provider_name}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error deleting provider: {e}")
            return False
    
    def update_provider_config(self, provider_name, config_updates):
        """Update OAuth2 provider configuration"""
        try:
            print(f"📝 Updating OAuth2 provider: {provider_name}")
            
            response = self.control_client.update_oauth2_credential_provider(
                oauth2CredentialProviderName=provider_name,
                oauth2CredentialProviderConfiguration=config_updates
            )
            
            print(f"   ✅ Provider updated successfully!")
            
            return response
            
        except Exception as e:
            print(f"❌ Error updating provider: {e}")
            return None

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 credentials_manager.py list")
        print("  python3 credentials_manager.py get <provider_name>")
        print("  python3 credentials_manager.py create-okta <name> <domain> <client_id> <client_secret> [scopes]")
        print("  python3 credentials_manager.py create-from-config <name> [config_file]")
        print("  python3 credentials_manager.py delete <provider_name>")
        print("")
        print("Examples:")
        print("  python3 credentials_manager.py create-okta my-okta trial-123.okta.com abc123 secret456 api")
        print("  python3 credentials_manager.py create-from-config bac-identity-provider-okta")
        sys.exit(1)
    
    manager = CredentialsManager()
    command = sys.argv[1]
    
    if command == "list":
        manager.list_providers()
    elif command == "get" and len(sys.argv) > 2:
        manager.get_provider(sys.argv[2])
    elif command == "create-okta" and len(sys.argv) > 5:
        name = sys.argv[2]
        domain = sys.argv[3]
        client_id = sys.argv[4]
        client_secret = sys.argv[5]
        scopes = sys.argv[6].split(',') if len(sys.argv) > 6 else None
        manager.create_okta_provider(name, domain, client_id, client_secret, scopes)
    elif command == "create-from-config" and len(sys.argv) > 2:
        name = sys.argv[2]
        config_file = sys.argv[3] if len(sys.argv) > 3 else None
        manager.create_provider_from_config(name, config_file)
    elif command == "delete" and len(sys.argv) > 2:
        manager.delete_provider(sys.argv[2])
    else:
        print("Invalid command or missing arguments")
        sys.exit(1)

if __name__ == "__main__":
    main()