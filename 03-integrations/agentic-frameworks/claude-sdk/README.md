# Claude Agent SDK with Bedrock AgentCore Integration

| Information         | Details                                                                      |
|---------------------|------------------------------------------------------------------------------|
| Agent type          | Asynchronous with Streaming                                                 |
| Agentic Framework   | Claude Agent SDK                                                           |
| LLM model           | Anthropic Claude (via Bedrock)                                              |
| Components          | AgentCore Runtime                                |
| Example complexity  | Easy                                                                 |
| SDK used            | Amazon BedrockAgentCore Python SDK, Claude Agent SDK                        |

This example demonstrates how to integrate Claude Agent SDK with AWS Bedrock AgentCore, enabling you to deploy your Claude-powered agent as a managed service with streaming support. You can use the `agentcore` CLI to configure and launch this agent.

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer and resolver
- AWS account with Bedrock AgentCore access
- Node.js and npm (for Claude Code CLI)

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

The `agent.py` file contains a Claude Agent SDK implementation with streaming support, integrated with Bedrock AgentCore:

```python
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

async def basic_example(prompt):
    """Basic example with streaming."""
    async for message in query(prompt=prompt):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"Claude: {block.text}")
        yield message

@app.entrypoint
async def run_main(payload):
    """Handler for agent invocation with streaming support"""
    async for message in basic_example(payload["prompt"]):
        yield message

app.run()
```

The agent supports three modes:
- **Mode 1**: Basic example - simple question answering
- **Mode 2**: With custom options - customized system prompt and max turns
- **Mode 3**: With tools - file reading and writing capabilities

### 4. Configure and Launch with Bedrock AgentCore Toolkit

```bash
# Configure your agent for deployment (without memory)
agentcore configure -e agent.py --disable-memory

# Deploy your agent with environment variables
agentcore launch --env CLAUDE_CODE_USE_BEDROCK=1 --env AWS_BEARER_TOKEN_BEDROCK=<your-token>
```

**Note**: The Claude Agent SDK requires either `ANTHROPIC_API_KEY` or AWS Bedrock access configured as environment variables. This example uses:
- `CLAUDE_CODE_USE_BEDROCK=1` to enable Bedrock integration
- `AWS_BEARER_TOKEN_BEDROCK` for authentication with Bedrock

You can provide these environment variables either in the Dockerfile or inline with the `--env` option as shown above. For more details on configuration options, see the [Claude Agent SDK documentation](https://docs.claude.com/en/api/agent-sdk/overview#core-concepts).

### 5. Testing Your Agent

Once deployed, you can test your agent using:

```bash
# Basic query (mode 1)
agentcore invoke '{"prompt":"What is the capital of France?", "mode":1}'

# With custom options (mode 2)
agentcore invoke '{"prompt":"Explain quantum computing", "mode":2}'

# With tools (mode 3)
agentcore invoke '{"prompt":"Read the contents of test.txt", "mode":3}'
```

## Key Features

- **Streaming Support**: Real-time response streaming for better user experience
- **Multiple Modes**: Three operational modes for different use cases
- **Tool Integration**: Built-in support for Read and Write tools
- **Async/Await**: Full asynchronous processing for optimal performance
- **BedrockAgentCore Integration**: Seamless deployment as a managed AWS service

## Architecture

The agent uses a layered architecture:
1. **Claude Agent SDK**: Handles LLM interactions via `query()` function
2. **Example Functions**: Process messages and yield them for streaming
3. **Main Function**: Routes requests based on mode parameter
4. **BedrockAgentCoreApp**: Provides runtime environment and handles deployment

## Customization

You can customize the agent by:
- Adding more tools to the `allowed_tools` list
- Modifying the `system_prompt` in `ClaudeAgentOptions`
- Adjusting `max_turns` for conversation length
- Creating new example functions for additional use cases

## Clean Up

When you're done with the agent, you can clean up the deployed resources.

### Memory
Since this example is configured with `--disable-memory`, no memory resources were created, so there's nothing to remove for memory.

### Agent Runtime
To destroy the agent and all its associated AWS resources, use the `agentcore destroy` command:

```bash
agentcore destroy
```

You'll see output similar to:

```
⚠️  About to destroy resources for agent 'claudesdkagent'

Current deployment:
  • Agent ARN: arn:aws:bedrock-agentcore:us-east-1:XXXXXXXXXXXX:runtime/claudesdkagent-XXXXXXXXXX
  • Agent ID: claudesdkagent-XXXXXXXXXX
  • ECR Repository: XXXXXXXXXXXX.dkr.ecr.us-east-1.amazonaws.com/bedrock-agentcore-claudesdkagent
  • Execution Role: arn:aws:iam::XXXXXXXXXXXX:role/AmazonBedrockAgentCoreSDKRuntime-us-east-1-XXXXXXXXXX

This will permanently delete AWS resources and cannot be undone!
Are you sure you want to destroy the agent 'claudesdkagent' and all its resources? [y/N]:
```

Type `y` to confirm and permanently delete the agent and all its associated resources including the ECR repository and execution role.
