import os
from strands import Agent, tool
from strands_tools import calculator
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()


@tool
def weather():
    """Get weather"""
    return "sunny"


model_id = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")
model = BedrockModel(model_id=model_id)

agent = Agent(
    model=model,
    tools=[calculator, weather],
    system_prompt="You're a helpful assistant. You can do simple math calculation, and tell the weather.",
)


@app.entrypoint
def strands_agent_bedrock(payload):
    user_input = payload.get("prompt")
    response = agent(user_input)
    return response.message["content"][0]["text"]
