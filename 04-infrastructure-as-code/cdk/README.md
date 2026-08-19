# CDK Samples

Deploy Amazon Bedrock AgentCore resources using AWS CDK in Python or TypeScript.

## Choose Your Language

| Language | Description | Samples |
|----------|-------------|---------|
| **[Python](./python/)** | Familiar syntax for Python developers, quick prototyping | 4 samples |
| **[TypeScript](./typescript/)** | Strong typing, rich npm ecosystem, compile-time checks | 1 sample |

## Prerequisites

### Common
- AWS CLI configured
- AWS CDK CLI installed: `npm install -g aws-cdk`
- Access to Amazon Bedrock AgentCore

### Python Samples
- Python 3.8+
- AWS CDK v2.218.0+

### TypeScript Samples
- Node.js 18+ and npm
- AWS CDK v2.236.0+ (for BedrockAgentCore alpha support)
- Docker installed and running

## Samples Overview

### Python Samples

| Sample | Description |
|--------|-------------|
| [basic-runtime](./python/basic-runtime/) | Simple agent deployment |
| [multi-agent-runtime](./python/multi-agent-runtime/) | Multi-agent system with agent-to-agent communication |
| [mcp-server-agentcore-runtime](./python/mcp-server-agentcore-runtime/) | MCP Server with JWT authentication |
| [end-to-end-weather-agent](./python/end-to-end-weather-agent/) | Weather agent with tools and memory |

### TypeScript Samples

| Sample | Description |
|--------|-------------|
| [knowledge-base-rag-agent](./typescript/knowledge-base-rag-agent/) | Full-stack RAG agent with Knowledge Base, OpenSearch Serverless, web interface, and Cognito authentication |

## CDK Advantages Over CloudFormation

- **DockerImageAsset** - Automatic container building without CodeBuild
- **Construct reusability** - Share and compose infrastructure patterns
- **Type safety** - IDE support and compile-time error checking
- **Faster iterations** - Quicker deployment times
- **Programmatic logic** - Loops, conditionals, and abstractions
