"""
Minimal Strands agent that connects to AgentCore Gateway with a tenant JWT.

The agent has zero tenant-specific logic. Tool visibility is determined entirely
by the Cedar policy engine on the Gateway, which inspects the JWT scope claim.
"""

import uuid

from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client


def create_tenant_agent(gateway_url: str, access_token: str, model_id: str = None):
    """Create a Strands agent connected to the Gateway with a tenant token.

    Args:
        gateway_url: The AgentCore Gateway MCP endpoint URL.
        access_token: OAuth2 access token with tenant-specific scope.
        model_id: Bedrock model ID. Defaults to Claude Sonnet.

    Returns:
        Tuple of (agent, mcp_client) for use and cleanup.
    """
    model_id = model_id or "us.anthropic.claude-sonnet-4-20250514"

    mcp_client = MCPClient(
        lambda: streamablehttp_client(
            gateway_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    )
    mcp_client.__enter__()
    tools = mcp_client.list_tools_sync()
    print(f"  Tools visible to this tenant: {[t.tool_name for t in tools]}")

    bedrock_model = BedrockModel(model_id=model_id, streaming=True)
    agent = Agent(model=bedrock_model, tools=tools)
    return agent, mcp_client


def list_tenant_tools(gateway_url: str, access_token: str) -> list:
    """List tools visible to a tenant (without creating a full agent).

    Returns list of (tool_name, description) tuples.
    """
    mcp_client = MCPClient(
        lambda: streamablehttp_client(
            gateway_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    )
    with mcp_client:
        tools = mcp_client.list_tools_sync()
        return [(t.tool_name, getattr(t, "description", "")) for t in tools]


def call_tool_raw(gateway_url: str, access_token: str, tool_name: str, arguments: dict):
    """Attempt to call a specific tool via the Gateway.

    Returns (success: bool, message: str).
    """
    mcp_client = MCPClient(
        lambda: streamablehttp_client(
            gateway_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    )
    with mcp_client:
        try:
            result = mcp_client.call_tool_sync(
                tool_use_id=str(uuid.uuid4()),
                name=tool_name,
                arguments=arguments,
            )
            if result.status == "error":
                return False, result.content
            return True, result.content
        except Exception as e:
            return False, str(e)
