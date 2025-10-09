#!/usr/bin/env python3
"""
AgentCore Identity Setup for Insurance Agent

This script sets up AgentCore Identity components:
1. Workload Identity for the insurance agent (Inbound)
2. OAuth2 Credential Provider for MCP Gateway access (Outbound)
3. API Key Credential Provider for Insurance API (Outbound)

Run this script once to set up identity infrastructure.
"""

import os
import json
import logging
from dotenv import load_dotenv
from bedrock_agentcore.services.identity import IdentityClient

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("IdentitySetup")

def get_account_id():
    """Get AWS account ID"""
    import boto3
    sts = boto3.client('sts')
    return sts.get_caller_identity()['Account']

def setup_identity_infrastructure():
    """Set up all identity components for the insurance agent"""
    
    # Get AWS region from environment
    aws_region = os.getenv("AWS_REGION", "us-east-1")
    logger.info(f"Setting up Identity infrastructure in region: {aws_region}")
    
    # Initialize Identity client
    identity_client = IdentityClient(aws_region)
    
    # =========================================================================
    # PHASE 2: INBOUND IDENTITY - Create Workload Identity for the agent
    # =========================================================================
    logger.info("\n=== Phase 2: Creating Workload Identity ===")
    
    try:
        workload_identity = identity_client.create_workload_identity(
            name="insurance-agent-workload"
        )
        
        logger.info(f"✓ Workload Identity created successfully")
        logger.info(f"  ARN: {workload_identity['workloadIdentityArn']}")
        logger.info(f"  Name: {workload_identity['name']}")
        
        workload_identity_arn = workload_identity['workloadIdentityArn']
        # Use the name as the ID (the API doesn't return a separate ID field)
        workload_identity_id = workload_identity['name']
        
    except KeyError as e:
        logger.error(f"Missing expected field in workload identity response: {str(e)}")
        logger.error(f"Available fields: {list(workload_identity.keys())}")
        raise
    except Exception as e:
        error_msg = str(e)
        # Check if identity already exists
        if "already exists" in error_msg:
            logger.warning(f"Workload identity 'insurance-agent-workload' already exists")
            logger.info("Retrieving existing workload identity...")
            
            # Get the existing identity using boto3 directly
            try:
                import boto3
                client = boto3.client('bedrock-agentcore-control', region_name=aws_region)
                response = client.get_workload_identity(name='insurance-agent-workload')
                
                workload_identity_arn = response['workloadIdentityArn']
                workload_identity_id = response['name']
                
                logger.info(f"✓ Using existing Workload Identity")
                logger.info(f"  ARN: {workload_identity_arn}")
                logger.info(f"  Name: {workload_identity_id}")
            except Exception as get_error:
                logger.error(f"Failed to retrieve existing workload identity: {str(get_error)}")
                logger.info("\nTo delete the existing identity, run:")
                logger.info(f"  python -c \"import boto3; boto3.client('bedrock-agentcore-control', region_name='{aws_region}').delete_workload_identity(name='insurance-agent-workload'); print('✓ Deleted')\"")
                raise
        else:
            logger.error(f"Failed to create workload identity: {error_msg}")
            raise
    
    # =========================================================================
    # PHASE 1: OUTBOUND IDENTITY - Create OAuth2 Credential Provider
    # =========================================================================
    logger.info("\n=== Phase 1: Creating OAuth2 Credential Provider for MCP Gateway ===")
    
    # Load gateway info to get OAuth2 credentials
    gateway_info_file = os.getenv("GATEWAY_INFO_FILE", "../cloud_mcp_server/gateway_info.json")
    
    try:
        with open(gateway_info_file, 'r') as f:
            gateway_info = json.load(f)
        
        client_id = gateway_info['auth']['client_id']
        client_secret = gateway_info['auth']['client_secret']
        token_endpoint = gateway_info['auth']['token_endpoint']
        
        logger.info(f"Loaded gateway OAuth2 configuration from {gateway_info_file}")
        
    except FileNotFoundError:
        logger.error(f"Gateway info file not found: {gateway_info_file}")
        logger.error("Please run the MCP gateway setup first")
        raise
    except KeyError as e:
        logger.error(f"Missing required field in gateway info: {e}")
        raise
    
    # Note: AgentCore Identity currently supports specific OAuth2 providers
    # For custom OAuth2 (like Cognito), we'll document the pattern but may need
    # to use the token directly until custom OAuth2 provider support is added
    
    logger.info("Note: Using Cognito OAuth2 - storing configuration for reference")
    logger.info(f"  Token Endpoint: {token_endpoint}")
    logger.info(f"  Client ID: {client_id}")
    
    # =========================================================================
    # PHASE 1: OUTBOUND IDENTITY - Create API Key Credential Provider
    # =========================================================================
    logger.info("\n=== Phase 1: Creating API Key Credential Provider for Insurance API ===")
    
    # Get API key from environment or gateway info
    api_key = os.getenv("API_KEY")
    if not api_key and 'api' in gateway_info and 'credentials' in gateway_info['api']:
        # Try to extract from gateway info if available
        logger.info("API key not in environment, will be configured separately")
    
    if api_key:
        try:
            api_key_provider = identity_client.create_api_key_credential_provider(req={
                "name": "InsuranceAPIKeyProvider",
                "apiKey": api_key
            })
            
            logger.info(f"✓ API Key Credential Provider created successfully")
            logger.info(f"  Provider ARN: {api_key_provider['credentialProviderArn']}")
            logger.info(f"  Provider Name: {api_key_provider['name']}")
            
            api_key_provider_name = api_key_provider['name']
            api_key_provider_arn = api_key_provider['credentialProviderArn']
            
        except Exception as e:
            error_msg = str(e)
            # Check if provider already exists
            if "already exists" in error_msg:
                logger.warning(f"API Key Provider 'InsuranceAPIKeyProvider' already exists")
                logger.info("Using existing API Key Provider")
                
                # Use the existing provider
                api_key_provider_name = "InsuranceAPIKeyProvider"
                # Construct the ARN (we don't have a get method, so we construct it)
                api_key_provider_arn = f"arn:aws:bedrock-agentcore:{aws_region}:{get_account_id()}:credential-provider/InsuranceAPIKeyProvider"
                
                logger.info(f"✓ Using existing API Key Credential Provider")
                logger.info(f"  Provider Name: {api_key_provider_name}")
            else:
                logger.error(f"Failed to create API key provider: {error_msg}")
                raise
    else:
        logger.warning("API_KEY not found in environment. Skipping API key provider creation.")
        logger.warning("Set API_KEY in .env file and re-run to create the provider.")
        api_key_provider_name = None
        api_key_provider_arn = None
    
    # =========================================================================
    # Save Identity Configuration
    # =========================================================================
    logger.info("\n=== Saving Identity Configuration ===")
    
    identity_config = {
        "workload_identity": {
            "arn": workload_identity_arn,
            "id": workload_identity_id,
            "name": "insurance-agent-workload"
        },
        "oauth2_provider": {
            "type": "cognito",
            "client_id": client_id,
            "token_endpoint": token_endpoint,
            "note": "Using Cognito OAuth2 - tokens managed via gateway_info.json"
        },
        "api_key_provider": {
            "name": api_key_provider_name,
            "arn": api_key_provider_arn
        } if api_key else None,
        "region": aws_region
    }
    
    # Save to file
    identity_config_file = "identity_config.json"
    with open(identity_config_file, 'w') as f:
        json.dump(identity_config, f, indent=2)
    
    logger.info(f"✓ Identity configuration saved to {identity_config_file}")
    
    # =========================================================================
    # Update .env file with identity information
    # =========================================================================
    logger.info("\n=== Updating .env file ===")
    
    env_additions = f"""
# =============================================================================
# AgentCore Identity Configuration (Auto-generated)
# =============================================================================
# WORKLOAD_IDENTITY_ARN: ARN of the workload identity for this agent
WORKLOAD_IDENTITY_ARN={workload_identity_arn}

# WORKLOAD_IDENTITY_ID: ID of the workload identity
WORKLOAD_IDENTITY_ID={workload_identity_id}
"""
    
    if api_key_provider_name:
        env_additions += f"""
# API_KEY_PROVIDER_NAME: Name of the API key credential provider
API_KEY_PROVIDER_NAME={api_key_provider_name}
"""
    
    logger.info("Add the following to your .env file:")
    logger.info(env_additions)
    
    # =========================================================================
    # Summary
    # =========================================================================
    logger.info("\n" + "="*80)
    logger.info("IDENTITY SETUP COMPLETE")
    logger.info("="*80)
    logger.info("\nPhase 1 (Outbound Identity):")
    logger.info(f"  ✓ OAuth2 configuration documented (using Cognito)")
    if api_key_provider_name:
        logger.info(f"  ✓ API Key Provider created: {api_key_provider_name}")
    else:
        logger.info(f"  ⚠ API Key Provider not created (set API_KEY in .env)")
    
    logger.info("\nPhase 2 (Inbound Identity):")
    logger.info(f"  ✓ Workload Identity created: {workload_identity_arn}")
    
    logger.info("\nNext Steps:")
    logger.info("1. Update your .env file with the values shown above")
    logger.info("2. The agent code will automatically use these identity components")
    logger.info("3. Test the agent with: agentcore invoke --bearer-token $BEARER_TOKEN '{\"user_input\": \"test\"}'")
    
    return identity_config

if __name__ == "__main__":
    try:
        config = setup_identity_infrastructure()
        print("\n✓ Identity setup completed successfully!")
    except Exception as e:
        logger.error(f"\n✗ Identity setup failed: {str(e)}")
        exit(1)
