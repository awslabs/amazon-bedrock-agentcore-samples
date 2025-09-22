# Claude Code Python SDK for AgentCore

Official Python SDK integration for running Claude Code on Amazon Bedrock AgentCore.

## Overview

This SDK provides two approaches for integrating Claude Code with AgentCore:

1. **Direct SDK Integration** - Uses the official Claude Code Python SDK with `query()` and `ClaudeSDKClient`
2. **AgentCore Wrapper** - Deploys Claude Code as a managed agent on AgentCore infrastructure

## Installation

1. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Ensure Claude Code CLI is installed:
   ```bash
   # Install via npm
   npm install -g @anthropic/claude-code-cli
   
   # Verify installation
   claude --version
   ```

## Quick Start

### Using the Official SDK Directly

For one-off tasks (new session each time):

```python
import asyncio
from claude_code_sdk import query, ClaudeCodeOptions

async def main():
    options = ClaudeCodeOptions(
        allowed_tools=["Read", "Write", "Bash"],
        permission_mode="acceptEdits"
    )
    
    async for message in query(
        prompt="Create a Python web server",
        options=options
    ):
        print(message)

asyncio.run(main())
```

For continuous conversations (maintains context):

```python
from claude_code_sdk import ClaudeSDKClient, ClaudeCodeOptions
import asyncio

async def conversation():
    options = ClaudeCodeOptions(
        allowed_tools=["Read", "Write", "Bash"]
    )
    
    async with ClaudeSDKClient(options) as client:
        # First question
        await client.query("Create a file called app.py")
        async for msg in client.receive_response():
            print(msg)
        
        # Follow-up - Claude remembers the context
        await client.query("Now add a Flask server to that file")
        async for msg in client.receive_response():
            print(msg)

asyncio.run(conversation())
```

### Deploying on AgentCore

Use the wrapper to deploy Claude Code as an AgentCore agent:

```bash
# Configure the agent
agentcore configure -e claude_code_agentcore_wrapper.py

# Deploy to AgentCore
agentcore launch

# Test the deployment
agentcore invoke '{
  "prompt": "Create a website showing NYC running clubs and deploy to S3",
  "options": {
    "allowed_tools": ["Read", "Write", "Bash", "WebFetch"]
  }
}'
```

## SDK Components

### Core Functions

#### `query()`
Creates a new session for each interaction. Best for:
- One-off tasks
- Independent operations
- Simple automation scripts

```python
from claude_code_sdk import query, ClaudeCodeOptions

async def example():
    async for message in query(
        prompt="Your task here",
        options=ClaudeCodeOptions(...)
    ):
        # Process messages
        pass
```

#### `ClaudeSDKClient`
Maintains conversation context. Best for:
- Multi-turn conversations
- Follow-up questions
- Interactive applications
- Complex workflows

```python
from claude_code_sdk import ClaudeSDKClient

async def example():
    async with ClaudeSDKClient() as client:
        await client.query("First prompt")
        async for msg in client.receive_response():
            # Process response
            pass
        
        # Follow-up in same context
        await client.query("Second prompt")
        async for msg in client.receive_response():
            # Process response
            pass
```

### Configuration Options

```python
from claude_code_sdk import ClaudeCodeOptions

options = ClaudeCodeOptions(
    # Tool configuration
    allowed_tools=["Read", "Write", "Bash", "WebFetch"],
    disallowed_tools=["KillBash"],
    
    # Prompts
    system_prompt="You are an expert Python developer",
    append_system_prompt="Additional instructions here",
    
    # Execution control
    permission_mode="acceptEdits",  # or "default", "plan", "bypassPermissions"
    max_turns=10,
    max_thinking_tokens=8000,
    
    # Working environment
    cwd="/path/to/project",
    add_dirs=["/additional/path"],
    env={"MY_VAR": "value"},
    
    # Model selection
    model="claude-3-opus-20240229",
    
    # Session management
    continue_conversation=False,
    resume="session-id-here"
)
```

### Custom Tools

Create custom MCP tools for your specific needs:

```python
from claude_code_sdk import tool, create_sdk_mcp_server

@tool("calculate", "Perform calculations", {"expression": str})
async def calculate(args):
    result = eval(args["expression"], {"__builtins__": {}})
    return {
        "content": [{
            "type": "text",
            "text": f"Result: {result}"
        }]
    }

# Create server with custom tools
server = create_sdk_mcp_server(
    name="math_tools",
    tools=[calculate]
)

# Use with Claude
options = ClaudeCodeOptions(
    mcp_servers={"math": server},
    allowed_tools=["mcp__math__calculate"]
)
```

## AgentCore Integration

The `claude_code_agentcore_wrapper.py` provides seamless integration with AgentCore:

### Single Prompt Execution

```json
{
  "prompt": "Create a REST API for task management",
  "options": {
    "allowed_tools": ["Read", "Write", "Bash"],
    "permission_mode": "acceptEdits"
  }
}
```

### Multi-turn Conversation

```json
{
  "prompts": [
    "Create a basic web application",
    "Add user authentication",
    "Deploy to AWS"
  ],
  "options": {
    "allowed_tools": ["Read", "Write", "Bash"],
    "cwd": "/workspace"
  }
}
```

## Examples

