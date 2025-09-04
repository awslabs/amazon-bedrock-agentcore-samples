# LlamaIndex Agent with Bedrock AgentCore Integration

| Information         | Details                                                                      |
|---------------------|------------------------------------------------------------------------------|
| Agent type          | Synchronous                                                                 |
| Agentic Framework   | LlamaIndex                                                                    |
| LLM model           | OpenAI GPT-4o-mini                                                    |
| Components          | AgentCore Runtime, Yahoo Finance Tools                                |
| Example complexity  | Easy                                                                 |
| SDK used            | Amazon BedrockAgentCore Python SDK                                           |

This example demonstrates how to integrate a LlamaIndex agent with AWS Bedrock AgentCore, enabling you to deploy a financial assistant with tool-using capabilities as a managed service.

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

The `llama_agent_hello_world.py` file contains a LlamaIndex agent with financial tools and basic math capabilities, integrated with Bedrock AgentCore:

```python
import asyncio
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.llms.openai import OpenAI
from llama_index.tools.yahoo_finance import YahooFinanceToolSpec

# Define custom function tools
def multiply(a: float, b: float) -> float:
    """Multiply two numbers and returns the product"""
    return a * b

def add(a: float, b: float) -> float:
    """Add two numbers and returns the sum"""
    return a + b

# Add other predefined tools
finance_tools = YahooFinanceToolSpec().to_tool_list()
finance_tools.extend([multiply, add])

# Create an agent workflow with our tools
agent = FunctionAgent(
    tools=finance_tools,
    llm=OpenAI(model="gpt-4o-mini"),
    system_prompt="You are a helpful assistant.",
)

from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()

@app.entrypoint
async def main(payload):
    # Run the agent
    response = await agent.run(payload.get("prompt","What is the current stock price of AMZN?"))
    print(response)
    return response.response.content

# Run the agent
if __name__ == "__main__":
    app.run()
```

### 4. Configure and Launch with Bedrock AgentCore Toolkit

```bash
# Configure your agent for deployment
agentcore configure -e llama_agent_hello_world.py

# Deploy your agent with OpenAI API key
agentcore launch --env OPENAI_API_KEY=sk-...
```

### 5. Testing Your Agent

You can test your agent locally before deploying to the cloud:

```bash
# Launch locally with your OpenAI API key
agentcore launch -l --env OPENAI_API_KEY=sk-...

# Invoke the agent with a query
agentcore invoke -l '{"prompt":"Price of AMZN stock today"}'
```

For cloud deployment, remove the `-l` flag:

```bash
# Deploy to cloud
agentcore launch --env OPENAI_API_KEY=sk-...

# Invoke the deployed agent
agentcore invoke '{"prompt":"Price of AMZN stock today"}'
```

The agent will:
1. Process your financial query
2. Use the Yahoo Finance tools to fetch real-time stock data
3. Provide a response with the requested financial information
4. Perform calculations if needed using the math tools

## How It Works

This agent uses LlamaIndex's agent framework to create a financial assistant that can:

1. Process natural language queries about stocks and financial data
2. Access real-time stock information through Yahoo Finance tools
3. Perform basic mathematical operations when needed
4. Provide comprehensive responses based on the data

The agent is wrapped with the Bedrock AgentCore framework, which handles:
- Deployment to AWS
- Scaling and management
- Request/response handling
- Environment variable management

## Additional Resources

- [LlamaIndex Documentation](https://docs.llamaindex.ai/en/stable/use_cases/agents/)
- [Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-core.html)
- [OpenAI API Documentation](https://platform.openai.com/docs/api-reference)
- [Yahoo Finance API Documentation](https://pypi.org/project/yfinance/)