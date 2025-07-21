#!/usr/bin/env python3
"""
Update Bedrock AgentCore Gateway Target
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
    parser = argparse.ArgumentParser(description='Update Bedrock AgentCore Gateway Target')
    parser.add_argument('--gateway-id', required=True, help='Gateway ID')
    parser.add_argument('--target-id', required=True, help='Target ID to update')
    parser.add_argument('--name', help='New target name')
    parser.add_argument('--description', help='New target description')
    parser.add_argument('--lambda-arn', help='New Lambda function ARN')
    parser.add_argument('--tools-file', help='Path to JSON file containing updated tool schemas')
    parser.add_argument('--show-current', action='store_true', help='Show current target configuration')
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
    """Get current target information from AWS"""
    try:
        response = bedrock_agentcore_client.get_gateway_target(
            gatewayIdentifier=gateway_id,
            targetId=target_id
        )
        return response
    except Exception as e:
        logger.error(f"Failed to get target info: {str(e)}")
        return None

def print_target_info(target_info):
    """Print formatted target information"""
    print(f"\nCurrent Target Configuration")
    print("=" * 50)
    print(f"Target ID: {target_info.get('targetId', 'Unknown')}")
    print(f"Name: {target_info.get('name', 'Unknown')}")
    print(f"Description: {target_info.get('description', 'None')}")
    print(f"Status: {target_info.get('status', 'Unknown')}")
    print(f"Created: {target_info.get('createdAt', 'Unknown')}")
    print(f"Updated: {target_info.get('updatedAt', 'Unknown')}")
    
    # Extract configuration details
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
            
            # Show tool details
            print(f"\nTool Details:")
            for i, tool in enumerate(tools, 1):
                print(f"  {i}. {tool.get('name', 'unknown')}")
                print(f"     Description: {tool.get('description', 'None')}")
                if 'inputSchema' in tool:
                    properties = tool['inputSchema'].get('properties', {})
                    print(f"     Parameters: {len(properties)} ({', '.join(properties.keys())})")

def load_tools_from_file(tools_file_path):
    """Load tool schemas from JSON file"""
    try:
        with open(tools_file_path, 'r') as f:
            tools_data = json.load(f)
        
        # Validate that it's a list of tools
        if not isinstance(tools_data, list):
            raise ValueError("Tools file must contain a JSON array of tool objects")
        
        # Basic validation of tool structure
        for i, tool in enumerate(tools_data):
            if not isinstance(tool, dict):
                raise ValueError(f"Tool {i+1} must be an object")
            if 'name' not in tool:
                raise ValueError(f"Tool {i+1} missing required 'name' field")
            if 'description' not in tool:
                raise ValueError(f"Tool {i+1} missing required 'description' field")
        
        return tools_data
        
    except FileNotFoundError:
        raise ValueError(f"Tools file not found: {tools_file_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in tools file: {str(e)}")

def confirm_update(target_info, updates):
    """Confirm target update with user"""
    
    print(f"\nTarget Update Confirmation")
    print("=" * 40)
    print(f"Target ID: {target_info.get('targetId', 'Unknown')}")
    print(f"Current Name: {target_info.get('name', 'Unknown')}")
    
    print(f"\nProposed Changes:")
    for field, new_value in updates.items():
        if field in ['gatewayIdentifier', 'targetId']:
            continue
        
        if field == 'targetConfiguration':
            print(f"  Target Configuration: Updated (see request details above)")
        else:
            current_value = target_info.get(field, 'None')
            print(f"  {field}: '{current_value}' → '{new_value}'")
    
    print()
    confirmation = input("Proceed with target update? (y/N): ").strip().lower()
    
    if confirmation != 'y':
        print("Update cancelled")
        return False
    
    return True

def update_bedrock_agentcore_target(config_manager, environment, gateway_id, target_id, updates, show_current=False):
    """Update Bedrock AgentCore Gateway Target using configuration"""
    
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
        endpoint_url=endpoints['control_plane']
    )
    
    # Get current target information
    print(f"\nRetrieving current target information...")
    target_info = get_target_info(bedrock_agentcore_client, gateway_id, target_id)
    
    if not target_info:
        print(f"Target {target_id} not found in gateway {gateway_id}")
        return False
    
    # Show current configuration if requested
    if show_current:
        print_target_info(target_info)
        return True
    
    # If no updates provided, show current info and exit
    if not updates or len(updates) == 2:  # Only gatewayIdentifier and targetId
        print("No updates specified. Current target configuration:")
        print_target_info(target_info)
        print("\nUse --name, --description, --lambda-arn, or --tools-file to specify updates")
        return True
    
    # Confirm update
    if not confirm_update(target_info, updates):
        return False
    
    print_request("UPDATE TARGET REQUEST", updates)
    
    try:
        # Update target
        response = bedrock_agentcore_client.update_gateway_target(**updates)
        
        print_response("UPDATE TARGET RESPONSE", response)
        
        print(f"\nTarget Updated Successfully!")
        print(f"   Target ID: {target_id}")
        print(f"   Gateway ID: {gateway_id}")
        print(f"   Environment: {environment}")
        
        # Show updated configuration
        print(f"\nRetrieving updated target information...")
        updated_target_info = get_target_info(bedrock_agentcore_client, gateway_id, target_id)
        if updated_target_info:
            print_target_info(updated_target_info)
        
        return True
        
    except Exception as e:
        logger.error(f"Target update failed: {str(e)}")
        print(f"\nTarget update failed: {str(e)}")
        return False

def main():
    """Main function"""
    args = parse_arguments()
    
    # Initialize configuration manager
    config_manager = BedrockAgentCoreConfigManager()
    
    # Use default environment from config
    environment = config_manager.get_default_environment()
    
    print("Update Bedrock AgentCore Gateway Target")
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
        
        # Build updates dictionary
        updates = {
            'gatewayIdentifier': args.gateway_id,
            'targetId': args.target_id
        }
        
        # Add basic field updates
        if args.name:
            updates['name'] = args.name
        if args.description:
            updates['description'] = args.description
        
        # Handle target configuration updates
        target_config_updates = {}
        
        if args.lambda_arn or args.tools_file:
            # Get current target info to preserve existing configuration
            aws_config = config_manager.get_aws_config(environment)
            endpoints = config_manager.get_bedrock_agentcore_endpoints()
            
            session = boto3.Session(
                profile_name=aws_config['profile'],
                region_name=aws_config['region']
            )
            
            bedrock_agentcore_client = session.client(
                'bedrock-agentcore-control',
                endpoint_url=endpoints['control_plane']
            )
            
            current_target = get_target_info(bedrock_agentcore_client, args.gateway_id, args.target_id)
            if not current_target:
                print(f"Cannot retrieve current target configuration")
                sys.exit(1)
            
            # Start with current configuration
            current_config = current_target.get('targetConfiguration', {})
            target_config_updates = json.loads(json.dumps(current_config))  # Deep copy
            
            # Update Lambda ARN if provided
            if args.lambda_arn:
                if 'mcp' not in target_config_updates:
                    target_config_updates['mcp'] = {}
                if 'lambda' not in target_config_updates['mcp']:
                    target_config_updates['mcp']['lambda'] = {}
                target_config_updates['mcp']['lambda']['lambdaArn'] = args.lambda_arn
            
            # Update tools if provided
            if args.tools_file:
                try:
                    tools = load_tools_from_file(args.tools_file)
                    print(f"📁 Loaded {len(tools)} tools from {args.tools_file}")
                    
                    if 'mcp' not in target_config_updates:
                        target_config_updates['mcp'] = {}
                    if 'lambda' not in target_config_updates['mcp']:
                        target_config_updates['mcp']['lambda'] = {}
                    if 'toolSchema' not in target_config_updates['mcp']['lambda']:
                        target_config_updates['mcp']['lambda']['toolSchema'] = {}
                    
                    target_config_updates['mcp']['lambda']['toolSchema']['inlinePayload'] = tools
                    
                except ValueError as e:
                    print(f"Error loading tools file: {str(e)}")
                    sys.exit(1)
            
            updates['targetConfiguration'] = target_config_updates
        
        # Update target
        success = update_bedrock_agentcore_target(
            config_manager,
            environment,
            args.gateway_id,
            args.target_id,
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
