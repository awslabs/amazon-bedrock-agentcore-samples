# Hosting Strands Agents with Amazon Bedrock models in Amazon Bedrock AgentCore Runtime

## Overview

In this tutorial we will learn how to host your existing agent, using Amazon Bedrock AgentCore Runtime.

We will focus on a Strands Agents with Amazon Bedrock model example. For LangGraph with Amazon Bedrock model check [here](../02-langgraph-with-bedrock-model)
and for a Strands Agents with an OpenAI model check [here](../03-strands-with-openai-model).


### Tutorial Details

| Information         | Details                                                                          |
|:--------------------|:---------------------------------------------------------------------------------|
| Tutorial type       | Conversational                                                                   |
| Agent type          | Single                                                                           |
| Agentic Framework   | Strands Agents                                                                   |
| LLM model           | Anthropic Claude Haiku 4.5                                                        |
| Tutorial components | Hosting agent on AgentCore Runtime. Using Strands Agent and Amazon Bedrock Model |
| Tutorial vertical   | Cross-vertical                                                                   |
| Example complexity  | Easy                                                                             |
| SDK used            | Amazon BedrockAgentCore Python SDK and boto3                                     |

---

## Architecture

When hosting agents, the SDK automatically:

- Hosts your agent on port `8080`
- Provides two key endpoints:
  - **`/invocations`**: Primary agent interaction (JSON input → JSON/SSE output)
  - **`/ping`**: Health check for monitoring

<div style="text-align:left">
    <img src="images/architecture_runtime.png" width="100%"/>
</div>

Once deployed, your AgentCore Runtime receives requests from clients via `invoke_agent_runtime` (boto3 or AWS SDK). Each session runs in an isolated microVM. The lifecycle looks as following:

1. **Local experimentation** — run your agent as a Python script
2. **Wrap with SDK** — add `BedrockAgentCoreApp` decorator
3. **Deploy to Runtime** — package code, upload to S3, create runtime via boto3
4. **Invoke** — call via boto3 `invoke_agent_runtime`

---

## What's This Feature

Amazon Bedrock AgentCore Runtime lets you deploy any Python-based agent (Strands, LangGraph, CrewAI, etc.) as a scalable, serverless HTTP service. You wrap your agent's invocation function with the `@app.entrypoint` decorator from the `bedrock_agentcore` SDK — no other code changes required.

### Tutorial Key Features

* Hosting Agents on Amazon Bedrock AgentCore Runtime
* Using Amazon Bedrock models
* Using Strands Agents
* CodeZip deployment (no Docker required) via boto3 `create_agent_runtime`
* Session lifecycle management with `stop_runtime_session`
* Lifecycle configuration (idle session timeout) via `update_agent_runtime`

---

## CLI Commands

> **CLI version**: `agentcore@0.11.0`
>
> Install or update: `npm install -g @aws/agentcore@0.11.0`

The `agentcore` CLI provides an alternative end-to-end workflow for creating, deploying, invoking, and monitoring your runtime without writing deployment code.

### 1. Create a new project

```bash
agentcore create \
  --name stransclaude \
  --framework Strands \
  --model-provider Bedrock \
  --build CodeZip \
  --skip-git \
  --skip-install \
  --json
```

This scaffolds a project with `agentcore/agentcore.json` config, CDK stack, and a starter `main.py`.

### 2. Replace the generated agent code

Copy your agent code (`strands_claude.py`) into the project:

```bash
cp strands_claude.py app/stransclaude/main.py
cp requirements.txt app/stransclaude/requirements.txt
```

### 3. Deploy to AgentCore Runtime

```bash
cd stransclaude
agentcore deploy -y --json
```

This creates the IAM role, packages the code, and calls `create_agent_runtime`. Wait for `READY` status.

### 4. Check deployment status

```bash
agentcore status --json
```

### 5. Invoke the deployed agent

```bash
agentcore invoke "What is the weather in Athens?" --json
```

### 6. View logs

```bash
agentcore logs --since 30m -n 50
```

---

## Cleanup

To delete the runtime and associated resources:

**Using boto3** (from the notebook cleanup cell):

```python
import boto3
agentcore_control = boto3.client('bedrock-agentcore-control', region_name=region)
agentcore_control.delete_agent_runtime(agentRuntimeId=agent_runtime_id)
```

**Using CLI** (if deployed via `agentcore deploy`):

```bash
# Remove the agent from project config and redeploy to tear down
agentcore remove agent --name stransclaude --json
agentcore deploy -y --json
```

Also delete the S3 deployment artifact:

```python
s3 = boto3.client('s3', region_name=region)
s3.delete_object(Bucket=bucket_name, Key=s3_key)
```
