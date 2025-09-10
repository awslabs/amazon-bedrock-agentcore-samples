"""
AWS Systems Manager Parameter Store Utilities

This module provides functions to interact with AWS Systems Manager Parameter Store
for retrieving configuration parameters. Parameters are stored with the prefix
'/strands-data-analyst-assistant/' followed by the parameter name.

Required SSM Parameters:
- SECRET_ARN: ARN of the AWS Secrets Manager secret containing database credentials
- AURORA_RESOURCE_ARN: ARN of the Aurora Serverless cluster
- DATABASE_NAME: Name of the database to connect to

Optional SSM Parameters:
- QUESTION_ANSWERS_TABLE: DynamoDB table for storing query results
- AGENT_INTERACTIONS_TABLE_NAME: DynamoDB table for storing agent interactions
- MAX_RESPONSE_SIZE_BYTES: Maximum size of query responses in bytes (default: 25600)
"""

import boto3
import os
from botocore.exceptions import ClientError

# Project ID for SSM parameter path prefix
PROJECT_ID = "agentcore-data-analyst-assistant"

# Default AWS region
DEFAULT_REGION = "us-east-1"

def get_ssm_client(region_name=None):
    """
    Creates and returns an SSM client.
    
    Args:
        region_name: AWS region where the SSM parameters are stored
        
    Returns:
        boto3.client: SSM client
    """
    if not region_name:
        region_name = os.environ.get("AWS_REGION", DEFAULT_REGION)
        
    session = boto3.session.Session()
    return session.client(service_name="ssm", region_name=region_name)

def get_ssm_parameter(param_name, region_name=None):
    """
    Retrieves a parameter from AWS Systems Manager Parameter Store.
    
    Args:
        param_name: Name of the parameter without the project prefix
        region_name: AWS region where the parameter is stored
        
    Returns:
        str: The parameter value
        
    Raises:
        ClientError: If there's an error retrieving the parameter
    """
    client = get_ssm_client(region_name)
    full_param_name = f"/{PROJECT_ID}/{param_name}"
    
    try:
        response = client.get_parameter(
            Name=full_param_name,
            WithDecryption=True
        )
        return response['Parameter']['Value']
    except ClientError as e:
        print("\n" + "="*70)
        print("❌ SSM PARAMETER RETRIEVAL ERROR")
        print("="*70)
        print(f"📋 Parameter: {full_param_name}")
        print(f"💥 Error: {e}")
        print("="*70 + "\n")
        raise

def load_config(region_name=None):
    """
    Loads all required configuration parameters from SSM.
    
    Args:
        region_name: AWS region where the parameters are stored
        
    Returns:
        dict: Configuration dictionary with all parameters
        
    Note:
        Required parameters will raise ValueError if not found.
        Optional parameters will be set to None or default values if not found.
    """
    # Define the parameters to load
    param_keys = [
        "SECRET_ARN",
        "AURORA_RESOURCE_ARN",
        "DATABASE_NAME",
        "QUESTION_ANSWERS_TABLE",
        "MAX_RESPONSE_SIZE_BYTES",
        "AGENT_INTERACTIONS_TABLE_NAME",
        "MEMORY_ID"
    ]
    
    config = {}
    
    # Get AWS region from environment or use default
    if not region_name:
        region_name = os.environ.get("AWS_REGION", DEFAULT_REGION)
    
    config["AWS_REGION"] = region_name
    
    # Load each parameter
    for key in param_keys:
        try:
            config[key] = get_ssm_parameter(key, region_name)
        except ClientError:
            # If MAX_RESPONSE_SIZE_BYTES is not found, use default value
            if key == "MAX_RESPONSE_SIZE_BYTES":
                config[key] = 25600
            # If optional parameters are not found, set to None
            elif key in ["QUESTION_ANSWERS_TABLE", "AGENT_INTERACTIONS_TABLE_NAME"]:
                config[key] = None
            # For required parameters, raise an exception
            elif key in ["SECRET_ARN", "AURORA_RESOURCE_ARN", "DATABASE_NAME"]:
                raise ValueError(f"Required SSM parameter /{PROJECT_ID}/{key} not found")
    
    # Convert MAX_RESPONSE_SIZE_BYTES to int if it exists
    if "MAX_RESPONSE_SIZE_BYTES" in config:
        try:
            config["MAX_RESPONSE_SIZE_BYTES"] = int(config["MAX_RESPONSE_SIZE_BYTES"])
        except ValueError:
            config["MAX_RESPONSE_SIZE_BYTES"] = 25600
    
    return config