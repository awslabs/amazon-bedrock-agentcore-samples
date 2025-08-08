#!/usr/bin/env python3
"""Bedrock AgentCore Gateway Setup with OpenAPI Specification

This script sets up an AWS Bedrock AgentCore Gateway that exposes
an insurance API as MCP tools using an OpenAPI specification.

The script uses environment variables loaded from a .env file for configuration:

Environment Variables:
    AWS_REGION (str): AWS region for the gateway (default: "us-west-2")
    ENDPOINT_URL (str): Endpoint URL for Bedrock AgentCore (default: Bedrock AgentCore endpoint in us-west-2)
    GATEWAY_NAME (str): Name for the gateway (default: "InsuranceAPIGateway")
    GATEWAY_DESCRIPTION (str): Description for the gateway
    API_GATEWAY_URL (str): API Gateway URL for the insurance API
    OPENAPI_FILE_PATH (str): Path to the OpenAPI specification file (default: "../cloud_insurance_api/openapi.json")
    API_KEY (str): API key for authenticating with the API
    CREDENTIAL_LOCATION (str): Location for API credentials (default: "HEADER")
    CREDENTIAL_PARAMETER_NAME (str): Parameter name for API credentials (default: "X-Subscription-Token")
    GATEWAY_INFO_FILE (str): File path to save gateway information (default: "gateway_info.json")

Output:
    Creates a Bedrock AgentCore Gateway with Cognito authentication
    Configures the gateway to use the insurance API via OpenAPI specification
    Saves gateway information to a JSON file for later use
"""

import logging
import json
import os
from dotenv import load_dotenv
from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient

# Load environment variables from .env file
load_dotenv()

# Setup the client using environment variables
region = os.getenv("AWS_REGION", "us-west-2")
endpoint_url = os.getenv("ENDPOINT_URL", "https://bedrock-agentcore-control.us-west-2.amazonaws.com")

print(f"Setting up Gateway client in region {region}")
client = GatewayClient(endpoint_url=endpoint_url, region_name=region)
client.logger.setLevel(logging.DEBUG)

# Get gateway name from environment variables
gateway_name = os.getenv("GATEWAY_NAME", "InsuranceAPIGateway")
gateway_description = os.getenv("GATEWAY_DESCRIPTION", "Insurance API Gateway with OpenAPI Specification")

# Create cognito authorizer
print(f"Creating OAuth authorizer for gateway '{gateway_name}'")
cognito_response = client.create_oauth_authorizer_with_cognito(gateway_name)

# Create the gateway
print(f"Creating MCP gateway '{gateway_name}'")
gateway = client.create_mcp_gateway(
    name=gateway_name,
    authorizer_config=cognito_response["authorizer_config"],
)


# Load the insurance API OpenAPI specification from environment or default path
env_openapi_path = os.getenv("OPENAPI_FILE_PATH", "../cloud_insurance_api/openapi.json")
openapi_file_path = os.path.abspath(env_openapi_path)

print(f"Loading OpenAPI specification from: {openapi_file_path}")
with open(openapi_file_path, "r") as f:
    openapi_spec = json.load(f)

# Set the API Gateway URL from environment variables
api_gateway_url = os.getenv("API_GATEWAY_URL", "https://i0zzy6t0x9.execute-api.us-west-2.amazonaws.com/dev")

# Add server URL if not present in OpenAPI spec
if "servers" not in openapi_spec:
    print("Adding server URL to OpenAPI specification...")
    openapi_spec["servers"] = [{"url": api_gateway_url}]

# Get API credentials from environment variables
api_key = os.getenv("API_KEY", "BSAm0I6f_91QSB-CJQzsVpukUKTlXGJ")
credential_location = os.getenv("CREDENTIAL_LOCATION", "HEADER")
credential_parameter_name = os.getenv("CREDENTIAL_PARAMETER_NAME", "X-Subscription-Token")

# Create the OpenAPI target with OAuth2 configuration using Cognito
print("Creating MCP gateway target with OpenAPI specification")
open_api_target = client.create_mcp_gateway_target(
    gateway=gateway,
    name="API",
    target_type="openApiSchema",
    target_payload={
        "inlinePayload": json.dumps(openapi_spec)
    },
    credentials={
        "api_key": api_key,
        "credential_location": credential_location,
        "credential_parameter_name": credential_parameter_name
    }
)

# Print the gateway information
print("\n✅ Gateway setup complete!")
print(f"Gateway ID: {gateway['gatewayId']}")
print(f"Gateway MCP URL: https://{gateway['gatewayId']}.gateway.bedrock-agentcore.{client.region}.amazonaws.com/mcp")
print(f"Target ID: {open_api_target['targetId']}")

# Print authentication information
print("\nAuthentication Information:")
print(f"Client ID: {cognito_response['client_info']['client_id']}")
print(f"Client Secret: {cognito_response['client_info']['client_secret']}")
print(f"Token Endpoint: {cognito_response['client_info']['token_endpoint']}")
print(f"Scope: {cognito_response['client_info']['scope']}")

# Generate an access token for testing
access_token = client.get_access_token_for_cognito(cognito_response["client_info"])
print(f"\nAccess Token: {access_token}")

# Save gateway information to file for later use
gateway_info = {
    "gateway": {
        "name": gateway["name"],
        "id": gateway["gatewayId"],
        "mcp_url": f"https://{gateway['gatewayId']}.gateway.bedrock-agentcore.{client.region}.amazonaws.com/mcp",
        "region": client.region,
        "description": gateway.get("description", "Insurance API Gateway with OpenAPI Specification")
    },
    "api": {
        "gateway_url": api_gateway_url,
        "openapi_file_path": openapi_file_path,
        "target_id": open_api_target["targetId"]
    },
    "auth": {
        "access_token": access_token,
        "client_id": cognito_response["client_info"]["client_id"],
        "client_secret": cognito_response["client_info"]["client_secret"],
        "token_endpoint": cognito_response["client_info"]["token_endpoint"],
        "scope": cognito_response["client_info"]["scope"],
        "user_pool_id": cognito_response["client_info"]["user_pool_id"],
        "discovery_url": cognito_response["authorizer_config"]["customJWTAuthorizer"]["discoveryUrl"]
    }
}

# Get gateway info file path from environment or use default
gateway_info_file = os.getenv("GATEWAY_INFO_FILE", "gateway_info.json")

print(f"\nSaving gateway information to {gateway_info_file}...")
with open(gateway_info_file, "w") as f:
    json.dump(gateway_info, f, indent=2)

print("\nSetup complete! You can now use the MCP server with the Insurance API.")