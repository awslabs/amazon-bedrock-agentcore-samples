"""
AWS Systems Manager Parameter Store Utilities

This module provides functions to interact with AWS Systems Manager Parameter Store
for retrieving configuration parameters. Parameters are stored with the prefix
'/agentcore-data-analyst-assistant/' followed by the parameter name.

Parameters:
- SECRET_ARN: ARN of the AWS Secrets Manager secret containing database credentials
- AURORA_RESOURCE_ARN: ARN of the Aurora Serverless cluster
- DATABASE_NAME: Name of the database to connect to
- MEMORY_ID: AgentCore Memory ID for conversation context management
- QUESTION_ANSWERS_TABLE: DynamoDB table for storing query results
- MAX_RESPONSE_SIZE_BYTES: Maximum size of query responses in bytes (default: 25600)
"""

import boto3
import os
from botocore.exceptions import ClientError

# Project ID for SSM parameter path prefix
PROJECT_ID = os.environ.get("PROJECT_ID", "agentcore-data-analyst-assistant")


def get_ssm_client():
    """
    Creates and returns an SSM client using default AWS configuration.

    Returns:
        boto3.client: SSM client
    """
    return boto3.client("ssm")


def get_ssm_parameter(param_name):
    """
    Retrieves a parameter from AWS Systems Manager Parameter Store.

    Args:
        param_name: Name of the parameter without the project prefix

    Returns:
        str: The parameter value

    Raises:
        ClientError: If there's an error retrieving the parameter
    """
    client = get_ssm_client()
    full_param_name = f"/{PROJECT_ID}/{param_name}"

    try:
        response = client.get_parameter(Name=full_param_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except ClientError as e:
        print("\n" + "=" * 70)
        print("❌ SSM PARAMETER RETRIEVAL ERROR")
        print("=" * 70)
        print(f"📋 Parameter: {full_param_name}")
        print(f"💥 Error: {e}")
        print("=" * 70 + "\n")
        raise


def load_config():
    """
    Loads all required configuration parameters from SSM.

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
        "MEMORY_ID",
    ]

    config = {}

    # Load each parameter
    for key in param_keys:
        try:
            value = get_ssm_parameter(key)
            # Convert to int for specific parameters
            if key in ["MAX_RESPONSE_SIZE_BYTES"]:
                config[key] = int(value)
            else:
                config[key] = value
        except ClientError:
            # If MAX_RESPONSE_SIZE_BYTES is not found, use default value
            if key == "MAX_RESPONSE_SIZE_BYTES":
                config[key] = 25600
            # If optional parameters are not found, set to None
            elif key in ["QUESTION_ANSWERS_TABLE"]:
                config[key] = None
            # For required parameters, raise an exception
            elif key in [
                "SECRET_ARN",
                "AURORA_RESOURCE_ARN",
                "DATABASE_NAME",
                "MEMORY_ID",
            ]:
                raise ValueError(
                    f"Required SSM parameter /{PROJECT_ID}/{key} not found"
                )

    return config
