#!/usr/bin/env python3
"""
Update Bedrock AgentCore Gateway
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
    parser = argparse.ArgumentParser(description='Update Bedrock AgentCore Gateway')
    parser.add_argument('--gateway-id', required=True, help='Gateway ID to update')
    parser.add_argument('--name', help='New gateway name')
    parser.add_argument('--description', help='New gateway description')
    parser.add_argument('--role-arn', help='New IAM role ARN')
    parser.add_argument('--show-current', action='store_true', help='Show current gateway configuration')
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

def get_gateway_info(bedrock_agentcore_client, gateway_id):
    """Get current gateway information from AWS"""
    try:
        response = bedrock_agentcore_client.get_gateway(gatewayIdentifier=gateway_id)
        return response
    except Exception as e:
        logger.error(f"Failed to get gateway info: {str(e)}")
        return None

def print_gateway_info(gateway_info):
    """Print formatted gateway information"""
    print(f"\nCurrent Gateway Configuration")
    print("=" * 50)
    print(f"Gateway ID: {gateway_info.get('gatewayId', 'Unknown')}")
    print(f"Name: {gateway_info.get('name', 'Unknown')}")
    print(f"Description: {gateway_info.get('description', 'None')}")
    print(f"Status: {gateway_info.get('status', 'Unknown')}")
    print(f"MCP Endpoint: {gateway_info.get('mcpEndpoint', 'Unknown')}")
    print(f"Role ARN: {gateway_info.get('roleArn', 'Unknown')}")
    print(f"Created: {gateway_info.get('createdAt', 'Unknown')}")
    print(f"Updated: {gateway_info.get('updatedAt', 'Unknown')}")

def confirm_update(gateway_info, updates):
    """Confirm gateway update with user"""
    
    print(f"\nGateway Update Confirmation")
    print("=" * 40)
    print(f"Gateway ID: {gateway_info.get('gatewayId', 'Unknown')}")
    print(f"Current Name: {gateway_info.get('name', 'Unknown')}")
    
    print(f"\nProposed Changes:")
    for field, new_value in updates.items():
        if field == 'gatewayIdentifier':
            continue
        current_value = gateway_info.get(field, 'None')
        print(f"  {field}: '{current_value}' → '{new_value}'")
    
    print()
    confirmation = input("Proceed with gateway update? (y/N): ").strip().lower()
    
    if confirmation != 'y':
        print("Update cancelled")
        return False
    
    return True

def update_bedrock_agentcore_gateway(config_manager, environment, gateway_id, updates, show_current=False):
    """Update Bedrock AgentCore Gateway using configuration"""
    
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
        'bedrock-agent-core',
        endpoint_url=endpoints['control_plane']
    )
    
    # Get current gateway information
    print(f"\nRetrieving current gateway information...")
    gateway_info = get_gateway_info(bedrock_agentcore_client, gateway_id)
    
    if not gateway_info:
        print(f"Gateway {gateway_id} not found")
        return False
    
    # Show current configuration if requested
    if show_current:
        print_gateway_info(gateway_info)
        return True
    
    # If no updates provided, show current info and exit
    if not updates or len(updates) == 1:  # Only gatewayIdentifier
        print("No updates specified. Current gateway configuration:")
        print_gateway_info(gateway_info)
        print("\nUse --name, --description, or --role-arn to specify updates")
        return True
    
    # Confirm update
    if not confirm_update(gateway_info, updates):
        return False
    
    print_request("UPDATE GATEWAY REQUEST", updates)
    
    try:
        # Update gateway
        response = bedrock_agentcore_client.update_gateway(**updates)
        
        print_response("UPDATE GATEWAY RESPONSE", response)
        
        print(f"\nGateway Updated Successfully!")
        print(f"   Gateway ID: {gateway_id}")
        print(f"   Environment: {environment}")
        
        # Show updated configuration
        print(f"\nRetrieving updated gateway information...")
        updated_gateway_info = get_gateway_info(bedrock_agentcore_client, gateway_id)
        if updated_gateway_info:
            print_gateway_info(updated_gateway_info)
        
        return True
        
    except Exception as e:
        logger.error(f"Gateway update failed: {str(e)}")
        print(f"\nGateway update failed: {str(e)}")
        return False

def main():
    """Main function"""
    args = parse_arguments()
    
    # Initialize configuration manager
    config_manager = BedrockAgentCoreConfigManager()
    
    # Use default environment from config
    environment = config_manager.get_default_environment()
    
    print("Update Bedrock AgentCore Gateway")
    print("=" * 40)
    print(f"Environment: {environment}")
    print(f"Gateway ID: {args.gateway_id}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    try:
        # Validate configuration
        if not config_manager.validate_config():
            print("Configuration validation failed")
            sys.exit(1)
        
        # Build updates dictionary
        updates = {'gatewayIdentifier': args.gateway_id}
        
        if args.name:
            updates['name'] = args.name
        if args.description:
            updates['description'] = args.description
        if args.role_arn:
            updates['roleArn'] = args.role_arn
        
        # Update gateway
        success = update_bedrock_agentcore_gateway(
            config_manager,
            environment,
            args.gateway_id,
            updates,
            args.show_current
        )
        
        if not success:
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"Operation failed: {str(e)}")
        print(f"\nOperation failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
