#!/usr/bin/env python3
"""
Delete Bedrock AgentCore Gateway
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
    parser = argparse.ArgumentParser(description='Delete Bedrock AgentCore Gateway')
    parser.add_argument('--gateway-id', required=True, help='Gateway ID to delete')
    parser.add_argument('--force', action='store_true', help='Skip confirmation prompt')
    parser.add_argument('--delete-targets', action='store_true', help='Delete all targets first')
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
    """Get gateway information from AWS"""
    try:
        response = bedrock_agentcore_client.get_gateway(gatewayIdentifier=gateway_id)
        return response
    except Exception as e:
        logger.error(f"Failed to get gateway info: {str(e)}")
        return None

def get_gateway_targets(bedrock_agentcore_client, gateway_id):
    """Get all targets for a gateway from AWS"""
    try:
        response = bedrock_agentcore_client.list_gateway_targets(gatewayIdentifier=gateway_id)
        return response.get('targets', [])
    except Exception as e:
        logger.error(f"Failed to get gateway targets: {str(e)}")
        return []

def confirm_deletion(gateway_info, targets):
    """Confirm gateway deletion with user"""
    
    print(f"\nGateway Deletion Confirmation")
    print("=" * 40)
    print(f"Gateway ID: {gateway_info.get('gatewayId', 'Unknown')}")
    print(f"Gateway Name: {gateway_info.get('name', 'Unknown')}")
    print(f"Status: {gateway_info.get('status', 'Unknown')}")
    print(f"MCP Endpoint: {gateway_info.get('mcpEndpoint', 'Unknown')}")
    print(f"Role ARN: {gateway_info.get('roleArn', 'Unknown')}")
    print(f"Targets: {len(targets)}")
    print(f"Created: {gateway_info.get('createdAt', 'Unknown')}")
    print(f"Updated: {gateway_info.get('updatedAt', 'Unknown')}")
    
    if targets:
        print(f"\nTargets that will be affected:")
        for target in targets:
            target_id = target.get('targetId', 'Unknown')
            target_name = target.get('name', 'Unknown')
            target_status = target.get('status', 'Unknown')
            print(f"  - {target_id}: {target_name} (Status: {target_status})")
    
    print()
    print("This action cannot be undone!")
    print("All targets and tools will become inaccessible!")
    print()
    
    confirmation = input("Type 'DELETE' to confirm gateway deletion: ").strip()
    
    if confirmation != 'DELETE':
        print("Deletion cancelled")
        return False
    
    return True

def delete_all_targets(bedrock_agentcore_client, gateway_id, targets):
    """Delete all targets from gateway"""
    
    if not targets:
        return True
    
    print(f"\nDeleting {len(targets)} targets first...")
    
    deleted_targets = []
    failed_targets = []
    
    for target in targets:
        target_id = target.get('targetId')
        target_name = target.get('name', 'Unknown')
        
        try:
            print(f"   Deleting target {target_id} ({target_name})...")
            
            request_data = {
                'gatewayIdentifier': gateway_id,
                'targetId': target_id
            }
            
            response = bedrock_agentcore_client.delete_gateway_target(**request_data)
            deleted_targets.append(target_id)
            print(f"   Target {target_id} deleted")
            
        except Exception as e:
            failed_targets.append((target_id, str(e)))
            print(f"   Failed to delete target {target_id}: {str(e)}")
    
    if failed_targets:
        print(f"\nFailed to delete {len(failed_targets)} targets:")
        for target_id, error in failed_targets:
            print(f"   - {target_id}: {error}")
        
        proceed = input("\nProceed with gateway deletion anyway? (y/N): ").strip().lower()
        if proceed != 'y':
            return False
    
    return True

def delete_bedrock_agentcore_gateway(config_manager, environment, gateway_id, force=False, delete_targets=False):
    """Delete Bedrock AgentCore Gateway using configuration"""
    
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
    
    # Get gateway information from AWS
    print(f"\nRetrieving gateway information from AWS...")
    gateway_info = get_gateway_info(bedrock_agentcore_client, gateway_id)
    if not gateway_info:
        print(f"Gateway {gateway_id} not found")
        return False
    
    # Get targets from AWS
    targets = get_gateway_targets(bedrock_agentcore_client, gateway_id)
    
    # Confirm deletion unless forced
    if not force:
        if not confirm_deletion(gateway_info, targets):
            return False
    
    # Delete targets first if requested or if they exist
    if targets and (delete_targets or not force):
        if not delete_all_targets(bedrock_agentcore_client, gateway_id, targets):
            print("Cannot proceed with gateway deletion due to target deletion failures")
            return False
    
    # Prepare request
    request_data = {
        'gatewayIdentifier': gateway_id
    }
    
    print_request("DELETE GATEWAY REQUEST", request_data)
    
    try:
        # Delete gateway
        response = bedrock_agentcore_client.delete_gateway(**request_data)
        
        print_response("DELETE GATEWAY RESPONSE", response)
        
        print(f"\nGateway Deleted Successfully!")
        print(f"   Gateway ID: {gateway_id}")
        print(f"   Environment: {environment}")
        print(f"   Targets Deleted: {len(targets)}")
        
        # Clear gateway info from config after successful deletion
        config_manager.clear_gateway_info(gateway_id)
        
        return True
        
    except Exception as e:
        logger.error(f"Gateway deletion failed: {str(e)}")
        print(f"\nGateway deletion failed: {str(e)}")
        
        # Check if it's a targets-still-exist error
        if "targets" in str(e).lower() or "in use" in str(e).lower():
            print("\nTip: Use --delete-targets to automatically delete all targets first")
        
        return False

def main():
    """Main function"""
    args = parse_arguments()
    
    # Initialize configuration manager
    config_manager = BedrockAgentCoreConfigManager()
    
    # Use default environment from config
    environment = config_manager.get_default_environment()
    
    print("Delete Bedrock AgentCore Gateway")
    print("=" * 40)
    print(f"Environment: {environment}")
    print(f"Gateway ID: {args.gateway_id}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    try:
        # Validate configuration
        if not config_manager.validate_config():
            print("Configuration validation failed")
            sys.exit(1)
        
        # Delete gateway
        success = delete_bedrock_agentcore_gateway(
            config_manager,
            environment,
            args.gateway_id,
            args.force,
            args.delete_targets
        )
        
        if success:
            print(f"\nGateway deletion completed successfully!")
            print(f"   Use 'python list-gateways.py' to see remaining gateways")
        else:
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"Operation failed: {str(e)}")
        print(f"\nOperation failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
