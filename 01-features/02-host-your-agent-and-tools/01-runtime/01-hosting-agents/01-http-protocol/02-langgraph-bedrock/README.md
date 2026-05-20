# LangGraph with Amazon Bedrock on AgentCore runtime

## Overview

Deploy a [LangGraph](https://langchain-ai.github.io/langgraph/) agent using an Amazon Bedrock model (Claude) to AgentCore runtime. This example shows that AgentCore runtime is framework-agnostic — the deployment process is identical regardless of which agent framework you use. Only the agent code changes.

```
┌─────────────┐     invoke_agent_runtime()     ┌──────────────────────────┐
│   Client     │ ──────────────────────────────▶│  AgentCore runtime       │
│  (boto3)     │◀────────────────────────────── │  ┌──────────────────┐    │
│              │         JSON response          │  │  LangGraph Agent │    │
└─────────────┘                                 │  │  + Bedrock LLM   │    │
                                                │  └──────────────────┘    │
                                                └──────────────────────────┘
```

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) installed (for building the arm64 deployment package)
- AWS CLI configured with credentials
- Access to Amazon Bedrock models (Claude) in your region

## Step 1: Write the Agent (`agent.py`)

LangGraph uses an explicit **state graph** to define the agent loop — unlike Strands where the loop is automatic. You define nodes (functions), edges (routing), and state (typed dict):

```python
from langgraph.graph import END, StateGraph
from langchain_aws import ChatBedrock
from langchain_core.tools import tool

# Define a tool
@tool
def calculator(expression: str) -> str:
    """Evaluate a math expression."""
    return str(eval(expression))

# Define state — what flows through the graph
class AgentState(TypedDict):
    messages: Annotated[list, operator.add]

# Define nodes
def call_model(state):
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}

def call_tools(state):
    # Execute tool calls from the LLM response
    ...

# Build the graph
graph = StateGraph(AgentState)
graph.add_node("model", call_model)
graph.add_node("tools", call_tools)
graph.set_entry_point("model")
graph.add_conditional_edges("model", should_continue, {"tools": "tools", END: END})
graph.add_edge("tools", "model")
agent = graph.compile()
```

The `@app.entrypoint` wrapper is the same as any other framework:

```python
app = BedrockAgentCoreApp()

@app.entrypoint
def invoke_agent(payload: dict) -> str:
    result = agent.invoke({"messages": [HumanMessage(content=payload["prompt"])]})
    # Extract the final AI message
    for msg in reversed(result["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            return msg.content
    return "No response generated."
```

Test locally:

```bash
pip install -r requirements.txt
python agent.py
# In another terminal:
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is 25 * 17 + 42?"}'
```

## Step 2: Create an IAM Execution Role (`deploy.py`)

The IAM role uses the official [AgentCore direct deploy execution role](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html) policy. This includes permissions for CloudWatch Logs, X-Ray tracing, CloudWatch Metrics, and Bedrock model invocation. Without all of these, the runtime fails to initialize.

The deploy script creates this automatically — see `create_execution_role()` in `deploy.py`.

## Step 3: Build Deployment Package and Upload to S3 (`deploy.py`)

AgentCore runtime runs on **arm64 (Graviton)** microVMs. The deployment zip must include pre-compiled arm64 dependencies — the runtime does NOT run `pip install` at startup.

```bash
# What deploy.py does under the hood:
uv pip install \
  --python-platform aarch64-manylinux2014 \
  --python-version 3.13 \
  --target deployment_package \
  --only-binary :all: \
  -r requirements.txt

cd deployment_package && zip -r ../code.zip . && cd ..
zip code.zip agent.py
# Then uploads code.zip to S3
```

| Flag | Purpose |
|:-----|:--------|
| `--python-platform aarch64-manylinux2014` | Download wheels for ARM64 Linux (Graviton) |
| `--python-version 3.13` | Match the `PYTHON_3_13` runtime |
| `--only-binary :all:` | Only pre-built wheels (no source compilation) |
| `--target deployment_package` | Install into a local directory |

## Step 4: Create the AgentCore runtime (`deploy.py`)

```python
control.create_agent_runtime(
    agentRuntimeName="langgraph_bedrock_12345",
    agentRuntimeArtifact={
        "codeConfiguration": {
            "code": {"s3": {"bucket": bucket, "prefix": "agent/code.zip"}},
            "runtime": "PYTHON_3_13",
            "entryPoint": ["agent.py"],
        }
    },
    roleArn=role_arn,
    networkConfiguration={"networkMode": "PUBLIC"},
    protocolConfiguration={"serverProtocol": "HTTP"},
)
```

The runtime name must use **alphanumeric characters and underscores only** (no hyphens). The deploy script appends a timestamp for uniqueness.

## Step 5: Create an Endpoint (`deploy.py`)

```python
control.create_agent_runtime_endpoint(agentRuntimeId=runtime_id, name="default")
```

Poll `list_agent_runtime_endpoints` until the endpoint status is `READY`.

## Step 6: Invoke the Agent (`invoke.py`)

```python
client = boto3.client("bedrock-agentcore")
response = client.invoke_agent_runtime(
    agentRuntimeArn=runtime_arn,
    payload=json.dumps({"prompt": "What is 25 * 17 + 42?"}).encode(),
    contentType="application/json",
    accept="application/json",
)
body = response["response"].read().decode()
```

## Step 7: Clean Up (`cleanup.py`)

Delete in reverse order: endpoints → runtime → S3 artifact → IAM role.

## What's Different from the Strands Example

The **deployment and invocation code is identical**. Only the agent code and dependencies change:

| Aspect | Strands Example | This Example |
|:-------|:----------------|:-------------|
| Framework | `strands.Agent` | `langgraph.StateGraph` |
| Model | `strands.models.BedrockModel` | `langchain_aws.ChatBedrock` |
| Tool definition | `@tool` (Strands) | `@tool` (LangChain) |
| Agent loop | Automatic | Explicit graph with nodes and edges |
| Dependencies | `strands-agents` | `langgraph`, `langchain-aws`, `langchain-core` |

## Files

| File | Description |
|:-----|:------------|
| `agent.py` | LangGraph agent with a ReAct loop and calculator tool |
| `requirements.txt` | `langgraph`, `langchain-aws`, `langchain-core`, `bedrock-agentcore` |
| `deploy.py` | Full deployment: IAM role → arm64 zip → S3 → create runtime → create endpoint |
| `invoke.py` | Invoke the deployed agent with sample math prompts |
| `cleanup.py` | Delete endpoint → runtime → S3 → IAM role |

## Quick Start

```bash
python deploy.py         # Deploy to AgentCore runtime (~2-3 min)
python invoke.py         # Invoke with math questions
python cleanup.py        # Clean up all resources
```
