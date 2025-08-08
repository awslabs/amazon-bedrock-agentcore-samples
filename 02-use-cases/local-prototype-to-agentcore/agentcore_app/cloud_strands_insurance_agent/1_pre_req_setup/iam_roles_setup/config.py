#!/usr/bin/env python3
"""
Configuration module for IAM role settings

This module stores all configuration settings for IAM role creation
and provides functions to load/save configuration.
"""

import os
import json
import configparser
from typing import Dict, Any, List, Optional

# Default config file path
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'iam_config.ini')

# Default configuration
DEFAULT_CONFIG = {
    'role': {
        'name': 'BedrockAgentCoreExecutionRole',
        'description': 'Execution role for Bedrock AgentCore applications'
    },
    'account': {
        'id': '',
        'regions': 'us-east-1,us-west-2'
    },
    'ecr': {
        'repository_name': 'bedrock-agentcore'
    },
    'agent': {
        'name': 'insurance-agent'
    },
    'policies': {
        'enable_ecr': 'true',
        'enable_logs': 'true',
        'enable_xray': 'true',
        'enable_cloudwatch': 'true',
        'enable_bedrock_agentcore': 'true',
        'enable_bedrock_models': 'true'
    }
}

def create_default_config() -> None:
    """Creates a default configuration file if it doesn't exist"""
    if not os.path.exists(CONFIG_FILE):
        config = configparser.ConfigParser()
        
        for section, options in DEFAULT_CONFIG.items():
            config[section] = options
            
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)
        
        print(f"Created default configuration at {CONFIG_FILE}")

def load_config() -> Dict[str, Dict[str, str]]:
    """
    Loads configuration from file
    
    Returns:
        Dictionary containing configuration values
    """
    # Create default config if it doesn't exist
    if not os.path.exists(CONFIG_FILE):
        create_default_config()
    
    # Load configuration
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    
    # Convert to dictionary
    config_dict = {
        section: dict(config[section]) 
        for section in config.sections()
    }
    
    return config_dict

def save_config(config_data: Dict[str, Dict[str, str]]) -> None:
    """
    Saves configuration to file
    
    Args:
        config_data: Dictionary containing configuration values
    """
    config = configparser.ConfigParser()
    
    for section, options in config_data.items():
        config[section] = options
        
    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)
    
    print(f"Configuration saved to {CONFIG_FILE}")

def get_regions(config_data: Dict[str, Dict[str, str]]) -> List[str]:
    """
    Gets list of regions from configuration
    
    Args:
        config_data: Dictionary containing configuration
        
    Returns:
        List of region strings
    """
    regions_str = config_data.get('account', {}).get('regions', 'us-east-1,us-west-2')
    return [r.strip() for r in regions_str.split(',') if r.strip()]

def get_account_id(config_data: Dict[str, Dict[str, str]]) -> str:
    """
    Gets account ID from configuration
    
    Args:
        config_data: Dictionary containing configuration
        
    Returns:
        AWS account ID string
    """
    return config_data.get('account', {}).get('id', '')

def get_role_name(config_data: Dict[str, Dict[str, str]]) -> str:
    """
    Gets role name from configuration
    
    Args:
        config_data: Dictionary containing configuration
        
    Returns:
        IAM role name
    """
    return config_data.get('role', {}).get('name', 'BedrockAgentCoreExecutionRole')

# Initialize configuration
if __name__ == "__main__":
    create_default_config()