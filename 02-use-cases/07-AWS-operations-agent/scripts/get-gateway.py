#!/usr/bin/env python3
"""
Get Bedrock AgentCore Gateway Details
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
    parser = argparse.ArgumentParser(description='Get Bedrock AgentCore Gateway Details')
    parser.add_argument('--gateway-id', required=True, help='Gateway ID to retrieve')
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

def get_gateway_from_aws(config_manager, environment, gateway_id):
    """Get gateway details from AWS"""
    
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
        'gatewayIdentifier': gateway_id
    }
    
    print_request("GET GATEWAY REQUEST", request_data)
    
    try:
        # Get gateway details
        response = bedrock_agentcore_client.get_gateway(**request_data)
        
        print_response("GET GATEWAY RESPONSE", response)
        
        return response, bedrock_agentcore_client
        
    except Exception as e:
        logger.error(f"Failed to get gateway from AWS: {str(e)}")
        print(f"\nFailed to get gateway from AWS: {str(e)}")
        print(f"   Check AWS profile '{aws_config['profile']}' and region '{aws_config['region']}'")
        return None, None

def get_gateway_targets(bedrock_agentcore_client, gateway_id):
    """Get targets for the gateway"""
    
    try:
        response = bedrock_agentcore_client.list_gateway_targets(gatewayIdentifier=gateway_id)
        return response.get('items', [])
    except Exception as e:
        logger.error(f"Failed to get targets for gateway {gateway_id}: {str(e)}")
        return []

def display_gateway_details(config_manager, gateway_data, bedrock_agentcore_client):
    """Display formatted gateway details"""
    
    print(f"\nGateway Details")
    print("=" * 50)
    
    # Basic information
    gateway_id = gateway_data.get('gatewayId', 'Unknown')
    print(f"Gateway ID: {gateway_id}")
    print(f"Name: {gateway_data.get('name', 'Unknown')}")
    print(f"Status: {gateway_data.get('status', 'Unknown')}")
    print(f"Protocol Type: {gateway_data.get('protocolType', 'Unknown')}")
    print(f"Authorizer Type: {gateway_data.get('authorizerType', 'Unknown')}")
    print(f"Description: {gateway_data.get('description', 'None')}")
    print(f"Role ARN: {gateway_data.get('roleArn', 'Unknown')}")
    
    # Timestamps
    if 'createdAt' in gateway_data:
        print(f"Created At: {gateway_data['createdAt']}")
    if 'updatedAt' in gateway_data:
        print(f"Updated At: {gateway_data['updatedAt']}")
    
    # Gateway URL/Endpoint
    if 'gatewayUrl' in gateway_data:
        print(f"Gateway URL: {gateway_data['gatewayUrl']}")
    elif 'endpoint' in gateway_data:
        print(f"Gateway Endpoint: {gateway_data['endpoint']}")
    
    # MCP endpoint (calculated)
    if gateway_id:
        mcp_endpoint = config_manager.get_mcp_gateway_url(gateway_id)
        print(f"MCP Endpoint: {mcp_endpoint}")
    
    # Authorizer configuration
    if 'authorizerConfiguration' in gateway_data:
        print(f"\nAuthorizer Configuration:")
        auth_config = gateway_data['authorizerConfiguration']
        print(json.dumps(auth_config, indent=2))
    
    # Protocol configuration
    if 'protocolConfiguration' in gateway_data:
        print(f"\nProtocol Configuration:")
        protocol_config = gateway_data['protocolConfiguration']
        print(json.dumps(protocol_config, indent=2))
    
    # Encryption key
    if 'kmsKeyArn' in gateway_data:
        print(f"\nEncryption Key ARN: {gateway_data['kmsKeyArn']}")
    
    # Get and display targets
    print(f"\nAssociated Targets:")
    targets = get_gateway_targets(bedrock_agentcore_client, gateway_id)
    
    if targets:
        total_tools = 0
        print(f"   Found {len(targets)} targets:")
        
        for i, target in enumerate(targets, 1):
            target_id = target.get('targetId', 'Unknown')
            target_name = target.get('name', 'Unknown')
            target_status = target.get('status', 'Unknown')
            
            print(f"     {i}. Target ID: {target_id}")
            print(f"        Name: {target_name}")
            print(f"        Status: {target_status}")
            
            # Extract tool information
            target_config = target.get('targetConfiguration', {})
            if 'mcp' in target_config and 'lambda' in target_config['mcp']:
                lambda_config = target_config['mcp']['lambda']
                lambda_arn = lambda_config.get('lambdaArn', 'Unknown')
                print(f"        Lambda ARN: {lambda_arn}")
                
                tool_schema = lambda_config.get('toolSchema', {})
                if 'inlinePayload' in tool_schema:
                    tools = tool_schema['inlinePayload']
                    tool_count = len(tools)
                    total_tools += tool_count
                    tool_names = [tool.get('name', 'unknown') for tool in tools[:3]]
                    if len(tools) > 3:
                        tool_names.append('...')
                    print(f"        Tools: {tool_count} ({', '.join(tool_names)})")
        
        print(f"\n   Total Tools Across All Targets: {total_tools}")
    else:
        print(f"   No targets found")

def main():
    """Main function"""
    args = parse_arguments()
    
    # Initialize configuration manager
    config_manager = BedrockAgentCoreConfigManager()
    
    # Use default environment from config
    environment = config_manager.get_default_environment()
    
    print("Get Bedrock AgentCore Gateway Details")
    print("=" * 40)
    print(f"Environment: {environment}")
    print(f"Gateway ID: {args.gateway_id}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Data Source: AWS Bedrock AgentCore API (Live)")
    
    try:
        # Validate configuration
        if not config_manager.validate_config():
            print("Configuration validation failed")
            sys.exit(1)
        
        # Get gateway details from AWS
        aws_data, bedrock_agentcore_client = get_gateway_from_aws(config_manager, environment, args.gateway_id)
        
        if not aws_data:
            print(f"Gateway {args.gateway_id} not found in AWS")
            sys.exit(1)
        
        # Display detailed information
        display_gateway_details(config_manager, aws_data, bedrock_agentcore_client)
        
        print(f"\nRetrieved gateway details from live AWS data")
        
    except Exception as e:
        logger.error(f"Operation failed: {str(e)}")
        print(f"\nOperation failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
