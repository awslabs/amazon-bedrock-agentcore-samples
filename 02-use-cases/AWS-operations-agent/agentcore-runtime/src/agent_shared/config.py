# ============================================================================
# IMPORTS
# ============================================================================

import os
import yaml
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION LOADING
# ============================================================================

def load_configs():
    """
    Load configuration using unified AgentCore configuration system.
    
    Returns:
        tuple: (merged_config, okta_config) - Two dictionaries with config data
    """
    try:
        # Import the unified config manager
        import sys
        import os
        
        # In Docker container, config_manager is in /app/shared/
        # No need to manipulate path since it's in the same shared directory structure
        from shared.config_manager import AgentCoreConfigManager
        
        # Initialize config manager
        config_manager = AgentCoreConfigManager()
        
        # Get merged configuration (static + dynamic)
        merged_config = config_manager.get_merged_config()
        
        # Get OAuth settings
        okta_config = config_manager.get_oauth_settings()
        
        logger.info("✅ Loaded configuration using unified AgentCore config system")
        return merged_config, okta_config
        
    except Exception as e:
        logger.error(f"❌ Failed to load unified configuration: {e}")
        # Fallback to empty configs
        return {}, {}

# ============================================================================
# MODEL SETTINGS
# ============================================================================

def get_model_settings():
    """
    Get the model settings for Strands.
    
    Returns:
        dict: Model configuration with region, model_id, temperature, max_tokens
    """
    agentcore_config, _ = load_configs()
    
    # Default values
    defaults = {
        'region_name': 'us-east-1',
        'model_id': 'anthropic.claude-3-5-sonnet-20241022-v2:0',
        'temperature': 0.7,
        'max_tokens': 4096
    }
    
    try:
        # Extract from config
        aws_config = agentcore_config.get('aws', {})
        agents_config = agentcore_config.get('agents', {})
        
        model_settings = {
            'region_name': aws_config.get('region', defaults['region_name']),
            'model_id': agents_config.get('modelid', defaults['model_id']),
            'temperature': defaults['temperature'],  # Use default for now
            'max_tokens': defaults['max_tokens']     # Use default for now
        }
        
        logger.info(f"📋 Model settings: {model_settings}")
        return model_settings
        
    except Exception as e:
        logger.error(f"❌ Failed to get model settings: {e}")
        logger.info(f"🔄 Using default model settings: {defaults}")
        return defaults

# ============================================================================
# OAUTH SETTINGS
# ============================================================================

def get_oauth_settings():
    """
    Get OAuth provider settings.
    
    Returns:
        dict: OAuth provider configuration
    """
    agentcore_config, okta_config = load_configs()
    
    try:
        # Get OAuth provider name from agentcore config
        oauth_config = agentcore_config.get('oauth', {})
        provider_name = oauth_config.get('provider_name', 'bac-identity-provider-okta')
        
        oauth_settings = {
            'provider_name': provider_name,
            'scopes': ['api'],  # Default scopes
            'auth_flow': 'M2M'  # Machine-to-Machine flow
        }
        
        logger.info(f"🔐 OAuth settings: {oauth_settings}")
        return oauth_settings
        
    except Exception as e:
        logger.error(f"❌ Failed to get OAuth settings: {e}")
        # Return default settings
        default_settings = {
            'provider_name': 'bac-identity-provider-okta',
            'scopes': ['api'],
            'auth_flow': 'M2M'
        }
        logger.info(f"🔄 Using default OAuth settings: {default_settings}")
        return default_settings

# ============================================================================
# GATEWAY SETTINGS
# ============================================================================

def get_gateway_url():
    """
    Get MCP gateway URL.
    
    Returns:
        str: Gateway URL or None if not configured
    """
    agentcore_config, _ = load_configs()
    
    try:
        gateway_config = agentcore_config.get('gateway', {})
        gateway_url = gateway_config.get('url')
        
        if gateway_url:
            logger.info(f"🌐 Gateway URL: {gateway_url}")
        else:
            logger.info("🏠 No gateway URL configured - will use local tools only")
            
        return gateway_url
        
    except Exception as e:
        logger.error(f"❌ Failed to get gateway URL: {e}")
        return None