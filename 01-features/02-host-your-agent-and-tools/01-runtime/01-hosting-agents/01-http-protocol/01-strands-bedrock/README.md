# Strands Agents with Amazon Bedrock on AgentCore runtime

## Overview

Deploy a [Strands Agents](https://strandsagents.com/) agent using an Amazon Bedrock model (Claude) to AgentCore runtime. This is the simplest path to hosting an agent — write your agent logic, zip it, and deploy with boto3.

![Architecture — agent in AgentCore runtime with Bedrock LLMs](images/architecture_runtime.png)

```
┌─────────────┐     invoke_agent_runtime()     ┌──────────────────────┐
│   Client     │ ──────────────────────────────▶│  AgentCore runtime   │
│  (boto3)     │◀────────────────────────────── │  ┌────────────────┐  │
│              │         JSON response          │  │  Strands Agent │  │
└─────────────┘                                 │  │  + Bedrock LLM │  │
                                                │  └────────────────┘  │
                                                └──────────────────────┘
```

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) installed (for building the arm64 deployment package)
- AWS CLI configured with credentials
- Access to Amazon Bedrock models (Claude) in your region

No Docker required — deployment uses direct code upload (zip to S3).

## Step 1: Write the Agent (`agent.py`)

The `bedrock-agentcore` SDK provides `BedrockAgentCoreApp`, which wraps your agent function into an HTTP service. The `@app.entrypoint` decorator tells the SDK which function handles incoming requests.

```python
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models.bedrock import BedrockModel

# Define tools — these are functions the LLM can call
@tool
def get_weather(city: str) -> dict:
    """Get current weather information for a city."""
    return {"city": city, "condition": "sunny", "temperature_f": 72}

# Configure the model
model = BedrockModel(model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0")

# Create the agent
agent = Agent(model=model, tools=[get_weather])

# Wrap with AgentCore SDK
app = BedrockAgentCoreApp()

@app.entrypoint
def invoke_agent(payload: dict) -> str:
    """This function is called for every POST /invocations request."""
    prompt = payload.get("prompt", "Hello!")
    response = agent(prompt)
    return response.message["content"][0]["text"]

if __name__ == "__main__":
    app.run()  # Starts HTTP server on port 8080
```

When `app.run()` starts, it creates two endpoints:
- `POST /invocations` — routes to your `@app.entrypoint` function
- `GET /ping` — returns 200 (health check)

You can test locally before deploying:

```bash
pip install -r requirements.txt
python agent.py
# In another terminal:
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is the weather in Seattle?"}'
```

## Step 2: Create an IAM Execution Role (`deploy.py`)

Every AgentCore runtime needs an IAM role that grants it permissions. The role needs:

- A **trust policy** allowing `bedrock-agentcore.amazonaws.com` to assume it
- An **inline policy** with the full set of permissions the runtime needs

> **Important**: The IAM policy needs more than just `bedrock:InvokeModel`. The runtime also requires CloudWatch Logs (specific log group path), X-Ray (distributed tracing), and CloudWatch Metrics permissions. Without these, the runtime fails to initialize even if your agent code is correct.

```python
import boto3, json

iam = boto3.client("iam")

# Trust policy — allows AgentCore to assume this role
trust_policy = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
        "Action": "sts:AssumeRole",
        "Condition": {
            "StringEquals": {"aws:SourceAccount": "123456789012"}
        },
    }],
}

iam.create_role(
    RoleName="agentcore-my-agent-role",
    AssumeRolePolicyDocument=json.dumps(trust_policy),
)

# Inline policy — the full AgentCore direct deploy execution role
iam.put_role_policy(
    RoleName="agentcore-my-agent-role",
    PolicyName="agent-policy",
    PolicyDocument=json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            # CloudWatch Logs — agent logging
            {"Effect": "Allow", "Action": ["logs:DescribeLogStreams", "logs:CreateLogGroup"],
             "Resource": ["arn:aws:logs:REGION:ACCOUNT:log-group:/aws/bedrock-agentcore/runtimes/*"]},
            {"Effect": "Allow", "Action": ["logs:DescribeLogGroups"],
             "Resource": ["arn:aws:logs:REGION:ACCOUNT:log-group:*"]},
            {"Effect": "Allow", "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
             "Resource": ["arn:aws:logs:REGION:ACCOUNT:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"]},
            # X-Ray — distributed tracing
            {"Effect": "Allow", "Action": ["xray:PutTraceSegments", "xray:PutTelemetryRecords",
             "xray:GetSamplingRules", "xray:GetSamplingTargets"], "Resource": ["*"]},
            # CloudWatch Metrics — runtime performance
            {"Effect": "Allow", "Action": "cloudwatch:PutMetricData", "Resource": "*",
             "Condition": {"StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}}},
            # Bedrock — model invocation
            {"Sid": "BedrockModelInvocation", "Effect": "Allow",
             "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
             "Resource": ["arn:aws:bedrock:*::foundation-model/*", "arn:aws:bedrock:REGION:ACCOUNT:*"]},
        ],
    }),
)
```

