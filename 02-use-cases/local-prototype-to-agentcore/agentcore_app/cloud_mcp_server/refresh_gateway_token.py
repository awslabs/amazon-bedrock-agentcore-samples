#!/usr/bin/env python3
"""
Script to refresh the access token for the Bedrock AgentCore Gateway.
Uses the stored Cognito client information from the gateway_info.json file.
"""

import json
import logging
import argparse
from bedrock_agentcore_starter_toolkit.operations.gateway import GatewayClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

def update_api_key(gateway_info, api_key):
    """Update the API key in the gateway info if provided"""
    if api_key:
        if "api" not in gateway_info:
            gateway_info["api"] = {}
            
        if "credentials" not in gateway_info["api"]:
            gateway_info["api"]["credentials"] = {}
            
        # Use the standard API key format
        gateway_info["api"]["credentials"] = {
            "apiKey": {
                "headers": {
                    "x-api-key": api_key
                }
            }
        }
        print("✓ Updated API key in gateway_info.json")
    
    return gateway_info

def main():
    parser = argparse.ArgumentParser(description="Refresh access token for Bedrock AgentCore Gateway")
    parser.add_argument("--api-key", help="API key for the API Gateway (optional)")
    args = parser.parse_args()

    print("Loading gateway information...")
    # Load gateway info from the previously saved file
    try:
        with open("gateway_info.json", "r") as f:
            gateway_info = json.load(f)
    except FileNotFoundError:
        print("Error: gateway_info.json file not found. Please run 3_agentcore_gateway_setup.py first.")
        exit(1)

    # Initialize the gateway client with the correct region
    client = GatewayClient(region_name=gateway_info["gateway"]["region"])

    print("Requesting new access token for gateway '{}'...".format(gateway_info['gateway']['name']))
    # Create client_info structure expected by get_test_token_for_cognito
    client_info = {
        "client_id": gateway_info["auth"]["client_id"],
        "client_secret": gateway_info["auth"]["client_secret"],
        "token_endpoint": gateway_info["auth"]["token_endpoint"],
        "scope": gateway_info["auth"]["scope"]
    }
    
    # Get a new access token using the stored client credentials
    new_token = client.get_access_token_for_cognito(client_info)

    print("✓ New access token generated successfully")

    # Update the gateway_info file with the new token
    gateway_info["auth"]["access_token"] = new_token
    
    # Update API key if provided
    gateway_info = update_api_key(gateway_info, args.api_key)
    
    # Save the updated gateway info
    with open("gateway_info.json", "w") as f:
        json.dump(gateway_info, f, indent=2)

    print("\nAccess token updated in gateway_info.json")
    print("\nTo use this token in your application, update the token value in your client code.")
    print("New access token:\n{}".format(new_token))
    
    # Output how to use in code
    print("\nExample of using the token in Python code:")
    print("""
from mcp.client.streamablehttp import streamablehttp_client
from strands.tools.mcp import MCPClient

# Create an MCP Client with your token
access_token = "{token}"
mcp_url = "{mcp_url}"
mcp_client = MCPClient(lambda: streamablehttp_client(
    mcp_url, 
    headers={{"Authorization": f"Bearer {{access_token}}"}}
))
""".format(token=new_token, mcp_url=gateway_info["gateway"].get("mcp_url", "YOUR_MCP_URL")))

if __name__ == "__main__":
    main()