### NYC Running Clubs Website (Complete Workflow)

```python
import asyncio
from claude_code_sdk import query, ClaudeCodeOptions

async def deploy_website():
    options = ClaudeCodeOptions(
        allowed_tools=["Read", "Write", "Bash", "WebFetch"],
        permission_mode="acceptEdits",
        append_system_prompt="""
        Use boto3 for AWS operations.
        Ensure the website is mobile-responsive.
        Return the final CloudFront URL.
        """
    )
    
    prompt = """
    Create a website listing NYC running clubs with their schedules.
    Deploy it to S3 with static hosting and set up CloudFront.
    """
    
    async for message in query(prompt=prompt, options=options):
        # Claude Code will autonomously:
        # 1. Research NYC running clubs
        # 2. Create HTML/CSS/JS files
        # 3. Set up S3 bucket
        # 4. Deploy files
        # 5. Configure CloudFront
        # 6. Return the URL
        print(message)

asyncio.run(deploy_website())
```

### Interactive Development Session

```python
from claude_code_sdk import ClaudeSDKClient, ClaudeCodeOptions
import asyncio

async def dev_session():
    options = ClaudeCodeOptions(
        allowed_tools=["Read", "Write", "Bash", "Grep"],
        permission_mode="acceptEdits"
    )
    
    async with ClaudeSDKClient(options) as client:
        # Create initial structure
        await client.query("Create a Python package structure for 'myapp'")
        async for msg in client.receive_response():
            pass
        
        # Add functionality
        await client.query("Add a CLI interface using Click")
        async for msg in client.receive_response():
            pass
        
        # Add tests
        await client.query("Create unit tests for all modules")
        async for msg in client.receive_response():
            pass
        
        # Set up CI/CD
        await client.query("Add GitHub Actions workflow for testing")
        async for msg in client.receive_response():
            pass

asyncio.run(dev_session())
```

### Using Hooks for Control

```python
from claude_code_sdk import (
    ClaudeSDKClient,
    ClaudeCodeOptions,
    HookMatcher,
    HookContext
)

async def validate_file_operations(input_data, tool_use_id, context):
    """Validate and log all file operations."""
    tool_name = input_data.get('tool_name')
    
    if tool_name == 'Write':
        file_path = input_data.get('tool_input', {}).get('file_path', '')
        print(f"[AUDIT] Writing to: {file_path}")
        
        # Block writes to system directories
        if file_path.startswith('/system/'):
            return {
                'hookSpecificOutput': {
                    'hookEventName': 'PreToolUse',
                    'permissionDecision': 'deny',
                    'permissionDecisionReason': 'System directory write blocked'
                }
            }
    
    return {}

async def main():
    options = ClaudeCodeOptions(
        hooks={
            'PreToolUse': [
                HookMatcher(hooks=[validate_file_operations])
            ]
        },
        allowed_tools=["Read", "Write"]
    )
    
    async with ClaudeSDKClient(options) as client:
        await client.query("Create a config file")
        async for msg in client.receive_response():
            pass

asyncio.run(main())
```

## Message Types

The SDK provides typed message objects:

- `UserMessage` - User input
- `AssistantMessage` - Claude's responses with content blocks
- `SystemMessage` - System metadata
- `ResultMessage` - Final result with cost and usage info

Content blocks include:
- `TextBlock` - Text responses
- `ThinkingBlock` - Claude's reasoning process
- `ToolUseBlock` - Tool execution requests
- `ToolResultBlock` - Tool execution results

## Error Handling

```python
from claude_code_sdk import (
    query,
    CLINotFoundError,
    ProcessError,
    CLIJSONDecodeError
)

try:
    async for message in query(prompt="Your task"):
        print(message)
except CLINotFoundError:
    print("Claude Code CLI not installed")
except ProcessError as e:
    print(f"Process failed: {e.exit_code}")
except CLIJSONDecodeError as e:
    print(f"JSON parse error: {e}")
```

## Best Practices

1. **Choose the Right Interface**:
   - Use `query()` for one-off tasks
   - Use `ClaudeSDKClient` for conversations

2. **Tool Selection**:
   - Only enable tools needed for the task
   - Use `disallowed_tools` for security

3. **Session Management**:
   - Save session IDs for resuming conversations
   - Use `continue_conversation` for follow-ups

4. **Error Handling**:
   - Always handle potential errors
   - Check `ResultMessage.is_error` field

5. **Cost Monitoring**:
   - Track `total_cost_usd` in ResultMessage
   - Set `max_turns` to limit costs

## Troubleshooting

### Claude Code CLI Not Found

```bash
# Install Claude Code CLI
npm install -g @anthropic/claude-code-cli

# Or download from releases
# https://github.com/anthropic/claude-code/releases
```

### Permission Denied

Ensure proper AWS credentials:
```bash
aws configure
```

### Timeout Issues

Increase timeout for long-running tasks:
```python
options = ClaudeCodeOptions(
    max_turns=20  # Allow more conversation turns
)
```

## Support

- [Claude Code Documentation](https://docs.claude.ai/code)
- [AgentCore Documentation](https://docs.aws.amazon.com/bedrock/agentcore)
- [SDK Reference](https://docs.claude.ai/code/python-sdk-reference)

## License

See LICENSE file in the repository root.
