# OpenAI Agents with Bedrock AgentCore Integration

| Information         | Details                                                                      |
|---------------------|------------------------------------------------------------------------------|
| Agent type          | Synchronous with and without Handoffs                                                   |
| Agentic Framework   | OpenAI Agents SDK                                                       |
| LLM model           | GPT-4o                                                              |
| Components          | AgentCore Runtime                                         |
| Example complexity  | Medium                                                                       |
| SDK used            | Amazon BedrockAgentCore Python SDK, OpenAI Agents SDK                   |

This example demonstrates how to integrate OpenAI Agents with AWS Bedrock AgentCore, showcasing agent handoffs for specialized tasks.

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer and resolver
- AWS account with Bedrock access
- OpenAI API key

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

## Example 1: Hello World Agent

The `openai_agents_hello_world.py` file contains a simple OpenAI agent with web search capabilities and Bedrock AgentCore integration:

```python
from agents import Agent, Runner, WebSearchTool
import logging
import sys

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("openai_agents")

# Initialize the agent with web search tool
agent = Agent(
    name="Assistant",
    tools=[WebSearchTool()],
)

async def main(query=None):
    if query is None:
        query = "Which coffee shop should I go to, taking into account my preferences and the weather today in SF?"
    
    logger.debug(f"Running agent with query: {query}")
    result = await Runner.run(agent, query)
    return result

# Integration with Bedrock AgentCore
from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()

@app.entrypoint
async def agent_invocation(payload, context):
    query = payload.get("prompt", "How can I help you today?")
    result = await main(query)
    return {"result": result.final_output}

if __name__ == "__main__":
    app.run()
```

## Example 2: Agent Handoffs

The `openai_agents_handoff_example.py` file demonstrates how to create a system of agents with specialized roles that can hand off tasks to each other:

```python
# Create specialized agents for different tasks
travel_agent = Agent(
    name="Travel Expert",
    instructions=(
        "You are a travel expert who helps users plan their trips. "
        "Use web search to find up-to-date information about destinations, "
        "flights, accommodations, and travel requirements."
    ),
    tools=[WebSearchTool()]
)

food_agent = Agent(
    name="Food Expert",
    instructions=(
        "You are a food expert who helps users find great dining options. "
        "Use web search to find information about restaurants, local cuisine, "
        "food tours, and dietary accommodations."
    ),
    tools=[WebSearchTool()]
)

# Create the main triage agent that can hand off to specialized agents
triage_agent = Agent(
    name="Travel Assistant",
    instructions=(
        "You are a helpful travel assistant. "
        "If the user asks about travel planning, destinations, flights, or accommodations, "
        "hand off to the Travel Expert. "
        "If the user asks about food, restaurants, or dining options, "
        "hand off to the Food Expert."
    ),
    handoffs=[travel_agent, food_agent]
)
```

### How Handoffs Work

1. The triage agent receives the initial user query
2. Based on the query content, it determines which specialized agent should handle the request
3. The appropriate specialized agent (Travel Expert or Food Expert) takes over
4. The specialized agent uses its tools (web search) to gather information
5. The final response is returned to the user

This pattern allows for:
- Specialized knowledge and behavior for different domains
- Clear separation of concerns between agents
- More accurate and relevant responses for domain-specific queries

## Configure and Launch with Bedrock AgentCore

```bash
# Configure your agent for deployment
agentcore configure

# Deploy your agent with OpenAI API key
agentcore deploy --app-file openai_agents_handoff_example.py -l --env OPENAI_API_KEY=your_api_key_here
```

## Testing Your Agent

```bash
agentcore invoke --prompt "I'm planning a trip to Japan next month. What should I know?"
```

The system will:
1. Process your query through the triage agent
2. Hand off to the Travel Expert agent
3. Use web search to gather information about Japan travel
4. Return a comprehensive response

## Additional Resources

- [OpenAI Agents Documentation](https://platform.openai.com/docs/assistants/overview)
- [Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-core.html)