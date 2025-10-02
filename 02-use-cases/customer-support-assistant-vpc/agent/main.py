from context import CustomerSupportContext
from utils import get_ssm_parameter
from bedrock_agentcore.identity.auth import requires_access_token
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
import os
import urllib

app = BedrockAgentCoreApp()


GATEWAY_URL = get_ssm_parameter("/app/customersupportvpc/gateway/gateway_url")
MODEL_ID = os.getenv("MODEL_ID", "us.anthropic.claude-3-5-haiku-20241022-v1:0")
MCP_REGION = os.getenv("MCP_REGION")
MCP_ARN = os.getenv("MCP_ARN")
escaped_arn = urllib.parse.quote(MCP_ARN, safe="")
MCP_URL = f"https://bedrock-agentcore.{MCP_REGION}.amazonaws.com/runtimes/{escaped_arn}/invocations?qualifier=DEFAULT"


GATEWAY_PROVIDER_NAME = os.getenv("GATEWAY_PROVIDER_NAME")
MCP_PROVIDER_NAME = os.getenv("MCP_PROVIDER_NAME")


@requires_access_token(
    provider_name=GATEWAY_PROVIDER_NAME,
    scopes=[],
    auth_flow="M2M",
)
async def get_gateway_access_token(access_token: setattr):
    return access_token


@requires_access_token(
    provider_name=MCP_PROVIDER_NAME,
    scopes=[],
    auth_flow="M2M",
)
async def get_mcp_access_token(access_token: str):
    return access_token


@app.entrypoint
async def strands_agent_bedrock(payload, context):
    """
    Invoke the agent with a payload
    """

    agent = CustomerSupportContext.get_agent_ctx()
    gateway_access_token = CustomerSupportContext.get_gateway_token_ctx()
    mcp_access_token = CustomerSupportContext.get_gateway_token_ctx()

    if not gateway_access_token:
        CustomerSupportContext.set_gateway_token_ctx(await get_gateway_access_token())
        gateway_access_token = CustomerSupportContext.get_gateway_token_ctx()

    if not mcp_access_token:
        CustomerSupportContext.set_mcp_token_ctx(await get_mcp_access_token())
        mcp_access_token = CustomerSupportContext.get_mcp_token_ctx()

    if agent is None:
        if not gateway_access_token:
            raise RuntimeError("Gateway Access token is none")
        if not mcp_access_token:
            raise RuntimeError("MCP Access token is none")

        mcp_client = MCPClient(
            lambda: streamablehttp_client(
                url=MCP_URL,
                headers={"Authorization": f"Bearer {mcp_access_token}"},
            )
        )

        gateway_client = MCPClient(
            lambda: streamablehttp_client(
                url=GATEWAY_URL,
                headers={"Authorization": f"Bearer {gateway_access_token}"},
            )
        )

        gateway_client.start()
        mcp_client.start()

        model = BedrockModel(
            model_id=MODEL_ID,
        )
        agent = Agent(
            model=model,
            tools=gateway_client.list_tools_sync() + mcp_client.list_tools_sync(),
            system_prompt="You're a helpful assistant",
        )

        CustomerSupportContext.set_agent_ctx(agent)

    user_message = payload["prompt"]

    _ = context.session_id

    response = agent(user_message)

    return response


if __name__ == "__main__":
    app.run()
