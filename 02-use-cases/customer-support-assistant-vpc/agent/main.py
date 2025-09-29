from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.tools.mcp.mcp_client import MCPClient
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands.models import BedrockModel
# from bedrock_agentcore.identity.auth import requires_access_token

from agent.context import CustomerSupportContext

# gateway_access_token = None
# agent = None


# @requires_access_token(
#     provider_name="customer-support-gateway",
#     scopes=[],  # Optional unless required
#     auth_flow="M2M",
# )
# async def get_gateway_access_token(access_token: str = ""):
#     global gateway_access_token
#     gateway_access_token = access_token
#     return access_token


app = BedrockAgentCoreApp()


@app.entrypoint
async def strands_agent_bedrock(payload, context):
    """
    Invoke the agent with a payload
    """

    # agent = CustomerSupportContext.get_agent_ctx()
    # gateway_access_token = CustomerSupportContext.get_gateway_token_ctx()

    # if not gateway_access_token:
    #     CustomerSupportContext.set_gateway_token_ctx(await get_gateway_access_token())
    #     gateway_access_token = CustomerSupportContext.get_gateway_token_ctx()

    # if agent is None:
    #     if not gateway_access_token:
    #         raise RuntimeError("Gateway Access token is none")
    #     streamable_http_mcp_client = MCPClient(
    #         lambda: streamablehttp_client(
    #             url="https://customer-support-3gwe5spzed.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp",
    #             headers={"Authorization": f"Bearer {gateway_access_token}"},
    #         )
    #     )

    #     streamable_http_mcp_client.start()

    #     model_id = "us.anthropic.claude-3-5-haiku-20241022-v1:0"
    #     model = BedrockModel(
    #         model_id=model_id,
    #     )
    #     agent = Agent(
    #         model=model,
    #         tools=streamable_http_mcp_client.list_tools_sync(),
    #         system_prompt="You're a helpful assistant",
    #     )

    #     CustomerSupportContext.set_agent_ctx(agent)

    user_message = payload["prompt"]
    # actor_id = payload["actor_id"]

    # session_id = context.session_id

    # response = agent(user_message)

    return user_message


if __name__ == "__main__":
    app.run()
