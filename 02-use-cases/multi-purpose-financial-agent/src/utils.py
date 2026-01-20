"""
Utility functions for the Financial Analyzer Agent.

This module provides configuration and authentication utilities for:
- Configuration loading from SSM Parameter Store
- Cognito authentication and token management
- Gateway connection management
"""

from typing import Dict, Optional, Tuple

import boto3
import requests
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient


def load_config_from_ssm(prefix="/finance-analyzer", region="us-east-1"):
    """Load configuration from AWS Systems Manager Parameter Store.

    Args:
        prefix: SSM parameter path prefix (default: /finance-analyzer)
        region: AWS region (default: us-east-1)

    Returns:
        Tuple of (config dict, success boolean)
    """
    ssm = boto3.client('ssm', region_name=region)

    default_config = {
        "region": region
    }

    try:
        paginator = ssm.get_paginator('get_parameters_by_path')
        pages = paginator.paginate(
            Path=prefix,
            Recursive=True,
            WithDecryption=True,
            PaginationConfig={'PageSize': 10}
        )

        parameters = [param for page in pages for param in page['Parameters']]

        if not parameters:
            raise ValueError("No parameters found in Parameter Store")

        config = {"client_info": {}, "region": region}
        client_keys = {'user_pool_id', 'client_id', 'client_secret'}

        for param in parameters:
            name = param['Name'].replace(f"{prefix}/", "")
            value = param['Value']

            if name in client_keys:
                config['client_info'][name] = value
            else:
                config[name] = value

        print(f"[Config] Loaded {len(parameters)} parameters")
        return config, True

    except Exception as e:
        print(f"[Config] Failed to load: {e}")
        print("[Config] Only local financial analysis tools will work")
        return default_config, False


def authenticate_and_connect_to_gateway(config: Dict) -> Tuple[Optional[MCPClient], bool]:
    """
    Authenticate with Cognito and establish connection to AgentCore Gateway.

    This function:
    1. Obtains a JWT access token from Amazon Cognito using client credentials
    2. Creates an MCP client configured with the Gateway URL
    3. Adds the JWT token to Authorization headers for all Gateway requests
    4. Starts the MCP client connection

    Args:
        config: Configuration dict containing gateway_url and Cognito credentials

    Returns:
        Tuple of (MCP client instance, success boolean)
        Returns (None, False) if connection fails
    """
    try:
        access_token = get_access_token(config)
        gateway_url = config["gateway_url"]

        mcp_client = MCPClient(
            lambda: streamablehttp_client(
                gateway_url, headers={"Authorization": f"Bearer {access_token}"}
            )
        )
        mcp_client.start()
        return mcp_client, True

    except KeyError as e:
        print(f"[Gateway] Configuration missing: {e}")
        return None, False
    except Exception as e:
        print(f"[Gateway] Connection failed: {e}")
        return None, False


def get_access_token(config):
    """
    Get Cognito access token using OAuth 2.0 client credentials flow.

    Args:
        config: Configuration dict with client_info and cognito_domain

    Returns:
        JWT access token string
    """
    client_info = config["client_info"]
    region = config["region"]
    domain = config.get("cognito_domain")

    token_url = f"https://{domain}.auth.{region}.amazoncognito.com/oauth2/token"

    response = requests.post(
        token_url,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "client_credentials",
            "client_id": client_info["client_id"],
            "client_secret": client_info["client_secret"]
        }
    )
    response.raise_for_status()
    return response.json()["access_token"]
