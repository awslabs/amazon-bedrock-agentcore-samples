# Strands Agent with Bedrock AgentCore Integration

| Information         | Details                                                                      |
|---------------------|------------------------------------------------------------------------------|
| Agent type          | Synchronous                                                                 |
| Agentic Framework   | Strands                                                                    |
| LLM model           | Anthropic Claude 3 Haiku                                                     |
| Components          | AgentCore Runtime                                |
| Example complexity  | Easy                                                                 |
| SDK used            | Amazon BedrockAgentCore Python SDK                                           |

These example demonstrate how to integrate a Strands agents with AWS Bedrock AgentCore, enabling you to deploy your agent as a managed service. You can use the `agentcore` CLI to configure and launch these agents. 

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer and resolver
- AWS account with Bedrock Agentcore access

## Setup Instructions

### 1. Create a Python Environment with uv

```bash
# Install uv if you don't have it already

# Create and activate a virtual environment
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 2. Install Requirements

```bash
uv pip install -r requirements.txt
```

### 3. Understanding the Agent Code

The `strands_agent_file_system.py` file contains a simple Strands agent with file system capabilities, integrated with Bedrock AgentCore:

```python
import os
os.environ["BYPASS_TOOL_CONSENT"]="true"

from strands import Agent
from strands_tools import file_read, file_write, editor

# Initialize Strands agent with file system tools
agent = Agent(tools=[file_read, file_write, editor])

# Integrate with Bedrock AgentCore
from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()

@app.entrypoint
def agent_invocation(payload, context):
    """Handler for agent invocation"""
    user_message = payload.get("prompt", "No prompt found in input, please guide customer to create a json payload with prompt key")
    result = agent(user_message)
    return {"result": result.message}

app.run()
```

### 4. Configure and Launch with Bedrock AgentCore Toolkit

```bash
# Configure your agent for deployment
agentcore configure -e strands_agent_file_system.py

# Deploy your agent
agentcore launch
```

### 5. Testing Your Agent

Once deployed, you can test your agent using:

```bash
agentcore invoke '{"prompt":"hello"}'
```