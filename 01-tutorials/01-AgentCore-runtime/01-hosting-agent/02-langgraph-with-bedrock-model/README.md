# Hosting LangGraph agent with Amazon Bedrock models in Amazon Bedrock AgentCore Runtime

## Overview

In this tutorial we will learn how to host your existing agent, using Amazon Bedrock AgentCore Runtime.

We will focus on a LangGraph with Amazon Bedrock model example. For Strands Agents with Amazon Bedrock model check [here](../01-strands-with-bedrock-model)
and for a Strands Agents with an OpenAI model check [here](../03-strands-with-openai-model).

### Tutorial Details

| Information         | Details                                                                      |
|:--------------------|:-----------------------------------------------------------------------------|
| Tutorial type       | Conversational                                                               |
| Agent type          | Single                                                                       |
| Agentic Framework   | LangGraph                                                                    |
| LLM model           | Anthropic Claude Haiku 4.5                                                    |
| Tutorial components | Hosting agent on AgentCore Runtime. Using LangGraph and Amazon Bedrock Model |
| Tutorial vertical   | Cross-vertical                                                               |
| Example complexity  | Easy                                                                         |
| SDK used            | Amazon BedrockAgentCore Python SDK and boto3                                 |

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

Once deployed, your AgentCore Runtime receives requests from clients via `invoke_agent_runtime`. Each session runs in an isolated microVM. The lifecycle:

1. **Local experimentation** — run your agent as a Python script
2. **Wrap with SDK** — add `BedrockAgentCoreApp` decorator
3. **Deploy to Runtime** — package code, upload to S3, create runtime via boto3
4. **Invoke** — call via boto3 `invoke_agent_runtime`

---

## What's This Feature

Amazon Bedrock AgentCore Runtime lets you deploy any Python-based agent (LangGraph, Strands, CrewAI, etc.) as a scalable, serverless HTTP service. You wrap your agent's invocation function with the `@app.entrypoint` decorator from the `bedrock_agentcore` SDK — no other code changes required.

### Tutorial Key Features

* Hosting Agents on Amazon Bedrock AgentCore Runtime
* Using Amazon Bedrock models
* Using LangGraph
* CodeZip deployment (no Docker required) via boto3 `create_agent_runtime`
* Session lifecycle management with `stop_runtime_session`
* Lifecycle configuration (idle session timeout) via `update_agent_runtime`

---

## CLI Commands

> **CLI version**: `agentcore@0.11.0`
>
> Install or update: `npm install -g @aws/agentcore@0.11.0`

### 1. Create a new project

```bash
agentcore create \
  --name langgraphclaude \
  --framework LangChain_LangGraph \
  --model-provider Bedrock \
  --build CodeZip \
  --skip-git \
  --skip-install \
  --json
```

### 2. Replace the generated agent code

```bash
cp langgraph_bedrock.py app/langgraphclaude/main.py
cp requirements.txt app/langgraphclaude/requirements.txt
```

### 3. Deploy to AgentCore Runtime

```bash
cd langgraphclaude
agentcore deploy -y --json
```

### 4. Check deployment status

```bash
agentcore status --json
```

### 5. Invoke the deployed agent

```bash
agentcore invoke "How much is 2+2?" --json
```

### 6. View logs

```bash
agentcore logs --since 30m -n 50
```

---

## Cleanup

**Using boto3** (from the notebook cleanup cell):

```python
import boto3
agentcore_control = boto3.client('bedrock-agentcore-control', region_name=region)
agentcore_control.delete_agent_runtime(agentRuntimeId=agent_runtime_id)
```

**Using CLI** (if deployed via `agentcore deploy`):

```bash
agentcore remove agent --name langgraphclaude --json
agentcore deploy -y --json
```

Also delete the S3 deployment artifact:

```python
s3 = boto3.client('s3', region_name=region)
s3.delete_object(Bucket=bucket_name, Key=s3_key)
```
