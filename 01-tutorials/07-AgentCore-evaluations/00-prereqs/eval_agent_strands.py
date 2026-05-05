from strands import Agent, tool
from strands_tools import calculator
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands.models import BedrockModel

app = BedrockAgentCoreApp()


@tool
def weather():
    """Get current weather conditions."""
    return "sunny"


model_id = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
model = BedrockModel(model_id=model_id)

_SESSION_AGENTS: dict = {}


@app.entrypoint
async def strands_agent_bedrock(payload, context):
    """Invoke the agent with a payload."""
    user_input = payload.get("prompt", "")
    session_id = context.session_id

    if session_id and session_id in _SESSION_AGENTS:
        agent = _SESSION_AGENTS[session_id]
    else:
        agent = Agent(
            model=model,
            tools=[calculator, weather],
            system_prompt="You're a helpful assistant. You can do simple math calculation, and tell the weather.",
        )
        if session_id:
            _SESSION_AGENTS[session_id] = agent

    parts = []
    async for event in agent.stream_async(user_input):
        if "data" in event:
            parts.append(str(event["data"]))
    return "".join(parts)


if __name__ == "__main__":
    app.run()
