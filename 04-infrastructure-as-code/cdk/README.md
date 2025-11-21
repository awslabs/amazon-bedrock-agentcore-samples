# CDK Samples

Deploy Amazon Bedrock AgentCore resources using AWS CDK (Python).

## Prerequisites

- Python 3.8+
- AWS CDK v2.218.0 or later (for BedrockAgentCore support)
- AWS CLI configured
- Access to Amazon Bedrock AgentCore (preview)

```bash
npm install -g aws-cdk
```

## General Deployment Pattern

```bash
cd <sample-directory>
pip install -r requirements.txt
cdk deploy
```

## Samples

- **[basic-runtime/](./basic-runtime/)** - Simple agent deployment
- **[multi-agent-runtime/](./multi-agent-runtime/)** - Multi-agent system  
- **[mcp-server-agentcore-runtime/](./mcp-server-agentcore-runtime/)** - MCP Server with JWT authentication
- **[end-to-end-weather-agent/](./end-to-end-weather-agent/)** - Weather agent with tools and memory

## CDK Advantages

- Uses `DockerImageAsset` for container building (no CodeBuild needed)
- Cleaner construct separation and reusability
- Type safety and IDE support
- Faster deployment times