> **Note**: IAM role propagation takes ~10 seconds. The deploy script waits before proceeding.

## Step 3: Build Deployment Package and Upload to S3 (`deploy.py`)

AgentCore runtime uses **direct code deployment** — you zip your Python code and upload it to S3. However, the zip must include **pre-compiled arm64 dependencies**, not just a `requirements.txt`. The runtime does not run `pip install` at startup.

> **Why arm64?** AgentCore runtime runs on Graviton (arm64) microVMs. If the zip only contains source files, the runtime can't import the required packages and fails with: *"runtime initialization time exceeded. Please make sure that initialization completes in 30s."*

We use [uv](https://docs.astral.sh/uv/) to download arm64-compatible wheels:

```bash
# Download arm64 wheels into a staging directory
uv pip install \
  --python-platform aarch64-manylinux2014 \
  --python-version 3.13 \
  --target deployment_package \
  --only-binary :all: \
  -r requirements.txt

# Create zip with dependencies at the root
cd deployment_package && zip -r ../code.zip .

# Add your agent code at the root of the zip
cd .. && zip code.zip agent.py
```

The `deploy.py` script automates this entire process.

| Flag | Purpose |
|:-----|:--------|
| `--python-platform aarch64-manylinux2014` | Download wheels for ARM64 Linux (Graviton) |
| `--python-version 3.13` | Match the `PYTHON_3_13` runtime |
| `--only-binary :all:` | Only download pre-built wheels (no source compilation) |
| `--target deployment_package` | Install into a local directory, not site-packages |

## Step 4: Create the AgentCore runtime (`deploy.py`)

This is the core API call. `create_agent_runtime` on the **control plane** client (`bedrock-agentcore-control`) registers your agent with AgentCore.

```python
control = boto3.client("bedrock-agentcore-control")

response = control.create_agent_runtime(
    # Name for your runtime (alphanumeric + underscores only, must be unique)
    agentRuntimeName="strands_bedrock_agent",

    # Code deployment — points to your S3 zip
    agentRuntimeArtifact={
        "codeConfiguration": {
            "code": {
                "s3": {
                    "bucket": "agentcore-code-123456789012-us-east-1",
                    "prefix": "my-agent/code.zip",
                }
            },
            "runtime": "PYTHON_3_13",       # Python version (must match uv --python-version)
            "entryPoint": ["agent.py"],      # File to execute
        }
    },

    # IAM role created in Step 2
    roleArn="arn:aws:iam::123456789012:role/agentcore-my-agent-role",

    # Network — PUBLIC means accessible via AWS APIs
    networkConfiguration={"networkMode": "PUBLIC"},

    # Protocol — HTTP for standard request/response
    protocolConfiguration={"serverProtocol": "HTTP"},

    # Optional
    description="Strands agent with Bedrock model",
)

runtime_id = response["agentRuntimeId"]    # e.g., "abc123"
runtime_arn = response["agentRuntimeArn"]  # e.g., "arn:aws:bedrock-agentcore:us-east-1:123:runtime/abc123"
status = response["status"]                # "CREATING"
```

### `create_agent_runtime` Parameters

| Parameter | Required | Description |
|:----------|:---------|:------------|
| `agentRuntimeName` | Yes | Unique name for the runtime |
| `agentRuntimeArtifact` | Yes | Either `codeConfiguration` (zip to S3) or `containerConfiguration` (ECR image) |
| `roleArn` | Yes | IAM execution role ARN |
| `networkConfiguration` | Yes | `PUBLIC` or `VPC` (with subnets/security groups) |
| `protocolConfiguration` | No | `HTTP` (default), `MCP`, `A2A`, or `AGUI` |
| `description` | No | Human-readable description |
| `environmentVariables` | No | Key-value pairs passed to the runtime environment |
| `lifecycleConfiguration` | No | `idleRuntimeSessionTimeout` (default 900s) and `maxLifetime` (default 28800s) |
| `authorizerConfiguration` | No | JWT authorizer for inbound auth (Cognito, Okta, etc.) |
| `filesystemConfigurations` | No | Persistent storage mounted at `/mnt/...` |

### `codeConfiguration` Fields

| Field | Description |
|:------|:------------|
| `code.s3.bucket` | S3 bucket containing your zip |
| `code.s3.prefix` | S3 key for the zip file |
| `runtime` | `PYTHON_3_10`, `PYTHON_3_11`, `PYTHON_3_12`, `PYTHON_3_13`, `PYTHON_3_14`, or `NODE_22` |
| `entryPoint` | List with the file to execute (e.g., `["agent.py"]`) |

The runtime starts in `CREATING` status. Poll with `get_agent_runtime` until it reaches `READY`:

```python
import time

while True:
    resp = control.get_agent_runtime(agentRuntimeId=runtime_id)
    status = resp["status"]  # CREATING → READY (or CREATE_FAILED)
    if status == "READY":
        break
    if status == "CREATE_FAILED":
        raise RuntimeError(resp.get("failureReason", "Unknown error"))
    time.sleep(15)
```

## Step 5: Create an Endpoint (`deploy.py`)

A runtime needs at least one **endpoint** before it can receive traffic. The endpoint is what clients invoke.

```python
control.create_agent_runtime_endpoint(
    agentRuntimeId=runtime_id,
    name="default",
)
```

Wait for the endpoint to reach `READY` the same way you waited for the runtime.

## Step 6: Invoke the Agent (`invoke.py`)

Now use the **data plane** client (`bedrock-agentcore`) to send requests:

```python
import json, boto3

client = boto3.client("bedrock-agentcore")

response = client.invoke_agent_runtime(
    # The runtime ARN from Step 4
    agentRuntimeArn="arn:aws:bedrock-agentcore:us-east-1:123:runtime/abc123",

    # Your request payload — passed to the @app.entrypoint function
    payload=json.dumps({"prompt": "What is the weather in Seattle?"}).encode("utf-8"),

    # Content negotiation
    contentType="application/json",
    accept="application/json",       # or "text/event-stream" for SSE streaming

    # Optional: reuse a session for multi-turn conversations
    # runtimeSessionId="my-session-123",
)

# Read the response
body = response["response"].read().decode("utf-8")
session_id = response["runtimeSessionId"]  # auto-generated if not provided
print(body)
```

### `invoke_agent_runtime` Parameters

| Parameter | Required | Description |
|:----------|:---------|:------------|
| `agentRuntimeArn` | Yes | ARN of the runtime to invoke |
| `payload` | Yes | Bytes — your request data (passed to `@app.entrypoint`) |
| `contentType` | No | MIME type of the payload (default: `application/json`) |
| `accept` | No | Desired response format — `application/json` or `text/event-stream` |
| `runtimeSessionId` | No | Session ID for multi-turn conversations (auto-generated if omitted) |
| `qualifier` | No | Endpoint name (default: `DEFAULT`) |

## Step 7: Clean Up (`cleanup.py`)

Delete resources in reverse order: endpoints → runtime → S3 artifact → IAM role.

```python
# 1. Delete endpoints
control.delete_agent_runtime_endpoint(agentRuntimeId=runtime_id, endpointName="default")

# 2. Delete runtime
control.delete_agent_runtime(agentRuntimeId=runtime_id)

# 3. Delete S3 code
s3.delete_object(Bucket=bucket, Key="my-agent/code.zip")

# 4. Delete IAM role (remove policies first)
iam.delete_role_policy(RoleName=role_name, PolicyName="agent-policy")
iam.delete_role(RoleName=role_name)
```

## Files

| File | Description |
|:-----|:------------|
| `agent.py` | Strands agent with `get_weather` and `get_time` tools |
| `requirements.txt` | Python dependencies |
| `deploy.py` | Full deployment script (Steps 2–5 above) |
| `invoke.py` | Invokes the deployed agent (Step 6) |
| `cleanup.py` | Deletes all resources (Step 7) |

## Quick Start

```bash
pip install -r requirements.txt

# Test locally
python agent.py

# Deploy to AgentCore runtime
python deploy.py

# Invoke the deployed agent
python invoke.py

# Clean up
python cleanup.py
```
