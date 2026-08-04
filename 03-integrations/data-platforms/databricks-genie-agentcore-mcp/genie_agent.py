"""Strands agent hosted on AgentCore Runtime that queries Databricks Genie
through Amazon Bedrock AgentCore Gateway.

The gateway handles all auth complexity:
  - Inbound:  Cognito JWT validates agent requests
  - Outbound: OAuth2 M2M (client credentials) authenticates with Databricks

Deployed with the AgentCore CLI, not run directly:

    agentcore configure --entrypoint genie_agent.py
    agentcore deploy

Requires gateway_config.json in the same directory (written by deploy.py).
"""

import json

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
SYSTEM_PROMPT = (
    "You answer business questions by calling the Databricks Genie tool exposed "
    "through the gateway. Genie returns governed, lakehouse-native SQL answers. "
    "Be concise and present results in a readable format."
)

app = BedrockAgentCoreApp()

with open("gateway_config.json") as f:
    config = json.load(f)

gw_client = GatewayClient(region_name=config["region"])


def _get_tools():
    """Connect to the gateway over MCP and return (client, tools)."""
    token = gw_client.get_access_token_for_cognito(config["client_info"])
    mcp = MCPClient(
        lambda: streamablehttp_client(
            config["gateway_url"],
            headers={"Authorization": f"Bearer {token}"},
        )
    )
    mcp.start()
    return mcp, mcp.list_tools_sync()


# Establish the tool surface once at cold start rather than per invocation.
mcp_client, tools = _get_tools()
print(f"Loaded {len(tools)} tools from gateway")


@app.entrypoint
def invoke(payload, context):
    """AgentCore Runtime entrypoint."""
    agent = Agent(
        model=BedrockModel(model_id=MODEL_ID),
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
    )
    result = agent(payload.get("prompt", ""))
    return {"result": result.message}


if __name__ == "__main__":
    app.run()
