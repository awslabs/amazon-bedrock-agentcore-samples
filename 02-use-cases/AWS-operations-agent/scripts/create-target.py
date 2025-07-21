#!/usr/bin/env python3
"""
Create Bedrock AgentCore Gateway Target
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
    parser = argparse.ArgumentParser(description='Create Bedrock AgentCore Gateway Target')
    parser.add_argument('--gateway-id', help='Gateway ID (uses live gateway discovery if not specified)')
    parser.add_argument('--lambda-arn', help='Lambda ARN (uses config default if not specified)')
    parser.add_argument('--name', help='Target name (optional)')
    parser.add_argument('--description', help='Target description (optional)')
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

def get_live_gateways(bedrock_agentcore_client):
    """Get live gateways from AWS"""
    try:
        response = bedrock_agentcore_client.list_gateways()
        return response.get('items', [])
    except Exception as e:
        logger.error(f"Failed to get live gateways: {str(e)}")
        return []

def select_gateway(bedrock_agentcore_client, config_manager, gateway_id=None):
    """Select gateway to use for target creation"""
    
    if gateway_id:
        # Verify specified gateway exists
        try:
            response = bedrock_agentcore_client.get_gateway(gatewayIdentifier=gateway_id)
            gateway_info = {
                'gatewayId': gateway_id,
                'name': response.get('name', 'Unknown'),
                'status': response.get('status', 'Unknown')
            }
            print(f"Using specified gateway: {gateway_id}")
            return gateway_id, gateway_info
        except Exception as e:
            print(f"Gateway {gateway_id} not found: {str(e)}")
            return None, None
    
    # First, try to get gateway from config (active endpoint)
    try:
        config_gateway_id = config_manager.get_bedrock_agentcore_endpoints().get('gateway_id')
        config_gateway_url = config_manager.get_bedrock_agentcore_endpoints().get('gateway_url')
        
        if config_gateway_id:
            print(f"Found gateway in config: {config_gateway_id}")
            
            # Verify the gateway exists in AWS
            try:
                response = bedrock_agentcore_client.get_gateway(gatewayIdentifier=config_gateway_id)
                gateway_info = {
                    'gatewayId': config_gateway_id,
                    'name': response.get('name', 'Unknown'),
                    'status': response.get('status', 'Unknown'),
                    'gatewayUrl': config_gateway_url
                }
                print(f"✅ Using gateway from config: {config_gateway_id} ({gateway_info['name']}) - Status: {gateway_info['status']}")
                return config_gateway_id, gateway_info
            except Exception as e:
                print(f"⚠️  Gateway from config not found in AWS: {str(e)}")
                print("   Falling back to gateway discovery...")
        else:
            print("No gateway found in config, discovering available gateways...")
    except Exception as e:
        print(f"Error reading gateway from config: {str(e)}")
        print("Falling back to gateway discovery...")
    
    # Auto-discover gateways if config doesn't have one
    print(f"🔍 Discovering available gateways...")
    gateways = get_live_gateways(bedrock_agentcore_client)
    
    if not gateways:
        print(f"❌ No gateways found in AWS")
        print("   Create a gateway first using: python create-gateway.py")
        return None, None
    
    if len(gateways) == 1:
        gateway = gateways[0]
        gateway_id = gateway['gatewayId']
        print(f"✅ Using available gateway: {gateway_id} ({gateway.get('name', 'Unknown')})")
        return gateway_id, gateway
    
    # Multiple gateways - show options and use first one
    print(f"📋 Multiple gateways found:")
    for i, gw in enumerate(gateways, 1):
        print(f"   {i}. {gw['gatewayId']}: {gw.get('name', 'Unknown')} ({gw.get('status', 'Unknown')})")
    
    gateway = gateways[0]
    gateway_id = gateway['gatewayId']
    print(f"✅ Using first gateway: {gateway_id}")
    return gateway_id, gateway

def create_gateway_target(config_manager, environment, gateway_id, lambda_arn, target_name=None, description=None, endpoint_override=None):
    """Create Gateway Target using configuration"""
    
    # Get configuration
    aws_config = config_manager.get_aws_config(environment)
    endpoints = config_manager.get_bedrock_agentcore_endpoints(endpoint_override)
    lambda_target_config = config_manager.get_lambda_target_config(lambda_arn)
    credential_config = config_manager.get_credential_provider_config()
    tool_schemas = config_manager.get_tool_schemas()
    
    print(f"Using Configuration:")
    print(f"   Environment: {environment}")
    print(f"   AWS Profile: {aws_config['profile']}")
    print(f"   AWS Region: {aws_config['region']}")
    print(f"   AWS Account: {aws_config['account']}")
    print(f"   Bedrock AgentCore Endpoint: {endpoints['control_plane']}")
    print(f"   Available Tools: {len(tool_schemas)}")
    
    # Generate target name if not provided
    if not target_name:
        target_name = "bac-tool"  # Short name for Bedrock AgentCore tools (8 chars)
    
    if not description:
        description = f'AWS Resource Inspector Target for {environment} - {len(tool_schemas)} tools: hello_world, get_time, EC2, S3, Lambda, CloudFormation'
    
    # Create AWS session
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
        'name': target_name,
        'description': description,
        'targetConfiguration': lambda_target_config,
        'credentialProviderConfigurations': credential_config
    }
    
    print_request("CREATE TARGET REQUEST", request_data)
    
    try:
        # Create target
        response = bedrock_agentcore_client.create_gateway_target(**request_data)
        
        print_response("CREATE TARGET RESPONSE", response)
        
        target_id = response['targetId']
        target_status = response.get('status', 'Unknown')
        
        print(f"\nTarget Created Successfully!")
        print(f"   Target ID: {target_id}")
        print(f"   Status: {target_status}")
        print(f"   Gateway ID: {gateway_id}")
        print(f"   Lambda ARN: {lambda_arn}")
        print(f"   Tool Count: {len(tool_schemas)}")
        print(f"   Environment: {environment}")
        
        return target_id, response
        
    except Exception as e:
        logger.error(f"Target creation failed: {str(e)}")
        print(f"\nTarget creation failed: {str(e)}")
        raise

def main():
    """Main function"""
    args = parse_arguments()
    
    # Initialize configuration manager
    config_manager = BedrockAgentCoreConfigManager()
    
    # Use default environment from config
    environment = args.environment or config_manager.get_default_environment()
    
    # Use specified endpoint or default from config
    endpoint_override = args.endpoint + '_endpoints' if args.endpoint else None
    
    print("🚀 Create Bedrock AgentCore Gateway Target")
    print("=" * 45)
    print(f"Environment: {environment}")
    print(f"Endpoint: {args.endpoint or 'default'}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    try:
        # Validate configuration
        if not config_manager.validate_config():
            print("❌ Configuration validation failed")
            sys.exit(1)
        
        # Get configuration
        aws_config = config_manager.get_aws_config(environment)
        endpoints = config_manager.get_bedrock_agentcore_endpoints(endpoint_override)
        
        # Create AWS session
        session = boto3.Session(
            profile_name=aws_config['profile'],
            region_name=aws_config['region']
        )
        
        bedrock_agentcore_client = session.client(
            'bedrock-agentcore-control',
            endpoint_url=endpoints['control_plane']
        )
        
        # Select gateway (now uses config first)
        gateway_id, gateway_info = select_gateway(bedrock_agentcore_client, config_manager, args.gateway_id)
        if not gateway_id:
            sys.exit(1)
        
        # Determine Lambda ARN
        lambda_arn = args.lambda_arn or config_manager.get_lambda_arn(environment)
        
        print(f"\nTarget Configuration:")
        print(f"  Gateway ID: {gateway_id}")
        print(f"  Gateway Name: {gateway_info.get('name', 'Unknown')}")
        print(f"  Lambda ARN: {lambda_arn}")
        
        # Create target
        target_id, response = create_gateway_target(
            config_manager,
            environment,
            gateway_id,
            lambda_arn,
            args.name,
            args.description,
            endpoint_override
        )
        
        print(f"\n✅ Target creation completed successfully!")
        print(f"   Use 'python list-targets.py --gateway-id {gateway_id}' to see targets")
        print(f"   Use 'python get-target.py --gateway-id {gateway_id} --target-id {target_id}' for details")
        
    except Exception as e:
        logger.error(f"Operation failed: {str(e)}")
        print(f"\n❌ Operation failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
