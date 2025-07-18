#!/usr/bin/env python3
"""
List Bedrock AgentCore Gateway Targets
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
    parser = argparse.ArgumentParser(description='List Bedrock AgentCore Gateway Targets (Live Data from AWS)')
    parser.add_argument('--gateway-id', help='Show targets for specific gateway only')
    parser.add_argument("--endpoint", type=str, choices=["beta", "gamma", "production"], help="Endpoint to use (beta, gamma, production)")
    parser.add_argument("--environment", type=str, default=None, help="Environment to use (dev, gamma, prod)")
    return parser.parse_args()

def print_response(title, response_data):
    """Print formatted response"""
    print(f"\n{title}")
    print("=" * 60)
    print(json.dumps(response_data, indent=2, default=str))
    print("=" * 60)

def get_live_gateways(bedrock_agentcore_client):
    """Get live gateways from AWS"""
    
    try:
        response = bedrock_agentcore_client.list_gateways()
        return response.get('items', [])
    except Exception as e:
        logger.error(f"Failed to get live gateways: {str(e)}")
        return []

def get_live_targets_for_gateway(bedrock_agentcore_client, gateway_id):
    """Get live targets for a specific gateway"""
    
    try:
        print(f"Fetching live targets for gateway {gateway_id}...")
        
        response = bedrock_agentcore_client.list_gateway_targets(gatewayIdentifier=gateway_id)
        
        print_response(f"LIST TARGETS RESPONSE (Gateway: {gateway_id})", response)
        
        targets = response.get('items', [])
        
        print(f"\nLive Data Summary for Gateway {gateway_id}:")
        print(f"   Total Targets: {len(targets)}")
        
        return targets
        
    except Exception as e:
        logger.error(f"Failed to get targets for gateway {gateway_id}: {str(e)}")
        print(f"\nFailed to get targets for gateway {gateway_id}: {str(e)}")
        return []

def display_live_targets_for_gateway(config_manager, gateway_id, gateway_name, targets):
    """Display live targets for a specific gateway"""
    
    if not targets:
        print(f"\nNo targets found for gateway {gateway_id}")
        print(f"   Create a target using: python create-target.py --gateway-id {gateway_id}")
        return
    
    # Generate MCP endpoint URL using config manager
    mcp_endpoint = config_manager.get_mcp_endpoint_url(gateway_id)
    
    print(f"\nLive Targets for Gateway {gateway_id}:")
    print("=" * 60)
    print(f"Gateway Name: {gateway_name}")
    print(f"MCP Endpoint: {mcp_endpoint}")
    
    for i, target in enumerate(targets, 1):
        target_id = target.get('targetId', 'Unknown')
        
        print(f"\n  {i}. Target ID: {target_id}")
        print(f"     Name: {target.get('name', 'Unknown')}")
        print(f"     Status: {target.get('status', 'Unknown')}")
        print(f"     Description: {target.get('description', 'None')}")
        print(f"     Created: {target.get('createdAt', 'Unknown')}")
        print(f"     Updated: {target.get('updatedAt', 'Unknown')}")
        
        # Extract Lambda ARN and tool information from target configuration
        target_config = target.get('targetConfiguration', {})
        if 'mcp' in target_config and 'lambda' in target_config['mcp']:
            lambda_config = target_config['mcp']['lambda']
            lambda_arn = lambda_config.get('lambdaArn', 'Unknown')
            print(f"     Lambda ARN: {lambda_arn}")
            
            # Tool schema information
            tool_schema = lambda_config.get('toolSchema', {})
            if 'inlinePayload' in tool_schema:
                tools = tool_schema['inlinePayload']
                print(f"     Tools: {len(tools)}")
                for j, tool in enumerate(tools, 1):
                    print(f"       {j}. {tool.get('name', 'Unknown')}: {tool.get('description', 'No description')}")

def main():
    """Main function"""
    args = parse_arguments()
    
    # Initialize configuration manager
    config_manager = BedrockAgentCoreConfigManager()
    
    # Use specified environment or default from config
    environment = args.environment or config_manager.get_default_environment()
    
    # Use specified endpoint or default from config
    endpoint_override = args.endpoint + '_endpoints' if args.endpoint else None
    
    print("List Bedrock AgentCore Gateway Targets (Live Data)")
    print("=" * 50)
    print(f"Environment: {environment}")
    print(f"Endpoint: {args.endpoint or 'default'}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Data Source: AWS Bedrock AgentCore API (Live)")
    
    try:
        # Get configuration
        aws_config = config_manager.get_aws_config(environment)
        endpoints = config_manager.get_bedrock_agentcore_endpoints(endpoint_override)
        
        # Create AWS session with environment-specific profile
        session = boto3.Session(
            profile_name=aws_config['profile'],
            region_name=aws_config['region']
        )
        
        # Use the same client configuration as in create-gateway.py
        bedrock_agentcore_client = session.client(
            'bedrock-agentcore-control', 
            region_name=aws_config['region'], 
            endpoint_url=endpoints['control_plane']
        )
        
        # If gateway ID is provided, show targets for that gateway only
        if args.gateway_id:
            try:
                # Get gateway details
                gateway_response = bedrock_agentcore_client.get_gateway(gatewayIdentifier=args.gateway_id)
                gateway_name = gateway_response.get('name', 'Unknown')
                
                # Get targets for the gateway
                targets = get_live_targets_for_gateway(bedrock_agentcore_client, args.gateway_id)
                
                # Display targets
                display_live_targets_for_gateway(config_manager, args.gateway_id, gateway_name, targets)
                
            except Exception as e:
                logger.error(f"Failed to get gateway {args.gateway_id}: {str(e)}")
                print(f"\nFailed to get gateway {args.gateway_id}: {str(e)}")
                sys.exit(1)
        
        # Otherwise, show targets for all gateways
        else:
            # Get all gateways
            gateways = get_live_gateways(bedrock_agentcore_client)
            
            if not gateways:
                print("\nNo gateways found in AWS")
                print("   Create a gateway using: python create-gateway.py")
                sys.exit(0)
            
            # Show targets for each gateway
            for gateway in gateways:
                gateway_id = gateway.get('gatewayId', 'Unknown')
                gateway_name = gateway.get('name', 'Unknown')
                
                # Get targets for the gateway
                targets = get_live_targets_for_gateway(bedrock_agentcore_client, gateway_id)
                
                # Display targets
                display_live_targets_for_gateway(config_manager, gateway_id, gateway_name, targets)
        
        print(f"\nListed targets from live AWS data")
        
    except Exception as e:
        logger.error(f"Operation failed: {str(e)}")
        print(f"\nOperation failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
