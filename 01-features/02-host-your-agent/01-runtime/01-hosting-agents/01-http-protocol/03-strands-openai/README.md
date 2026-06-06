# Strands Agents with Azure OpenAI on AgentCore runtime

## Overview

Deploy a [Strands Agents](https://strandsagents.com/) agent using **Azure OpenAI** (GPT-4.1-mini via [LiteLLM](https://docs.litellm.ai/)) to AgentCore runtime. This demonstrates that AgentCore runtime is model-agnostic — you can use any LLM provider, not just Amazon Bedrock.

```
┌─────────────┐     invoke_agent_runtime()     ┌──────────────────────────┐
│   Client     │ ──────────────────────────────▶│  AgentCore runtime       │
│  (boto3)     │◀────────────────────────────── │  ┌──────────────────┐    │
│              │         JSON response          │  │  Strands Agent   │    │
└─────────────┘                                 │  │  + Azure OpenAI  │    │
                                                │  │  (via LiteLLM)   │    │
                                                │  └──────────────────┘    │
                                                └──────────────────────────┘
```

## ⚠️ Before You Start: Update Your API Credentials

The `agent.py` file contains placeholder Azure OpenAI credentials that **you must replace** with your own before deploying:

```python
# In agent.py — replace these with your actual Azure OpenAI credentials:
os.environ["AZURE_API_KEY"] = "<YOUR_API_KEY>"
os.environ["AZURE_API_BASE"] = "<YOUR_API_BASE>"       # e.g., "https://your-resource.openai.azure.com/"
os.environ["AZURE_API_VERSION"] = "<YOUR_API_VERSION>"  # e.g., "2024-02-01"
```

Without valid credentials, the agent will deploy successfully but fail when invoked.

> **Production tip**: Instead of hardcoding credentials in the source file, pass them as `environmentVariables` in the `create_agent_runtime` call (see Step 3 below) and read them with `os.environ.get()` in the agent code.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) installed (for building the arm64 deployment package)
- AWS CLI configured with credentials
- Azure OpenAI API credentials (API key, base URL, API version)

## Step 1: Write the Agent (`agent.py`)

The key difference from the Bedrock examples is the model configuration. Instead of `BedrockModel`, we use `LiteLLMModel` which supports 100+ LLM providers:

```python
from strands.models.litellm import LiteLLMModel
import os

# Set Azure OpenAI credentials
os.environ["AZURE_API_KEY"] = "<YOUR_API_KEY>"
os.environ["AZURE_API_BASE"] = "<YOUR_API_BASE>"
os.environ["AZURE_API_VERSION"] = "<YOUR_API_VERSION>"

# Create the model via LiteLLM
model = LiteLLMModel(
    model_id="azure/gpt-4.1-mini",
    params={"max_tokens": 32000, "temperature": 0.7},
)

# Everything else is identical to the Bedrock example
agent = Agent(model=model, tools=[calculator, weather], ...)
```

The `@app.entrypoint` wrapper, tools, and `app.run()` are exactly the same as any other Strands agent.

Test locally (after updating credentials):

```bash
pip install -r requirements.txt
python agent.py
# In another terminal:
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is 25 * 17?"}'
```

## Step 2: Create an IAM Execution Role (`deploy.py`)

Since this agent calls Azure OpenAI (not Bedrock), the IAM role does **not** need `bedrock:InvokeModel` permissions. However, the runtime itself still needs CloudWatch Logs, X-Ray, and CloudWatch Metrics permissions to initialize correctly.

The deploy script creates the role automatically — see `create_execution_role()` in `deploy.py`.

## Step 3: Build Deployment Package and Upload to S3 (`deploy.py`)

Same arm64 packaging as the Bedrock examples — the zip must include pre-compiled `aarch64-manylinux2014` wheels. The deploy script handles this with `uv`.

> **Passing credentials via environment variables** (recommended for production):
> ```python
> control.create_agent_runtime(
>     # ... other params ...
>     environmentVariables={
>         "AZURE_API_KEY": "your-key",
>         "AZURE_API_BASE": "https://your-resource.openai.azure.com/",
>         "AZURE_API_VERSION": "2024-02-01",
>     },
> )
> ```
> Then in `agent.py`, read them with `os.environ.get("AZURE_API_KEY")` instead of hardcoding.

## Step 4: Create runtime and Endpoint (`deploy.py`)

Identical to the Bedrock examples — `create_agent_runtime` with `codeConfiguration`, then `create_agent_runtime_endpoint`.

## Step 5: Invoke the Agent (`invoke.py`)

```python
response = client.invoke_agent_runtime(
    agentRuntimeArn=runtime_arn,
    payload=json.dumps({"prompt": "What is 25 * 17?"}).encode(),
)
```

## Step 6: Clean Up (`cleanup.py`)

Delete in reverse order: endpoints → runtime → S3 artifact → IAM role.

## What's Different from the Bedrock Examples

| Aspect | Bedrock Example | This Example |
|:-------|:----------------|:-------------|
| Model | `strands.models.BedrockModel` | `strands.models.litellm.LiteLLMModel` |
| Model ID | `global.anthropic.claude-haiku-4-5-20251001-v1:0` | `azure/gpt-4.1-mini` |
| Credentials | IAM role (automatic) | Azure API key + base URL + version |
| IAM policy | Includes `bedrock:InvokeModel` | No Bedrock permissions needed |
| Dependencies | `strands-agents` | `strands-agents` + `litellm` |

Everything else — deployment flow, invocation, cleanup — is identical.

## Files

| File | Description |
|:-----|:------------|
| `agent.py` | Strands agent with LiteLLM + Azure OpenAI — **update credentials before deploying** |
| `requirements.txt` | `strands-agents`, `strands-agents-tools`, `litellm`, `bedrock-agentcore` |
| `deploy.py` | Full deployment: IAM role → arm64 zip → S3 → create runtime → create endpoint |
| `invoke.py` | Invoke the deployed agent |
| `cleanup.py` | Delete endpoint → runtime → S3 → IAM role |

## Quick Start

```bash
# 1. Update credentials in agent.py (replace <YOUR_API_KEY>, etc.)

# 2. Deploy
python deploy.py

# 3. Invoke
python invoke.py

# 4. Clean up
python cleanup.py
```
