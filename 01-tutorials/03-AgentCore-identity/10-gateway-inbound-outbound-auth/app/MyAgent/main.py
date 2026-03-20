"""
AgentCore Runtime agent that uses tools provided by an AgentCore Gateway.

- Inbound Auth:  Gateway validates caller's Cognito JWT before routing requests
- Outbound Auth: Gateway authenticates to the upstream MCP server with OAuth2
                 client credentials (configured in mcp.json, no code changes needed)

The agent uses the MCP gateway client to discover and call tools exposed
through the gateway. The gateway handles all outbound auth transparently.
"""

import os
from strands import Agent
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore_gateway import GatewayClient  # provided by bedrock-agentcore

app = BedrockAgentCoreApp()

_model = BedrockModel(model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0")
_agent: Agent | None = None


def _build_agent() -> Agent:
    """Build agent with tools discovered from the gateway at startup."""
    gateway_url = os.environ.get("AGENTCORE_GATEWAY_URL", "")
    if not gateway_url:
        raise ValueError(
            "AGENTCORE_GATEWAY_URL environment variable is not set. "
            "Run 'agentcore deploy -y' and check the gateway endpoint."
        )

    # GatewayClient fetches tool definitions from the gateway's MCP endpoint.
    # The gateway presents the agent's managed credential (Bearer token) for
    # inbound auth, and uses the configured outbound credential to talk to
    # the upstream MCP server.
    gateway_client = GatewayClient(endpoint=gateway_url)
    gateway_tools = gateway_client.get_tools()

    return Agent(
        model=_model,
        tools=gateway_tools,
        system_prompt=(
            "You are a helpful assistant with access to external tools "
            "provided through a secure gateway."
        ),
    )


@app.entrypoint
async def handler(payload: dict) -> str:
    global _agent

    if _agent is None:
        _agent = _build_agent()

    user_input = payload.get("prompt", "")
    response = _agent(user_input)
    return response.message["content"][0]["text"]


if __name__ == "__main__":
    app.run()
