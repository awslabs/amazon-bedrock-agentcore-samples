# Claude Code Headless Mode for AgentCore

Run Claude Code as an autonomous coding agent on Amazon Bedrock AgentCore without any interactive UI.

## Overview

This implementation allows you to:
- Execute Claude Code programmatically through AgentCore
- Handle complex, multi-step coding tasks autonomously
- Deploy applications and infrastructure from natural language prompts
- Maintain conversation context across multiple interactions

## Prerequisites

1. **Claude Code CLI**: Install Claude Code command-line interface
   ```bash
   # Option 1: Using npm
   npm install -g @anthropic/claude-code-cli
   
   # Option 2: Download binary from releases
   # https://github.com/anthropic/claude-code/releases
   ```

2. **AWS Configuration**: Ensure AWS CLI is configured
   ```bash
   aws configure
   ```

3. **Python Environment**: Python 3.10+ with pip

## Installation

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Verify Claude Code installation:
   ```bash
   claude --version
   ```

## Configuration

### Environment Variables

Set these optional environment variables to customize behavior:

```bash
# Enable verbose logging
export CLAUDE_CODE_VERBOSE=true

# Set execution timeout (seconds, default: 600)
export CLAUDE_CODE_TIMEOUT=1200

# AWS region for deployments
export AWS_DEFAULT_REGION=us-east-1
```

## Deployment to AgentCore

1. Configure the agent:
   ```bash
   agentcore configure -e claude_code_agent.py
   ```

2. Deploy to AgentCore:
   ```bash
   agentcore launch
   ```

3. Test the deployment:
   ```bash
   agentcore invoke '{"prompt":"Create a simple hello world Python script"}'
   ```

## Usage Examples

### Basic Code Generation

```json
{
  "prompt": "Create a Python Flask API with CRUD operations for a todo list application"
}
```

### AWS Deployment

```json
{
  "prompt": "Create a static website showing NYC running clubs with their schedules and locations. Deploy it to S3 and set up CloudFront distribution. Return the CloudFront URL.",
  "allowed_tools": "Bash,Read,Write,Replace,Search,List,WebFetch",
  "permission_mode": "acceptEdits"
}
```

### Multi-turn Conversation

First request:
```json
{
  "prompt": "Create a React application for task management"
}
```

Continue the conversation:
```json
{
  "prompt": "Now add authentication using AWS Cognito",
  "continue": true
}
```

Or resume a specific session:
```json
{
  "prompt": "Add a dashboard with charts",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Custom System Instructions

```json
{
  "prompt": "Build a REST API for inventory management",
  "append_system_prompt": "Use TypeScript, Express.js, and PostgreSQL. Include comprehensive error handling and input validation. Follow REST best practices."
}
```

## Input Parameters

The agent accepts these parameters in the payload:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `prompt` | string | Yes | The task description for Claude Code |
| `session_id` | string | No | Session ID to resume a previous conversation |
| `continue` | boolean | No | Continue the most recent conversation |
| `allowed_tools` | string | No | Comma-separated list of allowed tools |
| `append_system_prompt` | string | No | Additional system instructions |
| `output_format` | string | No | Output format: json, text, stream-json (default: json) |
| `permission_mode` | string | No | Permission handling: acceptEdits, askUser (default: acceptEdits) |

## Output Format

The agent returns a JSON response:

```json
{
  "success": true,
  "result": "The task has been completed. The website is now live at: https://d123abc.cloudfront.net",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "metadata": {
    "cost_usd": 0.042,
    "duration_ms": 45000,
    "num_turns": 12
  },
  "error": null
}
```

## Allowed Tools

Claude Code can use various tools. Common ones include:

- `Bash` - Execute shell commands
- `Read` - Read file contents
- `Write` - Create/overwrite files
- `Replace` - Make targeted file edits
- `Search` - Search files with regex
- `List` - List directory contents
- `WebFetch` - Fetch web content
- `AskFollowup` - Ask clarifying questions

## Best Practices

1. **Clear Prompts**: Provide detailed, specific instructions
2. **Tool Selection**: Only enable tools needed for the task
3. **Error Handling**: Check the `success` field in responses
4. **Session Management**: Use session IDs for complex multi-step tasks
5. **Timeouts**: Adjust timeout for long-running tasks
6. **Cost Monitoring**: Track the `cost_usd` in metadata

## Troubleshooting

### Claude Code not found

If you get "command not found" errors:
1. Ensure Claude Code CLI is installed
2. Add it to your PATH
3. Or specify full path in the agent code

### Timeout Issues

For long-running tasks:
```bash
export CLAUDE_CODE_TIMEOUT=1800  # 30 minutes
```

### Permission Errors

Ensure the agent has necessary AWS permissions:
- S3: CreateBucket, PutObject, PutBucketPolicy
- CloudFront: CreateDistribution
- IAM: As needed for your use case

## Advanced Usage

### Streaming Output

For real-time progress updates:
```json
{
  "prompt": "Build and deploy a complex application",
  "output_format": "stream-json"
}
```

### Custom Tool Configuration

Restrict tools for security:
```json
{
  "prompt": "Analyze this codebase and suggest improvements",
  "allowed_tools": "Read,List,Search"
}
```

## Examples

See the [examples](examples/) directory for more use cases:
- `example_prompts.json` - Sample prompts for various tasks
- Testing scripts and validation tools

## Support

For issues specific to:
- **This integration**: Open an issue in this repository
- **AgentCore**: Consult AWS documentation
- **Claude Code**: Refer to Claude Code documentation
