import os
from dotenv import load_dotenv
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
from bedrock_agentcore import BedrockAgentCoreApp

# Load environment variables from .env file
load_dotenv()

APP_NAME = "HostAgentA2A"

app = BedrockAgentCoreApp()

session_service = InMemorySessionService()

root_agent = None


@app.entrypoint
async def call_agent(payload: dict, context):
    global root_agent

    session_id = context.session_id

    # actor_id = request_headers["x-amzn-bedrock-agentCore-runtime-custom-actor"]

    # if not actor_id:
    #     raise Exception("Actor id is not is not set")
    # TODO: Actor Id
    # Ensure session exists before running
    actor_id = "Actor1"

    if not session_id:
        raise Exception("Context session_id is not set")

    if not root_agent:
        # Import agent creation inside entrypoint so workload identity is available
        from agent import get_agent_and_card

        # Create root agent once - LazyClientFactory creates fresh httpx clients
        # on each A2A invocation in the current event loop context
        root_agent, agent_card = await get_agent_and_card(
            session_id=session_id, actor_id=actor_id
        )

        yield agent_card

    query = payload.get("prompt")

    if not query:
        raise KeyError("'prompt' field is required in payload")

    in_memory_session = session_service.get_session_sync(
        app_name=APP_NAME, user_id=actor_id, session_id=session_id
    )

    if not in_memory_session:
        # Session doesn't exist, create it
        _ = session_service.create_session_sync(
            app_name=APP_NAME, user_id=actor_id, session_id=session_id
        )

    runner = Runner(
        agent=root_agent, app_name=APP_NAME, session_service=session_service
    )

    content = types.Content(role="user", parts=[types.Part(text=query)])

    # Use async run to properly maintain event loop across invocations
    async for event in runner.run_async(
        user_id=actor_id, session_id=session_id, new_message=content
    ):
        yield event


if __name__ == "__main__":
    app.run()  # Ready to run on Bedrock AgentCore
