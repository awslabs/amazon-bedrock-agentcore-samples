from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient
from dotenv import load_dotenv
import os
import re

load_dotenv()

COGNITO_AUTH_NAME = os.getenv('COGNITO_AUTH_NAME')

# Initialize the Gateway client
client = GatewayClient(region_name="us-west-2")
cognito_result = client.create_oauth_authorizer_with_cognito(COGNITO_AUTH_NAME)

print("Cognito OAuth setup completed!")
print(f"Client info: {cognito_result['client_info']}")

# Extract values from the result
client_info = cognito_result['client_info']
user_pool_id = client_info.get('user_pool_id')
client_id = client_info.get('client_id')
client_secret = client_info.get('client_secret')
region = client_info.get('region', 'us-west-2')

# Extract domain from token_endpoint or use domain_prefix
token_endpoint = client_info.get('token_endpoint', '')
auth_endpoint = client_info.get('authorization_endpoint', '')
discovery_url = client_info.get('issuer', '')

if token_endpoint:
    # Extract domain from token endpoint URL
    domain_match = re.search(r'https://([^/]+)', token_endpoint)
    domain = domain_match.group(1) if domain_match else client_info.get('domain_prefix')
else:
    domain = client_info.get('domain_prefix')

# Construct URLs if not provided
if not discovery_url and user_pool_id:
    discovery_url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"

if not auth_endpoint and domain:
    auth_endpoint = f"https://{domain}/oauth2/authorize"

if not token_endpoint and domain:
    token_endpoint = f"https://{domain}/oauth2/token"

# Path to agent-runtime .env file (from gateway folder)
agent_runtime_env_path = '../agent-runtime/.env'

def update_env_file(file_path, updates, description):
    """Update or create .env file with given updates."""
    if os.path.exists(file_path):
        # Read existing .env file
        with open(file_path, 'r') as file:
            content = file.read()
        
        # Update or add the configuration values
        for key, value in updates.items():
            if value:  # Only update if value exists
                pattern = rf'^{key}=.*$'
                replacement = f'{key}={value}'
                
                if re.search(pattern, content, re.MULTILINE):
                    # Update existing value
                    content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
                else:
                    # Add new value at the end
                    content += f'\n{replacement}'
        
        # Write updated content back to .env file
        with open(file_path, 'w') as file:
            file.write(content)
        
        print(f"\n✅ Updated existing {description} with Cognito configuration:")
    else:
        # Create new .env file with configuration
        content = f"# Cognito OAuth configuration\n"
        
        # Add configuration values
        for key, value in updates.items():
            if value:  # Only add if value exists
                content += f'{key}={value}\n'
        
        # Write new .env file
        with open(file_path, 'w') as file:
            file.write(content)
        
        print(f"\n✅ Created new {description} with Cognito configuration:")

# Update local .env file with the new values (existing functionality)
env_file_path = '.env'

# Prepare the Cognito configuration values for local .env (existing functionality)
local_updates = {
    'COGNITO_USERPOOL_ID': user_pool_id,
    'COGNITO_CLIENT_ID': client_id,
    'COGNITO_CLIENT_SECRET': client_secret,
    'COGNITO_DOMAIN': domain
}

# Prepare the Cognito configuration values for agent-runtime .env (for cognito_credentials_provider.py)
agent_runtime_updates = {
    'COGNITO_CLIENT_ID': client_id,
    'COGNITO_CLIENT_SECRET': client_secret,
    'COGNITO_DISCOVERY_URL': discovery_url,
    'COGNITO_AUTH_URL': auth_endpoint,
    'COGNITO_TOKEN_URL': token_endpoint
}

# Update local .env file (existing functionality)
update_env_file(env_file_path, local_updates, "local .env file")

# Update agent-runtime .env file (new functionality)
update_env_file(agent_runtime_env_path, agent_runtime_updates, "agent-runtime .env file")

print(f"\n🎉 Successfully updated both .env files with Cognito OAuth configuration!")
print(f"   Local .env: {os.path.abspath(env_file_path)}")
print(f"   Agent-runtime .env: {os.path.abspath(agent_runtime_env_path)}")
