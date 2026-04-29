# Hosting AI Agents on AgentCore Runtime

## Overview

This tutorial demonstrates how to host AI agents on **Amazon Bedrock AgentCore Runtime** using the Amazon Bedrock AgentCore Python SDK. Learn to transform your agent code into a standardized HTTP service that integrates seamlessly with Amazon Bedrock's infrastructure.

AgentCore Runtime is a **framework and model-agnostic** platform that can host agents built with any agentic framework (Strands Agents, LangGraph, CrewAI) and any LLM model (in Amazon Bedrock, OpenAI, etc.).

The Amazon Bedrock AgentCore Python SDK acts as a wrapper that:

- **Transforms** your agent code into AgentCore's standardized protocols
- **Handles** HTTP and MCP server infrastructure automatically
- **Lets you focus** on your agent's core functionality
- **Supports** two protocol types:
  - **HTTP Protocol**: Traditional request/response REST API endpoints
  - **MCP Protocol**: Model Context Protocol for tools and agent servers

---

## Architecture

When hosting agents, the SDK automatically:

- Hosts your agent on port `8080`
- Provides two key endpoints:
  - **`/invocations`**: Primary agent interaction (JSON input → JSON/SSE output)
  - **`/ping`**: Health check for monitoring

![Hosting agent](images/hosting_agent_python_sdk.png)

Once your agent is prepared for deployment on AgentCore Runtime, you deploy it using the Amazon Bedrock AgentCore SDK and boto3. The deployment uses **CodeZip** — your Python code is zipped, uploaded to S3, and the runtime is created via `create_agent_runtime`.

![RuntimeArchitecture](../images/runtime_architecture.png)

---

## What's This Feature

Amazon Bedrock AgentCore Runtime provides:

- **Serverless deployment** of Python agents — no container management required (CodeZip)
- **Session isolation** — each user session runs in an isolated microVM
- **Session lifecycle management** — stop sessions to release resources, configure idle timeouts
- **Framework agnostic** — works with Strands, LangGraph, CrewAI, or any Python framework
- **Model flexible** — supports Amazon Bedrock models, OpenAI, Azure OpenAI, and any LiteLLM provider

## Tutorial Examples

This tutorial includes four hands-on examples to get you started:

| Example                                                                | Framework      | Model          | Description                                |
| ---------------------------------------------------------------------- | -------------- | -------------- | ------------------------------------------ |
| **[01-strands-with-bedrock-model](01-strands-with-bedrock-model)**     | Strands Agents | Amazon Bedrock | Basic agent hosting with AWS native models |
| **[02-langgraph-with-bedrock-model](02-langgraph-with-bedrock-model)** | LangGraph      | Amazon Bedrock | LangGraph agent workflows                  |
| **[03-strands-with-openai-model](03-strands-with-openai-model)**       | Strands Agents | OpenAI         | Integration with external LLM providers    |
| **[06-strands-with-skills](06-strands-with-skills)**                   | Strands Agents | Amazon Bedrock | Skills-based agent hosting with AgentSkills plugin |

---

## CLI Commands

> **CLI version**: `agentcore@0.11.0`
>
> Install or update: `npm install -g @aws/agentcore@0.11.0`

The `agentcore` CLI provides a streamlined workflow for creating and deploying AgentCore Runtime projects.

### Full workflow example (Strands + Bedrock)

```bash
# 1. Create project
agentcore create \
  --name myagent \
  --framework Strands \
  --model-provider Bedrock \
  --build CodeZip \
  --skip-git --skip-install --json

# 2. Add your agent code
cp my_agent.py myagent/app/myagent/main.py

# 3. Deploy
cd myagent
agentcore deploy -y --json

# 4. Check status
agentcore status --json

# 5. Invoke
agentcore invoke "What is the weather in Athens?" --json

# 6. View logs
agentcore logs --since 30m -n 20
```

---

## Cleanup

**Using boto3** (recommended when deployed via notebook):

```python
import boto3
agentcore_control = boto3.client('bedrock-agentcore-control', region_name=region)
agentcore_control.delete_agent_runtime(agentRuntimeId=agent_runtime_id)

# Also clean up the S3 deployment artifact
s3 = boto3.client('s3', region_name=region)
s3.delete_object(Bucket=bucket_name, Key=s3_key)
```

**Using CLI** (when deployed via `agentcore deploy`):

```bash
agentcore remove agent --name myagent --json
agentcore deploy -y --json
```

---

## Key Benefits

- **Framework Agnostic**: Works with any Python-based agent framework
- **Model Flexible**: Support for LLMs in Amazon Bedrock, OpenAI, and other LLM providers
- **Production Ready**: Built-in health checks and monitoring
- **Easy Integration**: Minimal code changes required
- **Scalable**: Designed for enterprise workloads

## Getting Started

Choose one of the tutorial examples above based on your preferred framework and model combination. Each example includes:

- Step-by-step setup instructions
- Complete code samples
- Testing guidelines
- Best practices

## Next Steps

After completing the tutorials, you can:

- Extend these patterns to other frameworks and models
- Deploy to production environments
- Integrate with your existing applications
- Scale your agent infrastructure
