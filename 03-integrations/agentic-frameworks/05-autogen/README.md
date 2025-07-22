# AutoGen Agent with Bedrock AgentCore Integration

| Information         | Details                                                                      |
|---------------------|------------------------------------------------------------------------------|
| Agent type          | Synchronous                                                                 |
| Agentic Framework   | Autogen                                                                    |
| LLM model           | Open AI GPT 4o                                                    |
| Components          | AgentCore Runtime                                |
| Example complexity  | Easy                                                                 |
| SDK used            | Amazon BedrockAgentCore Python SDK                                           |

This example demonstrates how to integrate an AutoGen agent with AWS Bedrock AgentCore, enabling you to deploy a conversational agent with tool-using capabilities as a managed service.

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer and resolver
- AWS account with Bedrock access
- OpenAI API key (for the model client)

## Setup Instructions

### 1. Create a Python Environment with uv

```bash
# Install uv if you don't have it already
pip install uv

# Create and activate a virtual environment
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 2. Install Requirements

```bash
uv pip install -r requirements.txt
```

### 3. Understanding the Agent Code

The `autogen_agent_hello_world.py` file contains an AutoGen agent with a weather tool capability, integrated with Bedrock AgentCore:

```python
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
import asyncio
import logging

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("autogen_agent")

# Initialize the model client
model_client = OpenAIChatCompletionClient(
    model="gpt-4o",
)

# Define a simple function tool that the agent can use
async def get_weather(city: str) -> str:
    """Get the weather for a given city."""
    return f"The weather in {city} is 73 degrees and Sunny."

# Define an AssistantAgent with the model and tool
agent = AssistantAgent(
    name="weather_agent",
    model_client=model_client,
    tools=[get_weather],
    system_message="You are a helpful assistant.",
    reflect_on_tool_use=True,
    model_client_stream=True,  # Enable streaming tokens
)

# Integrate with Bedrock AgentCore
from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()

@app.entrypoint
async def main(payload):
    # Process the user prompt
    prompt = payload.get("prompt", "Hello! What can you help me with?")
    
    # Run the agent
    result = await Console(agent.run_stream(task=prompt))
    
    # Extract the response content for JSON serialization
    if result and hasattr(result, 'messages') and result.messages:
        last_message = result.messages[-1]
        if hasattr(last_message, 'content'):
            return {"result": last_message.content}
    
    return {"result": "No response generated"}

app.run()
```

### 4. Configure and Launch with Bedrock AgentCore Toolkit

```bash
# Configure your agent for deployment
agentcore configure -e 

# Deploy your agent with OpenAI API key
agentcore launch --env OPENAI_API_KEY=...
```


### 5. Testing Your Agent

Launch locally to test for:
`agentcore launch -l --env OPENAI_API_KEY=...`


```bash
agentcore invoke -l '{"prompt": "what is the weather in NYC?"}'
```

The agent will:
1. Process your query
2. Use the weather tool if appropriate
3. Provide a response based on the tool's output

> Note: Remove the -l to launch and invoke on clpud

## How It Works

This agent uses AutoGen's agent framework to create an assistant that can:

1. Process natural language queries
2. Decide when to use tools based on the query
3. Execute tools and incorporate their results into responses
4. Stream responses in real-time

The agent is wrapped with the Bedrock AgentCore framework, which handles:
- Deployment to AWS
- Scaling and management
- Request/response handling
- Environment variable management

## Additional Resources

- [AutoGen Documentation](https://microsoft.github.io/autogen/)
- [Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-core.html)
- [OpenAI API Documentation](https://platform.openai.com/docs/api-reference)