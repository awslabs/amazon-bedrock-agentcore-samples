#!/usr/bin/env python3
"""
Delete Bedrock AgentCore Gateway Target
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
    parser = argparse.ArgumentParser(description='Delete Bedrock AgentCore Gateway Target')
    parser.add_argument('--gateway-id', required=True, help='Gateway ID')
    parser.add_argument('--target-id', required=True, help='Target ID to delete')
    parser.add_argument('--force', action='store_true', help='Skip confirmation prompt')
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

def get_target_info(bedrock_agentcore_client, gateway_id, target_id):
    """Get target information from AWS"""
    try:
        response = bedrock_agentcore_client.get_gateway_target(
            gatewayIdentifier=gateway_id,
            targetId=target_id
        )
        return response
    except Exception as e:
        logger.error(f"Failed to get target info: {str(e)}")
        return None

def get_gateway_info(bedrock_agentcore_client, gateway_id):
    """Get gateway information from AWS"""
    try:
        response = bedrock_agentcore_client.get_gateway(gatewayIdentifier=gateway_id)
        return response
    except Exception as e:
        logger.error(f"Failed to get gateway info: {str(e)}")
        return None

def confirm_deletion(target_info, gateway_info):
    """Confirm target deletion with user"""
    
    print(f"\nTarget Deletion Confirmation")
    print("=" * 40)
    print(f"Gateway ID: {gateway_info.get('gatewayId', 'Unknown')}")
    print(f"Gateway Name: {gateway_info.get('name', 'Unknown')}")
    print(f"Target ID: {target_info.get('targetId', 'Unknown')}")
    print(f"Target Name: {target_info.get('name', 'Unknown')}")
    print(f"Target Status: {target_info.get('status', 'Unknown')}")
    print(f"Description: {target_info.get('description', 'None')}")
    
    # Extract tool information if available
    target_config = target_info.get('targetConfiguration', {})
    if 'mcp' in target_config and 'lambda' in target_config['mcp']:
        lambda_config = target_config['mcp']['lambda']
        lambda_arn = lambda_config.get('lambdaArn', 'Unknown')
        print(f"Lambda ARN: {lambda_arn}")
        
        tool_schema = lambda_config.get('toolSchema', {})
        if 'inlinePayload' in tool_schema:
            tools = tool_schema['inlinePayload']
            tool_names = [tool.get('name', 'unknown') for tool in tools]
            print(f"Tool Count: {len(tools)}")
            print(f"Tools: {', '.join(tool_names)}")
    
    print()
    print("This action cannot be undone!")
    print()
    
    confirmation = input("Type 'DELETE' to confirm target deletion: ").strip()
    
    if confirmation != 'DELETE':
        print("Deletion cancelled")
        return False
    
    return True

def delete_gateway_target(config_manager, environment, gateway_id, target_id, force=False):
    """Delete Gateway Target using configuration"""
    
    # Get configuration
    aws_config = config_manager.get_aws_config(environment)
    endpoints = config_manager.get_bedrock_agentcore_endpoints()
    
    print(f"Using Configuration:")
    print(f"   Environment: {environment}")
    print(f"   AWS Profile: {aws_config['profile']}")
    print(f"   AWS Region: {aws_config['region']}")
    print(f"   AWS Account: {aws_config['account']}")
    print(f"   Bedrock AgentCore Endpoint: {endpoints['control_plane']}")
    
    # Create AWS session
    session = boto3.Session(
        profile_name=aws_config['profile'],
        region_name=aws_config['region']
    )
    
    bedrock_agentcore_client = session.client(
        'bedrock-agentcore-control',
        region_name=aws_config['region'],
        endpoint_url=endpoints['control_plane']
    )
    
    # Get target and gateway information
    print(f"\nRetrieving target and gateway information...")
    target_info = get_target_info(bedrock_agentcore_client, gateway_id, target_id)
    gateway_info = get_gateway_info(bedrock_agentcore_client, gateway_id)
    
    if not target_info:
        print(f"Target {target_id} not found in gateway {gateway_id}")
        return False
    
    if not gateway_info:
        print(f"Gateway {gateway_id} not found")
        return False
    
    # Confirm deletion unless forced
    if not force:
        if not confirm_deletion(target_info, gateway_info):
            return False
    
    # Prepare request
    request_data = {
        'gatewayIdentifier': gateway_id,
        'targetId': target_id
    }
    
    print_request("DELETE TARGET REQUEST", request_data)
    
    try:
        # Delete target
        response = bedrock_agentcore_client.delete_gateway_target(**request_data)
        
        print_response("DELETE TARGET RESPONSE", response)
        
        print(f"\nTarget Deleted Successfully!")
        print(f"   Target ID: {target_id}")
        print(f"   Gateway ID: {gateway_id}")
        print(f"   Environment: {environment}")
        
        return True
        
    except Exception as e:
        logger.error(f"Target deletion failed: {str(e)}")
        print(f"\nTarget deletion failed: {str(e)}")
        return False

def main():
    """Main function"""
    args = parse_arguments()
    
    # Initialize configuration manager
    config_manager = BedrockAgentCoreConfigManager()
    
    # Use default environment from config
    environment = config_manager.get_default_environment()
    
    print("Delete Bedrock AgentCore Gateway Target")
    print("=" * 45)
    print(f"Environment: {environment}")
    print(f"Gateway ID: {args.gateway_id}")
    print(f"Target ID: {args.target_id}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    try:
        # Validate configuration
        if not config_manager.validate_config():
            print("Configuration validation failed")
            sys.exit(1)
        
        # Delete target
        success = delete_gateway_target(
            config_manager,
            environment,
            args.gateway_id,
            args.target_id,
            args.force
        )
        
        if success:
            print(f"\nTarget deletion completed successfully!")
            print(f"   Use 'python list-targets.py --gateway-id {args.gateway_id}' to see remaining targets")
        else:
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"Operation failed: {str(e)}")
        print(f"\nOperation failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
