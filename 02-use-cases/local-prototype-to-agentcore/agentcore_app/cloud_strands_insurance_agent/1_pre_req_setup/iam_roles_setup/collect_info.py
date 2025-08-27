#!/usr/bin/env python3
"""
Interactive script to collect IAM role setup information

This script guides the user through collecting all necessary information
for setting up Bedrock AgentCore IAM roles.
"""

import os
import sys
import subprocess
from typing import Dict, Optional, List, Any

# Import configuration module
from config import (
    load_config, save_config, get_regions,
    get_account_id, get_role_name
)

def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def get_aws_account_id() -> Optional[str]:
    """
    Get the AWS account ID using the AWS CLI
    
    Returns:
        AWS account ID or None if not available
    """
    try:
        result = subprocess.run(
            ['aws', 'sts', 'get-caller-identity', '--query', 'Account', '--output', 'text'],
            capture_output=True,
            text=True,
            check=True
        )
        account_id = result.stdout.strip()
        return account_id
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

def validate_aws_account_id(account_id: str) -> bool:
    """
    Validate AWS account ID format
    
    Args:
        account_id: Account ID to validate
        
    Returns:
        True if valid, False otherwise
    """
    # AWS account IDs are 12 digits
    return account_id.isdigit() and len(account_id) == 12

