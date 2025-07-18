#!/usr/bin/env python3
"""
List Bedrock AgentCore Gateways
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
    parser = argparse.ArgumentParser(description='List Bedrock AgentCore Gateways (Live Data from AWS)')
    parser.add_argument('--show-targets', action='store_true', help='Also show targets for each gateway')
    parser.add_argument("--endpoint", type=str, choices=["beta", "gamma", "production"], help="Endpoint to use (beta, gamma, production)")
    parser.add_argument("--environment", type=str, default=None, help="Environment to use (dev, gamma, prod)")
    return parser.parse_args()

def print_response(title, response_data):
    """Print formatted response"""
    print(f"\n{title}")
    print("=" * 60)
    print(json.dumps(response_data, indent=2, default=str))
    print("=" * 60)

def get_live_gateways(config_manager, environment, endpoint_override=None):
    """Get live gateways from AWS Bedrock AgentCore API"""
    
    # Get configuration for the specific environment
    aws_config = config_manager.get_aws_config(environment)
    endpoints = config_manager.get_bedrock_agentcore_endpoints(endpoint_override)
    
    print(f"Using Configuration:")
    print(f"   Environment: {environment}")
    print(f"   AWS Profile: {aws_config['profile']}")
    print(f"   AWS Region: {aws_config['region']}")
    print(f"   AWS Account: {aws_config['account']}")
    print(f"   Bedrock AgentCore Endpoint: {endpoints['control_plane']}")
    print(f"   Endpoint Type: {endpoint_override.replace('_endpoints', '') if endpoint_override else 'default'}")
    
    # Create AWS session with environment-specific profile and region
    session = boto3.Session(
        profile_name=aws_config['profile'],
        region_name=aws_config['region']
    )
    
    # Use the same client configuration that worked for creating gateways
    bedrock_agentcore_client = session.client(
        'bedrock-agentcore-control', 
        region_name=aws_config['region'], 
        endpoint_url=endpoints['control_plane']
    )
    
    try:
        print(f"\nFetching live gateways from AWS Bedrock AgentCore API...")
        
        # List gateways from AWS
        response = bedrock_agentcore_client.list_gateways()
        
        print_response("LIST GATEWAYS RESPONSE (LIVE DATA)", response)
        
        gateways = response.get('items', [])
        
        print(f"\nLive Data Summary:")
        print(f"   Total Gateways: {len(gateways)}")
        
        return gateways, bedrock_agentcore_client
        
    except Exception as e:
        logger.error(f"Failed to fetch live gateways from AWS: {str(e)}")
        print(f"\nFailed to fetch live gateways from AWS: {str(e)}")
        print(f"   Check AWS profile '{aws_config['profile']}' and region '{aws_config['region']}'")
        return [], None

def get_live_targets_for_gateway(bedrock_agentcore_client, gateway_id):
    """Get live targets for a specific gateway"""
    
    try:
        response = bedrock_agentcore_client.list_gateway_targets(gatewayIdentifier=gateway_id)
        targets = response.get('items', [])
        return targets
        
    except Exception as e:
        logger.error(f"Failed to get targets for gateway {gateway_id}: {str(e)}")
        return []

def display_live_gateways(config_manager, gateways, bedrock_agentcore_client, show_targets=False):
    """Display live gateway information"""
    
    if not gateways:
        print(f"\nNo gateways found in AWS")
        return
    
    print(f"\nLive Gateways from AWS:")
    print("=" * 60)
    
    for i, gateway in enumerate(gateways, 1):
        gateway_id = gateway.get('gatewayId', 'Unknown')
        # Generate MCP endpoint URL using config manager
        mcp_endpoint = config_manager.get_mcp_endpoint_url(gateway_id)
        
        print(f"\n{i}. Gateway ID: {gateway_id}")
        print(f"   Name: {gateway.get('name', 'Unknown')}")
        print(f"   Status: {gateway.get('status', 'Unknown')}")
        print(f"   Protocol: {gateway.get('protocolType', 'Unknown')}")
        print(f"   Authorizer: {gateway.get('authorizerType', 'Unknown')}")
        print(f"   Role ARN: {gateway.get('roleArn', 'Unknown')}")
        print(f"   MCP Endpoint: {mcp_endpoint}")
        print(f"   Description: {gateway.get('description', 'None')}")
        print(f"   Created: {gateway.get('createdAt', 'Unknown')}")
        print(f"   Updated: {gateway.get('updatedAt', 'Unknown')}")
        
        # Show targets if requested
        if show_targets and bedrock_agentcore_client:
            print(f"   \n   Fetching targets...")
            targets = get_live_targets_for_gateway(bedrock_agentcore_client, gateway_id)
            
            if targets:
                print(f"   Targets ({len(targets)}):")
                for j, target in enumerate(targets, 1):
                    target_id = target.get('targetId', 'Unknown')
                    print(f"     {j}. Target ID: {target_id}")
                    print(f"        Name: {target.get('name', 'Unknown')}")
                    print(f"        Status: {target.get('status', 'Unknown')}")
                    print(f"        Created: {target.get('createdAt', 'Unknown')}")
                    
                    # Try to extract tool count from target configuration
                    target_config = target.get('targetConfiguration', {})
                    if 'mcp' in target_config and 'lambda' in target_config['mcp']:
                        lambda_config = target_config['mcp']['lambda']
                        tool_schema = lambda_config.get('toolSchema', {})
                        if 'inlinePayload' in tool_schema:
                            tools = tool_schema['inlinePayload']
                            print(f"        Tools: {len(tools)}")
                            tool_names = [tool.get('name', 'unknown') for tool in tools[:3]]
                            if len(tools) > 3:
                                tool_names.append('...')
                            print(f"        Tool Names: {', '.join(tool_names)}")
            else:
                print(f"   Targets: None")

def main():
    """Main function"""
    args = parse_arguments()
    
    # Initialize configuration manager
    config_manager = BedrockAgentCoreConfigManager()
    
    # Use specified environment or default from config
    environment = args.environment or config_manager.get_default_environment()
    
    # Use specified endpoint or default from config
    endpoint_override = args.endpoint + '_endpoints' if args.endpoint else None
    
    print("List Bedrock AgentCore Gateways (Live Data)")
    print("=" * 45)
    print(f"Environment: {environment}")
    print(f"Endpoint: {args.endpoint or 'default'}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Data Source: AWS Bedrock AgentCore API (Live)")
    
    try:
        # Validate configuration
        if not config_manager.validate_config():
            print("Configuration validation failed")
            sys.exit(1)
        
        # Get live gateways from AWS
        live_gateways, bedrock_agentcore_client = get_live_gateways(config_manager, environment, endpoint_override)
        
        if not live_gateways:
            print("\nNo gateways found in AWS")
            print("   Create a gateway using: python create-gateway.py")
            sys.exit(0)
        
        # Display live gateway information
        display_live_gateways(config_manager, live_gateways, bedrock_agentcore_client, args.show_targets)
        
        print(f"\nListed {len(live_gateways)} gateways from live AWS data")
        
    except Exception as e:
        logger.error(f"Operation failed: {str(e)}")
        print(f"\nOperation failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
