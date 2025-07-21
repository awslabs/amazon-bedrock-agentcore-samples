import asyncio
from bedrock_agentcore.identity.auth import requires_api_key
from strands import Agent
from strands.models.openai import OpenAIModel
from strands_tools import calculator
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# Global agent variable
agent = None
AZURE_API_KEY_FROM_CREDS_PROVIDER = ""

@requires_api_key(
    provider_name="OPENAI-key" # replace with your own credential provider name
)
async def need_api_key(*, api_key: str):
    global AZURE_API_KEY_FROM_CREDS_PROVIDER
    print(f'received api key for async func: {api_key}')
    AZURE_API_KEY_FROM_CREDS_PROVIDER = api_key

def create_model():
    """Create the OpenAI model with the API key"""
    return OpenAIModel(
        client_args={
            "api_key": AZURE_API_KEY_FROM_CREDS_PROVIDER, 
        },
        model_id="gpt-4o",
        params={
            "max_tokens": 1000,
            "temperature": 0.7,
        }
    )

app = BedrockAgentCoreApp()

@app.entrypoint
async def strands_agent_open_ai(payload):
    """
    Invoke the agent with a payload
    """
    global AZURE_API_KEY_FROM_CREDS_PROVIDER, agent
    
    print(f"Entrypoint called with AZURE_API_KEY_FROM_CREDS_PROVIDER: '{AZURE_API_KEY_FROM_CREDS_PROVIDER}'")
    
    # Get API key if not already retrieved
    if not AZURE_API_KEY_FROM_CREDS_PROVIDER:
        print("Attempting to retrieve API key...")
        try:
            await need_api_key(api_key="")
            print(f"API key retrieved: '{AZURE_API_KEY_FROM_CREDS_PROVIDER}'")
            print("Environment variable AZURE_API_KEY set")
        except Exception as e:
            print(f"Error retrieving API key: {e}")
            raise
    else:
        print("API key already available")
    
    # Initialize agent after API key is set
    if agent is None:
        print("Initializing agent with API key...")
        model = create_model()
        agent = Agent(model=model, tools=[calculator])
    user_input = payload.get("prompt")
    print(f"User input: {user_input}")
    
    try:
        response = agent(user_input)
        print(f"Agent response: {response}")
        return response.message['content'][0]['text']
    except Exception as e:
        print(f"Error in agent processing: {e}")
        raise

if __name__ == "__main__":
    app.run()