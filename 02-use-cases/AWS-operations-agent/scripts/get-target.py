#!/usr/bin/env python3
"""
Get Bedrock AgentCore Gateway Target Details
Pulls live data from Bedrock AgentCore Gateway endpoint (AWS is source of truth)
"""
import json
import boto3
import logging
import argparse
import sys
from datetime import datetime
from pathlib import Path

# Add configs directory to path
sys.path.append(str(Path(__file__).parent.parent / "configs"))
from config_manager import BedrockAgentCoreConfigManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Get Bedrock AgentCore Gateway Target Details')
    parser.add_argument('--gateway-id', required=True, help='Gateway ID')
    parser.add_argument('--target-id', required=True, help='Target ID to retrieve')
    parser.add_argument("--endpoint", type=str, choices=["beta", "gamma", "production"], help="Endpoint to use (beta, gamma, production)")
    parser.add_argument("--environment", type=str, default=None, help="Environment to use (dev, gamma, prod)")
    return parser.parse_args()

def print_request(title, request_data):
    """Print formatted request"""
    print(f"\n{title}")
    print("=" * 60)
    print(json.dumps(request_data, indent=2, default=str))
    print("=" * 60)

def print_response(title, response_data):
    """Print formatted response"""
    print(f"\n{title}")
    print("=" * 60)
    print(json.dumps(response_data, indent=2, default=str))
    print("=" * 60)

def get_target_from_aws(config_manager, environment, gateway_id, target_id):
    """Get target details from AWS"""
    
    # Get configuration for the specific environment
    aws_config = config_manager.get_aws_config(environment)
    endpoints = config_manager.get_bedrock_agentcore_endpoints()
    
    print(f"Using Configuration:")
    print(f"   Environment: {environment}")
    print(f"   AWS Profile: {aws_config['profile']}")
    print(f"   AWS Region: {aws_config['region']}")
    print(f"   AWS Account: {aws_config['account']}")
    print(f"   Bedrock AgentCore Endpoint: {endpoints['control_plane']}")
    
    # Create AWS session with environment-specific profile and region
    session = boto3.Session(
        profile_name=aws_config['profile'],
        region_name=aws_config['region']
    )
    
    bedrock_agentcore_client = session.client(
        'bedrock-agentcore-control',
        endpoint_url=endpoints['control_plane']
    )
    
    # Prepare request
    request_data = {
        'gatewayIdentifier': gateway_id,
        'targetId': target_id
    }
    
    print_request("GET TARGET REQUEST", request_data)
    
    try:
        # Get target details
        response = bedrock_agentcore_client.get_gateway_target(**request_data)
        
        print_response("GET TARGET RESPONSE", response)
        
        return response, bedrock_agentcore_client
        
    except Exception as e:
        logger.error(f"Failed to get target from AWS: {str(e)}")
        print(f"\nFailed to get target from AWS: {str(e)}")
        print(f"   Check AWS profile '{aws_config['profile']}' and region '{aws_config['region']}'")
        return None, None

def get_gateway_info(bedrock_agentcore_client, gateway_id):
    """Get gateway information"""
    
    try:
        response = bedrock_agentcore_client.get_gateway(gatewayIdentifier=gateway_id)
        return response
    except Exception as e:
        logger.error(f"Failed to get gateway info: {str(e)}")
        return None

def display_target_details(config_manager, target_data, bedrock_agentcore_client):
    """Display formatted target details"""
    
    print(f"\nTarget Details")
    print("=" * 50)
    
    # Basic information
    target_id = target_data.get('targetId', 'Unknown')
    gateway_id = target_data.get('gatewayIdentifier', 'Unknown')
    
    print(f"Target ID: {target_id}")
    print(f"Name: {target_data.get('name', 'Unknown')}")
    print(f"Status: {target_data.get('status', 'Unknown')}")
    print(f"Description: {target_data.get('description', 'None')}")
    print(f"Gateway ID: {gateway_id}")
    
    # Timestamps
    if 'createdAt' in target_data:
        print(f"Created At: {target_data['createdAt']}")
    if 'updatedAt' in target_data:
        print(f"Updated At: {target_data['updatedAt']}")
    
    # Gateway information
    print(f"\nAssociated Gateway:")
    gateway_info = get_gateway_info(bedrock_agentcore_client, gateway_id)
    if gateway_info:
        print(f"   Gateway Name: {gateway_info.get('name', 'Unknown')}")
        print(f"   Gateway Status: {gateway_info.get('status', 'Unknown')}")
        mcp_endpoint = config_manager.get_mcp_gateway_url(gateway_id)
        print(f"   MCP Endpoint: {mcp_endpoint}")
    else:
        print(f"   Gateway information not available")
    
    # Target configuration
    if 'targetConfiguration' in target_data:
        target_config = target_data['targetConfiguration']
        print(f"\nTarget Configuration:")
        print(json.dumps(target_config, indent=2))
        
        # Extract and display Lambda configuration if present
        if 'mcp' in target_config and 'lambda' in target_config['mcp']:
            lambda_config = target_config['mcp']['lambda']
            print(f"\nLambda Configuration:")
            print(f"   Lambda ARN: {lambda_config.get('lambdaArn', 'Unknown')}")
            
            # Tool schema information
            if 'toolSchema' in lambda_config and 'inlinePayload' in lambda_config['toolSchema']:
                tools = lambda_config['toolSchema']['inlinePayload']
                print(f"\nAvailable Tools ({len(tools)}):")
                
                for i, tool in enumerate(tools, 1):
                    print(f"   {i}. {tool.get('name', 'unnamed')}")
                    print(f"      Description: {tool.get('description', 'No description')}")
                    
                    # Show parameters
                    input_schema = tool.get('inputSchema', {})
                    properties = input_schema.get('properties', {})
                    required = input_schema.get('required', [])
                    
                    if properties:
                        print(f"      Parameters:")
                        for param_name, param_info in properties.items():
                            param_type = param_info.get('type', 'unknown')
                            param_desc = param_info.get('description', 'No description')
                            required_marker = ' (required)' if param_name in required else ' (optional)'
                            print(f"        - {param_name} ({param_type}){required_marker}: {param_desc}")
                    else:
                        print(f"      Parameters: None")
                    print()
    
    # Credential provider configurations
    if 'credentialProviderConfigurations' in target_data:
        cred_configs = target_data['credentialProviderConfigurations']
        print(f"\nCredential Provider Configurations:")
        print(json.dumps(cred_configs, indent=2))

def main():
    """Main function"""
    args = parse_arguments()
    
    # Initialize configuration manager
    config_manager = BedrockAgentCoreConfigManager()
    
    # Use default environment from config
    environment = config_manager.get_default_environment()
    
    print("Get Bedrock AgentCore Gateway Target Details")
    print("=" * 45)
    print(f"Environment: {environment}")
    print(f"Gateway ID: {args.gateway_id}")
    print(f"Target ID: {args.target_id}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Data Source: AWS Bedrock AgentCore API (Live)")
    
    try:
        # Validate configuration
        if not config_manager.validate_config():
            print("Configuration validation failed")
            sys.exit(1)
        
        # Get target details from AWS
        aws_data, bedrock_agentcore_client = get_target_from_aws(config_manager, environment, args.gateway_id, args.target_id)
        
        if not aws_data:
            print(f"Target {args.target_id} not found in AWS")
            sys.exit(1)
        
        # Display detailed information
        display_target_details(config_manager, aws_data, bedrock_agentcore_client)
        
        print(f"\nRetrieved target details from live AWS data")
        
    except Exception as e:
        logger.error(f"Operation failed: {str(e)}")
        print(f"\nOperation failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
