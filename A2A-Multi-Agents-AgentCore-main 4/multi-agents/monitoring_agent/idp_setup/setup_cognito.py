#!/usr/bin/env python3
"""
Script to set up Cognito User Pool for Monitoring Agent

This script creates a Cognito User Pool with authentication configuration
for the monitoring agent using the utility functions from utils.py.
"""
import sys
import json
import boto3
import logging
from pathlib import Path
from typing import Dict, Optional

# Import utility functions from parent directory
sys.path.append(str(Path(__file__).parent.parent))
from utils import (
    setup_cognito_user_pool,
    get_or_create_user_pool,
    get_or_create_resource_server,
    get_or_create_m2m_client,
    create_cognito_domain
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)
logger = logging.getLogger(__name__)

# Configuration for user pool, resource server and M2M client
USER_POOL_NAME = "monitoring-agentcore-gateway-pool"
RESOURCE_SERVER_ID = "monitoring-agentcore-gateway-id"
RESOURCE_SERVER_NAME = "monitoring-agentcore-gateway-name"
CLIENT_NAME = "monitoring-agentcore-gateway-client"
SCOPES = [
    {"ScopeName": "gateway:read", "ScopeDescription": "Read access"},
    {"ScopeName": "gateway:write", "ScopeDescription": "Write access"}
]


def save_cognito_config(
    cognito_config: Dict[str, str],
    output_file: str = "cognito_config.json"
) -> bool:
    """
    Save Cognito configuration to a JSON file
    
    Args:
        cognito_config: Dictionary containing Cognito configuration
        output_file: Path to output file
        
    Returns:
        bool: True if saved successfully, False otherwise
    """
    try:
        config_path = Path(output_file)
        logger.info(f"Saving Cognito configuration to {config_path}")
        
        with open(config_path, 'w') as f:
            json.dump(cognito_config, f, indent=2)
        
        logger.info(f"Successfully saved configuration to {config_path}")
        return True
    except Exception as e:
        logger.error(f"Error saving configuration: {e}")
        return False


def main():
    """
    Main function to set up Cognito User Pool for monitoring agent
    """
    logger.info("Starting Cognito User Pool setup for the monitoring Agent")
    
    try:
        # Get AWS session and region
        boto_session = boto3.session.Session()
        region = boto_session.region_name
        logger.info(f"Using AWS region: {region}")
        
        # Set up Cognito User Pool
        logger.info("Creating Cognito User Pool...")
        cognito = boto3.client("cognito-idp", region_name=region)
        
        # Use the simpler setup_cognito_user_pool function
        cognito_config = setup_cognito_user_pool()
        
        if cognito_config is None:
            logger.error("Failed to create Cognito User Pool")
            sys.exit(1)
            
        user_pool_id = cognito_config['pool_id']
        logger.info(f"Created User Pool ID: {user_pool_id}")

        # Create domain for the user pool
        logger.info("Creating/checking Cognito domain...")
        domain_info = create_cognito_domain(user_pool_id, region=region)
        cognito_config['domain'] = domain_info['domain']
        cognito_config['domain_url'] = domain_info['domain_url']
        logger.info(f"Domain: {domain_info['domain']} ({domain_info['status']})")

        # Create resource server
        logger.info("Creating resource server...")
        get_or_create_resource_server(cognito, user_pool_id, RESOURCE_SERVER_ID, RESOURCE_SERVER_NAME, SCOPES)
        logger.info("Resource server ensured.")
        
        # Create M2M client
        logger.info("Creating M2M client...")
        client_id, client_secret = get_or_create_m2m_client(cognito, user_pool_id, CLIENT_NAME, RESOURCE_SERVER_ID)
        logger.info(f"M2M Client ID: {client_id}")
        
        # Add M2M client info to config
        cognito_config['m2m_client_id'] = client_id
        cognito_config['m2m_client_secret'] = client_secret
        cognito_config['resource_server_id'] = RESOURCE_SERVER_ID
        
        logger.info("✅ Successfully created Cognito User Pool")
        
        # Display the configuration
        logger.info("Cognito Configuration:")
        logger.info(f"Pool ID: {cognito_config['pool_id']}")
        logger.info(f"Client ID: {cognito_config['client_id']}")
        logger.info(f"Discovery URL: {cognito_config['discovery_url']}")
        logger.info(f"Bearer Token: {cognito_config['bearer_token'][:20]}...")
        
        # Save configuration to file
        if save_cognito_config(cognito_config):
            logger.info("✅ Configuration saved to cognito_config.json")
        else:
            logger.warning("⚠️ Failed to save configuration to file")
        
        # Print usage information
        print("\n" + "="*60)
        print("COGNITO SETUP COMPLETE")
        print("="*60)
        print(f"Pool ID: {cognito_config['pool_id']}")
        print(f"Domain: {cognito_config.get('domain', 'N/A')}")
        print(f"Domain URL: {cognito_config.get('domain_url', 'N/A')}")
        print(f"Client ID: {cognito_config['client_id']}")
        print(f"Discovery URL: {cognito_config['discovery_url']}")
        print(f"Username: testuser")
        print(f"Password: MyPassword123!")
        if 'm2m_client_id' in cognito_config:
            print(f"M2M Client ID: {cognito_config['m2m_client_id']}")
            print(f"M2M Client Secret: {cognito_config['m2m_client_secret'][:10]}...")
        print("="*60)
        print("Use these credentials to authenticate with the monitoring agent")
        print("Configuration has been saved to cognito_config.json")
        print("="*60)
        
    except Exception as e:
        logger.error(f"Error during Cognito setup: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()