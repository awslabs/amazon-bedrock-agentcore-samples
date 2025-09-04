#!/usr/bin/env python3
import os
import sys
import json
import requests

def main():
    # Find the cognito_config.env file
    config_paths = [
        "./config/cognito_config.env",  # When run from project root
        "../config/cognito_config.env",  # When run from scripts directory
    ]
    
    # If running from scripts directory, ensure we look in the right place
    current_dir = os.getcwd()
    if os.path.basename(current_dir) == "scripts":
        config_paths = [
            "../config/cognito_config.env",  # When run from scripts directory
            "./config/cognito_config.env",  # Fallback
        ]
    
    config_file = None
    for path in config_paths:
        if os.path.exists(path):
            config_file = path
            print(f"Found Cognito config at {path}")
            break
    
    if not config_file:
        print("Error: Could not find cognito_config.env")
        sys.exit(1)
    
    # Load environment variables
    cognito_config = {}
    with open(config_file, 'r') as f:
        for line in f:
            if line.startswith('export '):
                key, value = line.replace('export ', '').strip().split('=', 1)
                cognito_config[key] = value.strip('"\'')
    
    # Get token
    url = f"https://{cognito_config['COGNITO_DOMAIN_NAME']}.auth.us-west-2.amazoncognito.com/oauth2/token"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = {
        'grant_type': 'client_credentials',
        'client_id': cognito_config['COGNITO_APP_CLIENT_ID'],
        'client_secret': cognito_config['COGNITO_CLIENT_SECRET']
    }
    
    try:
        print(f"Requesting token from {url}")
        print(f"Using client ID: {cognito_config['COGNITO_APP_CLIENT_ID']}")
        
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        token_data = response.json()
        token = token_data.get('access_token')
        
        if not token:
            print(f"Error: No access token in response. Full response: {token_data}")
            sys.exit(1)
            
        print(f"Token received: {token[:20]}...")
        print(f"Token expires in: {token_data.get('expires_in', 'unknown')} seconds")
        
        # Update cognito_config.env
        with open(config_file, 'r') as f:
            lines = f.readlines()
        
        with open(config_file, 'w') as f:
            for line in lines:
                if line.startswith('export COGNITO_ACCESS_TOKEN='):
                    f.write(f'export COGNITO_ACCESS_TOKEN={token}\n')
                else:
                    f.write(line)
        
        # Update mcp.json
        mcp_file = os.path.expanduser('~/.aws/amazonq/mcp.json')
        try:
            with open(mcp_file, 'r') as f:
                mcp_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Create a new mcp.json if it doesn't exist or is invalid
            mcp_data = {"mcpServers": {}}
        
        # Get gateway ID from config
        gateway_config_paths = [
            "./config/gateway_config.env",  # When run from project root
            "../config/gateway_config.env",  # When run from scripts directory
        ]
        
        # If running from scripts directory, ensure we look in the right place
        if os.path.basename(current_dir) == "scripts":
            gateway_config_paths = [
                "../config/gateway_config.env",  # When run from scripts directory
                "./config/gateway_config.env",  # Fallback
            ]
        
        gateway_id = None
        for path in gateway_config_paths:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    for line in f:
                        if line.startswith('export GATEWAY_IDENTIFIER='):
                            gateway_id = line.replace('export GATEWAY_IDENTIFIER=', '').strip()
                            break
                if gateway_id:
                    break
        
        if not gateway_id:
            print("Warning: Could not find GATEWAY_IDENTIFIER in config files")
        else:
            # Update mcp.json with the gateway ID and token
            gateway_url = f"https://{gateway_id}.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp"
            server_name = "db-performance-analyzer"
            
            # Update existing entries
            for server in mcp_data.get('mcpServers', {}):
                for i, arg in enumerate(mcp_data['mcpServers'][server]['args']):
                    if arg.startswith('Authorization: Bearer '):
                        mcp_data['mcpServers'][server]['args'][i] = f'Authorization: Bearer {token}'
            
            # Add entry if it doesn't exist
            if server_name not in mcp_data.get('mcpServers', {}):
                mcp_data.setdefault('mcpServers', {})[server_name] = {
                    "command": "npx",
                    "timeout": 60000,
                    "args": [
                        "mcp-remote@latest",
                        gateway_url,
                        "--header",
                        f"Authorization: Bearer {token}"
                    ]
                }
                print(f"Added entry for {server_name} in mcp.json")
            
            with open(mcp_file, 'w') as f:
                json.dump(mcp_data, f, indent=2)
        
        return token
        
    except Exception as e:
        print(f'Error: {e}')
        sys.exit(1)

if __name__ == "__main__":
    main()