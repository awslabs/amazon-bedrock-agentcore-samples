import logging

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
from lab_helpers.utils import get_or_create_cognito_pool, get_ssm_parameter
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

# Add a handler to see the logs
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s", handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("agentcore-app")
logger.setLevel(logging.DEBUG)


class CustomerSupportAgent:
    def __init__(self):
        # Lab1 import: Create the Bedrock model
        self.model = BedrockModel(model_id=MODEL_ID)
        self.cognito_config = get_or_create_cognito_pool()
        self.session_id = None
        self.memory_hook = None

    # Create the agent with all customer support tools (local + MCP)
    async def create_client(self, gateway_url):
        # Set up MCP client
        if self.cognito_config:
            try:
                # Lab3 import: Set up MCP client for gateway integration
                self.gateway_client = MCPClient(
                    lambda: streamablehttp_client(
                        gateway_url,
                        headers={
                            "Authorization": f"Bearer {self.cognito_config['access_token']}"
                        },
                    )
                )
            except Exception as e:
                logger.error(f"Could not initialize MCP client: {e}")
        else:
            logger.error("Failed to initialize the agent without a Bearer token")

    def invoke(self, user_input: str):
        """AgentCore Runtime entrypoint function"""
        try:
            with self.gateway_client:
                agent = Agent(
                    model=self.model,
                    tools=[get_return_policy, get_product_info, get_technical_support]
                    + self.gateway_client.list_tools_sync(),
                    system_prompt=SYSTEM_PROMPT,
                    hooks=[self.memory_hook],
                )
                response = agent(user_input)
            return response
        except Exception as e:
            return f"Error while invoking Agent {e}"

    async def stream(self, user_query: str):
        try:
            async for event in self.agent.stream_async(user_query):
                if "data" in event:
                    # Only stream text chunks to the client
                    yield event["data"]
        except Exception as e:
            yield f"We are unable to process your request at the moment. Error: {e}"


# Lab2 import : Initialize memory via hooks
memory_id = get_ssm_parameter("/app/customersupport/agentcore/memory_id")
# Lab 3: Get gateway URL from SSM
gateway_url = get_ssm_parameter("/app/customersupport/agentcore/gateway_url")
# Initialize the customer support agent
customer_support = CustomerSupportAgent()
# Initialize the AgentCore Runtime App
app = BedrockAgentCoreApp()  #### AGENTCORE RUNTIME - LINE 2 ####


@app.entrypoint  #### AGENTCORE RUNTIME - LINE 3 ####
async def invoke(payload, context=None):
    """AgentCore Runtime entrypoint function"""
    # if not customer_support.agent:
    logger.info("initializing agent")
    memory_hook = CustomerSupportMemoryHooks(
        memory_id, memory_client, ACTOR_ID, context.session_id or SESSION_ID
    )
    customer_support.memory_hook = memory_hook
    # Initialize MCP client
    await customer_support.create_client(gateway_url)
    # Invoke the agent
    user_input = payload.get("prompt", "")
    response = customer_support.invoke(user_input)
    return response


if __name__ == "__main__":
    app.run()  #### AGENTCORE RUNTIME - LINE 4 ####
