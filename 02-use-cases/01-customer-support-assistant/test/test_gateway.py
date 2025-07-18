#!/usr/bin/python

import asyncio
import click
from bedrock_agentcore.identity.auth import requires_access_token
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts.utils import get_ssm_parameter

gateway_access_token = None


@requires_access_token(
    provider_name=get_ssm_parameter("/app/customersupport/agentcore/cognito_provider"),
    scopes=[],  # Optional unless required
    auth_flow="M2M",
)
async def _get_access_token_manually(*, access_token: str):
    global gateway_access_token
    gateway_access_token = access_token
    return access_token


@click.command()
@click.option("--prompt", "-p", required=True, help="Prompt to send to the MCP agent")
def main(prompt: str):
    """CLI tool to interact with an MCP Agent using a prompt."""

    # Fetch access token
    asyncio.run(_get_access_token_manually(access_token=""))

    # Load gateway configuration from SSM parameters
    try:
        gateway_url = get_ssm_parameter("/app/customersupport/agentcore/gateway_url")
    except Exception as e:
        print(f"❌ Error reading gateway URL from SSM: {str(e)}")
        sys.exit(1)

    print(f"Gateway Endpoint - MCP URL: {gateway_url}")

    # Set up MCP client
    client = MCPClient(
        lambda: streamablehttp_client(
            gateway_url,
            headers={"Authorization": f"Bearer {gateway_access_token}"},
        )
    )

    with client:
        agent = Agent(tools=client.list_tools_sync())
        response = agent(prompt)
        print(str(response))


if __name__ == "__main__":
    main()
