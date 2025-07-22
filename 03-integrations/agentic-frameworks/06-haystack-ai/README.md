# Haystack AI Agent with Bedrock AgentCore Integration

| Information         | Details                                                                      |
|---------------------|------------------------------------------------------------------------------|
| Agent type          | Synchronous                                                                 |
| Agentic Framework   | Haystack AI                                                                    |
| LLM model           | Anthropic Claude 3.7 Sonnet                                                     |
| Components          | AgentCore Runtime                                |
| Example complexity  | Easy                                                                 |
| SDK used            | Amazon BedrockAgentCore Python SDK                                           |

These example demonstrate how to integrate a Haystack AI agents with AWS Bedrock AgentCore, enabling you to deploy your agent as a managed service. You can use the `agentcore` CLI to configure and launch these agents. 

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

The `haystack_github_agent.py` file contains a Haystack AI agent with GitHub issue viewing capabilities, integrated with Bedrock AgentCore:

```python
import os
os.environ["BYPASS_TOOL_CONSENT"]="true"

from haystack.components.agents import Agent
from haystack.dataclasses import Document, ChatMessage
from haystack_integrations.components.generators.amazon_bedrock import AmazonBedrockChatGenerator
from haystack_integrations.tools.github import GitHubIssueViewerTool

tool = GitHubIssueViewerTool()

# Create the agent with the GitHub tool
tool_calling_agent = Agent(
    chat_generator=AmazonBedrockChatGenerator(model="us.anthropic.claude-3-7-sonnet-20250219-v1:0"),
    system_prompt="""You're a helpful agent. When asked about GitHub issues, use the github issue viewer tool to find the information and then summarize the findings based on the link provided.""",
    tools=[tool]
)

# Integrate with Bedrock AgentCore
from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()

@app.entrypoint
def agent_invocation(payload, context):
    """Handler for agent invocation"""
    payload = payload.get("prompt", "No prompt found in input, please guide customer to create a json payload with prompt key")
    user_message = ChatMessage.from_user(payload)
    result = tool_calling_agent.run(messages=[user_message])
    result = result["messages"][-1].text
    return {"result": result}

app.run()
```

### 4. Configure and Launch with Bedrock AgentCore Toolkit

```bash
# Configure your agent for deployment
agentcore configure -e haystack_github_agent.py

# Deploy your agent
agentcore launch
```

### 5. Testing Your Agent

Once deployed, you can test your agent using:

```bash
agentcore invoke '{"prompt": "Explain the Github issue at the following url GH_ISSUE_URL"}'
```