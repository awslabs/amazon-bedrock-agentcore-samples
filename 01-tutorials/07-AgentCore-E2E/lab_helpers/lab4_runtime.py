import boto3
import requests
from bedrock_agentcore.runtime import (
    BedrockAgentCoreApp,
)  # ### AGENTCORE RUNTIME - LINE 1 ####
from lab_helpers.lab1_strands_agent import (
    MODEL_ID,
    SYSTEM_PROMPT,
    get_product_info,
    get_return_policy,
    get_technical_support,
)
from lab_helpers.lab2_memory import (
    ACTOR_ID,
    SESSION_ID,
    CustomerSupportMemoryHooks,
    memory_client,
)
from mcp.client.streamable_http import streamablehttp_client
from scripts.utils import get_cognito_client_secret, get_ssm_parameter
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

# Lab1 import: Create the Bedrock model
model = BedrockModel(model_id=MODEL_ID)

# Lab2 import : Initialize memory via hooks
memory_id = get_ssm_parameter("/app/customersupport/agentcore/memory_id")
memory_hooks = CustomerSupportMemoryHooks(
    memory_id, memory_client, ACTOR_ID, SESSION_ID
)

# Lab3 import: Set up MCP client for gateway integration
try:
    # Get gateway URL from SSM
    gateway_id = get_ssm_parameter("/app/customersupport/agentcore/gateway_id")

    # Get gateway details
    gateway_client = boto3.client("bedrock-agentcore-control")
    gateway_response = gateway_client.get_gateway(gatewayIdentifier=gateway_id)
    gateway_url = gateway_response["gatewayUrl"]
    print(f"Gateway Endpoint - MCP URL: {gateway_url}")
    # Get authentication token
    cognito_config = get_or_create_cognito_pool()
    # Set up MCP client
    mcp_client = MCPClient(
        lambda: streamablehttp_client(
            gateway_url,
            headers={"Authorization": f"Bearer {cognito_config['bearer_token']}"},
        )
    )

    # Initialize MCP client
    mcp_client.start()

    # Get MCP tools
    mcp_tools = mcp_client.list_tools_sync()

except Exception as e:
    print(f"Warning: Could not initialize MCP client: {e}")
    mcp_tools = []

# Create the agent with all customer support tools (local + MCP)
agent = Agent(
    model=model,
    tools=[get_return_policy, get_product_info, get_technical_support] + mcp_tools,
    system_prompt=SYSTEM_PROMPT,
    hooks=[memory_hooks],
)

# Initialize the AgentCore Runtime App
app = BedrockAgentCoreApp()  #### AGENTCORE RUNTIME - LINE 2 ####


@app.entrypoint  #### AGENTCORE RUNTIME - LINE 3 ####
def invoke(payload):
    """AgentCore Runtime entrypoint function"""
    user_input = payload.get("prompt", "")
    # Invoke the agent

    response = agent(user_input)
    return response.message["content"][0]["text"]


if __name__ == "__main__":
    app.run()  #### AGENTCORE RUNTIME - LINE 4 ####
