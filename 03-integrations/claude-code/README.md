# Claude Code Integration for Amazon Bedrock AgentCore

This integration enables you to run Claude Code as an autonomous coding agent on Amazon Bedrock AgentCore. Claude Code can programmatically handle complex coding tasks, create projects, and deploy infrastructure - all through natural language prompts.

## Overview

Claude Code is an AI-powered coding assistant that can:
- Generate complete applications from natural language descriptions
- Set up and configure cloud infrastructure 
- Deploy code to various platforms
- Handle multi-step development workflows autonomously

This integration provides two ways to use Claude Code with AgentCore:
1. **Headless Mode**: Run Claude Code programmatically without UI
2. **Python SDK**: Programmatic interface for Claude Code operations

## Directory Structure

```
claude-code/
├── headless-mode/       # Headless mode implementation
│   ├── examples/        # Example prompts and use cases
│   └── ...
└── python-sdk/          # Python SDK wrapper
    ├── examples/        # SDK usage examples
    └── ...
```

## Quick Start

### Headless Mode

The headless mode allows you to run Claude Code as an autonomous agent on AgentCore:

```bash
# Navigate to headless mode directory
cd headless-mode

# Install requirements
pip install -r requirements.txt

# Configure and deploy to AgentCore
agentcore configure -e claude_code_agent.py
agentcore launch
```

Once deployed, you can invoke the agent with prompts like:

```json
{
  "prompt": "Create a website that lists all running clubs in NYC with meeting times and locations. Deploy it to S3 and set up CloudFront distribution."
}
```

### Python SDK

The Python SDK provides a programmatic interface:

```python
from claude_code_sdk_wrapper import ClaudeCodeAgent

agent = ClaudeCodeAgent()
result = agent.execute("Build a REST API for task management with CRUD operations")
print(result)
```

## Features

- **Autonomous Code Generation**: Claude Code handles complete development workflows
- **Infrastructure as Code**: Automatically sets up cloud resources
- **Multi-turn Conversations**: Maintain context across multiple interactions
- **Tool Integration**: Supports various development tools and AWS services
- **Production Ready**: Scales automatically on AgentCore runtime

## Use Cases

1. **Rapid Prototyping**: Generate MVPs from descriptions
2. **Infrastructure Automation**: Set up cloud resources programmatically  
3. **Code Migration**: Transform codebases between frameworks
4. **Documentation Generation**: Create comprehensive docs from code
5. **Test Generation**: Automatically create test suites

## Requirements

- Python 3.10+
- AWS Account with Bedrock AgentCore access
- Claude Code CLI (installed via npm or binary)
- AWS CLI configured with appropriate permissions

## Documentation

- [Headless Mode Guide](headless-mode/README.md)
- [Python SDK Documentation](python-sdk/README.md)
- [Examples and Tutorials](examples/)

## Support

For issues and questions:
- Review the [AgentCore documentation](https://docs.aws.amazon.com/bedrock/agentcore)
- Check the [Claude Code documentation](https://docs.claude.ai/code)
- Open an issue in this repository
