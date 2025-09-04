#!/usr/bin/env python3
import os
import json
import boto3
import shutil
from bedrock_agentcore_starter_toolkit.operations.gateway import GatewayClient

def main():
    # Set up region
    region = os.environ.get('AWS_REGION', 'us-west-2')
    print(f"Using AWS Region: {region}")
    
    # Create GatewayClient
    client = GatewayClient(region_name=region)
    
    # Load IAM role ARN
    role_arn = os.environ.get('ROLE_ARN')
    print(f"Role ARN from environment: {role_arn}")
    
    if not role_arn:
        # Try to load from config file
        config_paths = [
            "./config/iam_config.env",  # When run from project root
            "../config/iam_config.env",  # When run from scripts directory
        ]
        
        for config_path in config_paths:
            if os.path.exists(config_path):
                print(f"Found config file at {config_path}")
                with open(config_path, "r") as f:
                    for line in f:
                        if line.startswith("export GATEWAY_ROLE_ARN="):
                            role_arn = line.replace("export GATEWAY_ROLE_ARN=", "").strip()
                            break
                break
    
    if not role_arn:
        print("Error: IAM role ARN not found. Please run create_iam_roles.sh first.")
        return
    
    print(f"Using IAM role ARN: {role_arn}")
    
    # Load existing Cognito configuration
    cognito_config = {}
    config_paths = [
        "./config/cognito_config.env",  # When run from project root
        "../config/cognito_config.env",  # When run from scripts directory
    ]
    
    for config_path in config_paths:
        if os.path.exists(config_path):
            print(f"Found Cognito config file at {config_path}")
            with open(config_path, "r") as f:
                for line in f:
                    if line.startswith("export "):
                        key, value = line.replace("export ", "").strip().split("=", 1)
                        cognito_config[key] = value
            break
    
    if not cognito_config:
        print("Warning: No existing Cognito configuration found. A new one will be created.")
        # Create gateway using the GatewayClient (will create a new Cognito authorizer)
        gateway = client.create_mcp_gateway(
            name="DB-Performance-Analyzer-Gateway",
            role_arn=role_arn
        )
    else:
        print("Using existing Cognito configuration")
        # Create gateway with existing Cognito configuration
        gateway = client.client.create_gateway(
            name="DB-Performance-Analyzer-Gateway",
            roleArn=role_arn,
            protocolType="MCP",
            authorizerType="CUSTOM_JWT",
            authorizerConfiguration={
                "customJWTAuthorizer": {
                    "discoveryUrl": cognito_config["COGNITO_DISCOVERY_URL"],
                    "allowedClients": [cognito_config["COGNITO_APP_CLIENT_ID"]]
                }
            },
            description="Gateway for DB Performance Analysis"
        )
    
    print(f"Gateway created with ID: {gateway['gatewayId']}")
    print(f"Gateway ARN: {gateway['gatewayArn']}")
    
    # Get the content to write to the config file
    config_content = f"""export GATEWAY_IDENTIFIER={gateway['gatewayId']}
export GATEWAY_ARN={gateway['gatewayArn']}
export REGION={region}
"""
    
    # Save to the project's config directory
    current_dir = os.getcwd()
    os.makedirs(os.path.join(current_dir, "config"), exist_ok=True)
    with open(os.path.join(current_dir, "config/gateway_config.env"), "w") as f:
        f.write(config_content)
    print(f"Saved gateway configuration to {os.path.join(current_dir, 'config/gateway_config.env')}")
    
    # If running from scripts directory, ensure parent config directory exists
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.basename(current_dir) == "scripts":
        print("Running from scripts directory, ensuring config is accessible...")
        config_path = os.path.join(script_dir, "../config")
        if not os.path.exists(config_path):
            os.makedirs(config_path, exist_ok=True)
    
    return gateway

if __name__ == "__main__":
    main()