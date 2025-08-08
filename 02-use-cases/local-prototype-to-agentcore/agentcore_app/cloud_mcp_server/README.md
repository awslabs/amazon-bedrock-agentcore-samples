# Cloud MCP Server

This component sets up an AWS Bedrock AgentCore Gateway that exposes insurance API operations as MCP tools using an OpenAPI specification.

## Overview

The Cloud MCP Server acts as a bridge between your LLM-powered agents and your insurance API. It leverages AWS Bedrock AgentCore Gateway to create a secure, managed MCP (Model Control Protocol) endpoint that agents can use to access insurance operations.

## Features

- **OpenAPI Integration**: Automatically converts your API's OpenAPI specification into MCP tools
- **OAuth Authentication**: Configures secure access with Amazon Cognito
- **Environment-Based Configuration**: Uses environment variables for flexible deployment
- **Gateway Management**: Creates and configures the AWS Bedrock AgentCore Gateway

## Prerequisites

- AWS account with Bedrock access
- Python 3.10+
- OpenAPI specification for your insurance API
- API endpoint deployed and accessible

## Installation

1. Clone this repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the `cloud_mcp_server` directory with the following variables:

```
# AWS Configuration
AWS_REGION=us-west-2
ENDPOINT_URL=https://bedrock-agentcore-control.us-west-2.amazonaws.com

# Gateway Configuration
GATEWAY_NAME=InsuranceAPIGatewayCreds3
GATEWAY_DESCRIPTION=Insurance API Gateway with OpenAPI Specification

# API Configuration
API_GATEWAY_URL=https://your-api-gateway-url.execute-api.us-west-2.amazonaws.com/dev
OPENAPI_FILE_PATH=../cloud_insurance_api/openapi.json

# API Credentials
API_KEY=your-api-key
CREDENTIAL_LOCATION=HEADER
CREDENTIAL_PARAMETER_NAME=X-Subscription-Token

# Output Configuration
GATEWAY_INFO_FILE=./gateway_info.json
```

Replace the placeholder values with your actual configuration.

## Usage

Run the gateway setup script:

```bash
python agentcore_gateway_setup_openapi.py
```

This will:

1. Create a new AWS Bedrock AgentCore Gateway
2. Configure OAuth authentication with Amazon Cognito
3. Register your OpenAPI specification as MCP tools
4. Save the gateway information for future use

After running the script, you'll receive:
- Gateway ID and MCP URL
- Authentication credentials
- Access token for testing

## Gateway Information

The script saves all gateway information to a JSON file (`gateway_info.json` by default) with the following structure:

```json
{
  "gateway": {
    "name": "InsuranceAPIGatewayCreds3",
    "id": "gateway-id",
    "mcp_url": "https://gateway-id.gateway.bedrock-agentcore.region.amazonaws.com/mcp",
    "region": "us-west-2",
    "description": "Insurance API Gateway with OpenAPI Specification"
  },
  "api": {
    "gateway_url": "https://your-api-gateway-url.execute-api.us-west-2.amazonaws.com/dev",
    "openapi_file_path": "/path/to/openapi.json",
    "target_id": "target-id"
  },
  "auth": {
    "access_token": "temporary-access-token",
    "client_id": "cognito-client-id",
    "client_secret": "cognito-client-secret",
    "token_endpoint": "https://auth-endpoint.amazonaws.com/oauth2/token",
    "scope": "gateway-name/invoke",
    "user_pool_id": "us-west-2_poolid",
    "discovery_url": "https://cognito-idp.region.amazonaws.com/user-pool-id/.well-known/openid-configuration"
  }
}
```

## Connecting Agents

Agents can connect to this MCP server using the MCP URL and authentication token. For example, using the strands-agents library:

```python
from strands import Agent
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client

# Get the MCP URL and access token from your gateway_info.json
MCP_SERVER_URL = "https://gateway-id.gateway.bedrock-agentcore.region.amazonaws.com/mcp"
access_token = "your-access-token"

# Create an MCP Client
mcp_client = MCPClient(lambda: streamablehttp_client(
    MCP_SERVER_URL, 
    headers={"Authorization": f"Bearer {access_token}"}
))

# Use the client with your agent
with mcp_client:
    tools = mcp_client.list_tools_sync()
    agent = Agent(
        model="your-model",
        tools=tools,
        system_prompt="Your system prompt"
    )
    response = agent(user_input)
```

## Troubleshooting

- **Authentication Errors**: Make sure your access token is valid and not expired
- **OpenAPI Errors**: Validate your OpenAPI specification before running the script
- **Gateway Creation Fails**: Check your AWS permissions and Bedrock service limits
- **Invalid Endpoint**: Verify your API Gateway URL is accessible

## Next Steps

After setting up the MCP server:

1. Configure your agents to use the MCP URL and authentication
2. Set up token refresh for production use
3. Add monitoring and logging for gateway operations