def collect_account_info(config_data: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    """
    Collect AWS account information
    
    Args:
        config_data: Current configuration
        
    Returns:
        Updated configuration dictionary
    """
    clear_screen()
    print("=== AWS Account Information ===\n")
    
    # Try to get account ID automatically
    current_id = config_data.get('account', {}).get('id', '')
    detected_id = get_aws_account_id()
    
    if detected_id and not current_id:
        print(f"Detected AWS Account ID: {detected_id}")
        use_detected = input("Use this account ID? (Y/n): ").strip().lower() != 'n'
        if use_detected:
            account_id = detected_id
        else:
            account_id = input("Enter AWS Account ID: ").strip()
    else:
        if current_id:
            print(f"Current AWS Account ID: {current_id}")
            change_id = input("Do you want to change it? (y/N): ").strip().lower() == 'y'
            if change_id:
                account_id = input("Enter AWS Account ID: ").strip()
            else:
                account_id = current_id
        else:
            account_id = input("Enter AWS Account ID: ").strip()
    
    # Validate account ID
    while not validate_aws_account_id(account_id):
        print("Invalid AWS Account ID. It should be a 12-digit number.")
        account_id = input("Enter AWS Account ID: ").strip()
    
    # Get regions
    current_regions = ','.join(get_regions(config_data))
    print(f"\nCurrent AWS Regions: {current_regions}")
    change_regions = input("Do you want to change the regions? (y/N): ").strip().lower() == 'y'
    
    if change_regions:
        print("\nEnter comma-separated list of AWS regions.")
        print("Example: us-east-1,us-west-2")
        regions = input("AWS Regions: ").strip()
    else:
        regions = current_regions
    
    # Update config
    if 'account' not in config_data:
        config_data['account'] = {}
        
    config_data['account']['id'] = account_id
    config_data['account']['regions'] = regions
    
    return config_data

def collect_role_info(config_data: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    """
    Collect IAM role information
    
    Args:
        config_data: Current configuration
        
    Returns:
        Updated configuration dictionary
    """
    clear_screen()
    print("=== IAM Role Information ===\n")
    
    # Get role name
    current_name = get_role_name(config_data)
    print(f"Current Role Name: {current_name}")
    change_name = input("Do you want to change it? (y/N): ").strip().lower() == 'y'
    
    if change_name:
        role_name = input("Enter IAM Role Name: ").strip()
    else:
        role_name = current_name
    
    # Get role description
    current_desc = config_data.get('role', {}).get('description', 
                                            'Execution role for Bedrock AgentCore applications')
    print(f"\nCurrent Role Description: {current_desc}")
    change_desc = input("Do you want to change it? (y/N): ").strip().lower() == 'y'
    
    if change_desc:
        description = input("Enter Role Description: ").strip()
    else:
        description = current_desc
    
    # Update config
    if 'role' not in config_data:
        config_data['role'] = {}
        
    config_data['role']['name'] = role_name
    config_data['role']['description'] = description
    
    return config_data

def collect_policy_info(config_data: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    """
    Collect policy configuration information
    
    Args:
        config_data: Current configuration
        
    Returns:
        Updated configuration dictionary
    """
    clear_screen()
    print("=== Policy Configuration ===\n")
    print("Select which permissions to include in the execution role.")
    print("(Default is to enable all permissions)\n")
    
    # Get current policies
    policies = config_data.get('policies', {})
    
    # Configure each policy option
    policy_options = [
        ('enable_ecr', 'Amazon ECR (Container Registry) Access'),
        ('enable_logs', 'CloudWatch Logs Access'),
        ('enable_xray', 'AWS X-Ray Tracing'),
        ('enable_cloudwatch', 'CloudWatch Metrics'),
        ('enable_bedrock_agentcore', 'Bedrock AgentCore Access'),
        ('enable_bedrock_models', 'Bedrock Models Access')
    ]
    
    for policy_key, policy_name in policy_options:
        current = policies.get(policy_key, 'true').lower() == 'true'
        enabled = 'enabled' if current else 'disabled'
        
        print(f"{policy_name} - Currently {enabled}")
        toggle = input(f"Toggle this permission? (y/N): ").strip().lower() == 'y'
        
        if toggle:
            policies[policy_key] = str(not current).lower()
        else:
            policies[policy_key] = str(current).lower()
    
    # Update config
    config_data['policies'] = policies
    
    return config_data

def collect_ecr_info(config_data: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    """
    Collect ECR repository information
    
    Args:
        config_data: Current configuration
        
    Returns:
        Updated configuration dictionary
    """
    clear_screen()
    print("=== ECR Repository Information ===\n")
    
    # Get repository name
    current_repo = config_data.get('ecr', {}).get('repository_name', 'bedrock-agentcore')
    print(f"Current Repository Name: {current_repo}")
    change_repo = input("Do you want to change it? (y/N): ").strip().lower() == 'y'
    
    if change_repo:
        repository_name = input("Enter ECR Repository Name: ").strip()
    else:
        repository_name = current_repo
    
    # Update config
    if 'ecr' not in config_data:
        config_data['ecr'] = {}
        
    config_data['ecr']['repository_name'] = repository_name
    
    return config_data

def collect_agent_info(config_data: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    """
    Collect agent information
    
    Args:
        config_data: Current configuration
        
    Returns:
        Updated configuration dictionary
    """
    clear_screen()
    print("=== Agent Information ===\n")
    
    # Get agent name
    current_agent = config_data.get('agent', {}).get('name', 'insurance-agent')
    print(f"Current Agent Name: {current_agent}")
    change_agent = input("Do you want to change it? (y/N): ").strip().lower() == 'y'
    
    if change_agent:
        agent_name = input("Enter Agent Name: ").strip()
    else:
        agent_name = current_agent
    
    # Update config
    if 'agent' not in config_data:
        config_data['agent'] = {}
        
    config_data['agent']['name'] = agent_name
    
    return config_data

def run_interactive_setup() -> Dict[str, Dict[str, str]]:
    """
    Run the interactive setup process
    
    Returns:
        Final configuration dictionary
    """
    print("=== Bedrock AgentCore IAM Role Setup ===\n")
    print("This script will guide you through setting up the necessary IAM roles")
    print("for AWS Bedrock AgentCore execution.\n")
    print("Press Enter to continue...")
    input()
    
    # Load current configuration
    config_data = load_config()
    
    # Collect information
    config_data = collect_account_info(config_data)
    config_data = collect_role_info(config_data)
    config_data = collect_ecr_info(config_data)
    config_data = collect_agent_info(config_data)
    config_data = collect_policy_info(config_data)
    
    # Summary
    clear_screen()
    print("=== Configuration Summary ===\n")
    print(f"AWS Account ID: {get_account_id(config_data)}")
    print(f"AWS Regions: {','.join(get_regions(config_data))}")
    print(f"Role Name: {get_role_name(config_data)}")
    print(f"Role Description: {config_data.get('role', {}).get('description')}")
    print(f"ECR Repository: {config_data.get('ecr', {}).get('repository_name')}")
    print(f"Agent Name: {config_data.get('agent', {}).get('name')}")
    print("\nPolicy Permissions:")
    
    policies = config_data.get('policies', {})
    for policy_key, policy_name in [
        ('enable_ecr', 'Amazon ECR'),
        ('enable_logs', 'CloudWatch Logs'),
        ('enable_xray', 'X-Ray Tracing'),
        ('enable_cloudwatch', 'CloudWatch Metrics'),
        ('enable_bedrock_agentcore', 'Bedrock AgentCore'),
        ('enable_bedrock_models', 'Bedrock Models')
    ]:
        enabled = policies.get(policy_key, 'true').lower() == 'true'
        status = "✓" if enabled else "✗"
        print(f"  {status} {policy_name}")
    
    # Save configuration
    print("\nSave this configuration?")
    save = input("(Y/n): ").strip().lower() != 'n'
    
    if save:
        save_config(config_data)
        print("\nConfiguration saved!")
    else:
        print("\nConfiguration not saved.")
    
    return config_data

if __name__ == "__main__":
    try:
        run_interactive_setup()
    except KeyboardInterrupt:
        print("\n\nSetup interrupted. No changes were saved.")
        sys.exit(1)