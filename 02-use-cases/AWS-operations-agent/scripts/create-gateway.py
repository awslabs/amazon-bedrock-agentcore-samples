#!/usr/bin/env python3
"""
Create Bedrock AgentCore Gateway
Uses configuration from /configs (AWS is source of truth)
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
    parser = argparse.ArgumentParser(description='Create Bedrock AgentCore Gateway')
    parser.add_argument('--name', help='Gateway name (optional)')
    parser.add_argument('--description', help='Gateway description (optional)')
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
    print(f"\n {title}")
    print("=" * 60)
    print(json.dumps(response_data, indent=2, default=str))
    print("=" * 60)

def create_bedrock_agentcore_gateway(config_manager, environment, gateway_name=None, description=None):
    """Create Bedrock AgentCore Gateway using configuration"""
    
    # Get configuration
    aws_config = config_manager.get_aws_config(environment)
    auth_config = config_manager.get_okta_authorizer_config()
    bedrock_agentcore_role_arn = config_manager.get_bedrock_agentcore_role_arn(environment)
    endpoints = config_manager.get_bedrock_agentcore_endpoints()
    tool_count = len(config_manager.get_tool_schemas())
    
    print(f"Using Configuration:")
    print(f"   Environment: {environment}")
    print(f"   AWS Profile: {aws_config['profile']}")
    print(f"   AWS Region: {aws_config['region']}")
    print(f"   AWS Account: {aws_config['account']}")
    print(f"   Bedrock AgentCore Endpoint: {endpoints['control_plane']}")
    print(f"   Bedrock AgentCore Role ARN: {bedrock_agentcore_role_arn}")
    print(f"   Available Tools: {tool_count}")
    
    # Generate gateway name if not provided
    if not gateway_name:
        gateway_name = f"{environment}-aws-resource-inspector-gateway"
    
    if not description:
        description = f'AWS Resource Inspector Gateway for {environment} environment - {tool_count} tools available'
    
    # Create AWS session
    session = boto3.Session(
        profile_name=aws_config['profile'],
        region_name=aws_config['region']
    )
    
    # Use the specified bedrock-agentcore-control client configuration
    bedrock_agentcore_client = session.client(
        'bedrock-agentcore-control', 
        region_name=aws_config['region'], 
        endpoint_url=endpoints['control_plane']
    )
    
    # Prepare request - match the exact structure from the successful curl command
    request_data = {
        'name': gateway_name,
        'protocolType': 'MCP',
        'roleArn': bedrock_agentcore_role_arn,
        'description': description,
        'authorizerType': 'CUSTOM_JWT',
        'authorizerConfiguration': auth_config
    }
    
    print_request("CREATE GATEWAY REQUEST", request_data)
    
    try:
        # Create gateway using the PUT method to match the curl command
        response = bedrock_agentcore_client.create_gateway(**request_data)
        
        print_response("CREATE GATEWAY RESPONSE", response)
        
        gateway_id = response['gatewayId']
        gateway_status = response.get('status', 'Unknown')
        actual_mcp_endpoint = response.get('gatewayUrl', 'Unknown')
        
        # Update the config with the complete gateway information from the response
        config_manager.update_gateway_info_from_response(response)
        
        print(f"\nGateway Created Successfully!")
        print(f"   Gateway ID: {gateway_id}")
        print(f"   Status: {gateway_status}")
        print(f"   MCP Endpoint: {actual_mcp_endpoint}")
        print(f"   Environment: {environment}")
        
        return gateway_id, response
        
    except Exception as e:
        logger.error(f"Gateway creation failed: {str(e)}")
        print(f"\nGateway creation failed: {str(e)}")
        raise

def main():
    """Main function"""
    args = parse_arguments()
    
    # Initialize configuration manager
    config_manager = BedrockAgentCoreConfigManager()
    
    # Use default environment from config
    environment = config_manager.get_default_environment()
    
    print("🚀 Create Bedrock AgentCore Gateway")
    print("=" * 40)
    print(f"Environment: {environment}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    try:
        # Validate configuration
        if not config_manager.validate_config():
            print("❌ Configuration validation failed")
            sys.exit(1)
        
        # Create gateway
        gateway_id, response = create_bedrock_agentcore_gateway(
            config_manager, 
            environment, 
            args.name, 
            args.description
        )
        
        print(f"\n✅ Gateway creation completed successfully!")
        print(f"   Use 'python list-gateways.py' to see all gateways")
        print(f"   Use 'python get-gateway.py --gateway-id {gateway_id}' for details")
        
    except Exception as e:
        logger.error(f"Operation failed: {str(e)}")
        print(f"\n❌ Operation failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
