# Demo 1 Architecture Clarification

## The Confusion: Lambda References

In the planning documents, Lambda was mentioned as a **code reference**, not as an architectural component. Let me clarify what Demo 1 actually uses.

---

## Demo 1 Actual Architecture (NO LAMBDA)

```
┌─────────────────────────────────────────────────────────┐
│                    Your Laptop / EC2                    │
│  ┌──────────────────────────────────────────────────┐   │
│  │  simple_observability_demo.py                    │   │
│  │  - Python CLI script                             │   │
│  │  - Uses boto3 SDK                                │   │
│  │  - Makes API calls to AgentCore Runtime          │   │
│  └────────────────────┬─────────────────────────────┘   │
└────────────────────────┼───────────────────────────────┘
                         │
                         │ boto3.client('bedrock-agentcore-runtime')
                         │ .invoke_agent(agentId=..., inputText=...)
                         ▼
┌─────────────────────────────────────────────────────────┐
│          Amazon Bedrock AgentCore Runtime               │
│               (Fully Managed Service)                   │
│  ┌──────────────────────────────────────────────────┐   │
│  │         Your Strands Agent (Hosted)              │   │
│  │  - You deploy agent to Runtime once              │   │
│  │  - Runtime manages execution                     │   │
│  │  - Automatic OTEL instrumentation               │   │
│  │  - No servers to manage                          │   │
│  └────────────────────┬─────────────────────────────┘   │
└────────────────────────┼───────────────────────────────┘
                         │
                         │ Tool calls via MCP
                         ▼
┌─────────────────────────────────────────────────────────┐
│              AgentCore Gateway                          │
│               (Fully Managed Service)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │   Weather   │  │  World Time │  │ Calculator  │     │
│  │   MCP Tool  │  │   MCP Tool  │  │  MCP Tool   │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
              CloudWatch + Braintrust
           (OTEL traces exported automatically)
```

## Key Points

### What You Run Locally
```python
# simple_observability_demo.py
import boto3

def main():
    client = boto3.client('bedrock-agentcore-runtime')

    # Just call the API - that's it!
    response = client.invoke_agent(
        agentId='your-agent-id-123',  # Pre-deployed agent
        inputText='What is the weather in Seattle?',
        enableTrace=True
    )

    print(response['output'])
```

**That's the entire "Lambda" part - there is no Lambda!**

### What Runs in AWS (Managed Services)

1. **AgentCore Runtime**
   - You deploy your Strands agent definition once
   - Runtime executes it when you call `invoke_agent()`
   - Automatic OTEL spans generated
   - No infrastructure to manage

2. **AgentCore Gateway**
   - You configure MCP tools once
   - Gateway exposes them to your agent
   - Handles tool execution
   - No infrastructure to manage

### Where Lambda Was Referenced (And Why It's Confusing)

In the planning docs, I said:

> "Reusable from Lambda tutorial: error handling, logging, session tracking"

**What I meant:**
- The Lambda tutorial has GOOD CODE PATTERNS
- We can copy those patterns into our CLI script
- But we don't use Lambda itself

**What it sounded like:**
- Demo 1 uses Lambda (WRONG!)

## Correct Understanding

### Demo 1 Setup (One-Time)

**Step 1: Deploy Agent to AgentCore Runtime**
```bash
# Using AWS CLI or Console
aws bedrock-agentcore create-agent \
  --agent-name "weather-assistant" \
  --agent-framework "strands" \
  --agent-definition file://strands_agent_config.json

# Returns: agentId = "abc123"
```

**Step 2: Configure AgentCore Gateway with MCP Tools**
```bash
# Deploy Gateway with 3 tools
aws bedrock-agentcore-gateway create-gateway \
  --gateway-name "demo-tools" \
  --tools file://mcp_tools_config.json

# Returns: gatewayId = "xyz789"
```

**Step 3: Link Agent to Gateway**
```bash
aws bedrock-agentcore update-agent \
  --agent-id "abc123" \
  --gateway-id "xyz789"
```

**Done! Now you have a hosted agent that can use tools.**

### Demo 1 Execution (Every Time)

**Your Local Script:**
```python
# simple_observability_demo.py
import boto3
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


def invoke_agent(query: str) -> dict:
    """Invoke the pre-deployed agent."""
    client = boto3.client('bedrock-agentcore-runtime', region_name='us-east-1')

    logger.info(f"Invoking agent with query: {query}")

    response = client.invoke_agent(
        agentId='abc123',  # Your pre-deployed agent
        inputText=query,
        enableTrace=True  # Enable detailed tracing
    )

    logger.info("Agent response received")
    return response


def scenario_success():
    """Scenario 1: Successful query."""
    query = "What's the weather in Seattle and what time is it there?"
    result = invoke_agent(query)
    print(f"Result: {result['output']}")
    print("Now check CloudWatch X-Ray and Braintrust for traces!")


def scenario_error():
    """Scenario 2: Error handling."""
    query = "Calculate the factorial of -5"
    result = invoke_agent(query)
    print(f"Result: {result['output']}")
    print("Now check CloudWatch X-Ray and Braintrust for error traces!")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Demo AgentCore observability with dual platform support"
    )
    parser.add_argument('--agent-id', required=True, help='AgentCore Runtime agent ID')
    parser.add_argument('--scenario', choices=['success', 'error', 'all'], default='all')

    args = parser.parse_args()

    if args.scenario in ['success', 'all']:
        scenario_success()

    if args.scenario in ['error', 'all']:
        scenario_error()


if __name__ == "__main__":
    main()
```

**Run it:**
```bash
python simple_observability_demo.py --agent-id abc123
```

**That's it!**

## Where OTEL Configuration Happens

### Automatic (No Code)
- AgentCore Runtime automatically instruments your agent
- Generates spans for: agent invocation, tool selection, tool execution
- Exports to CloudWatch X-Ray by default

### Manual Configuration (For Braintrust)
You configure the Runtime to also export to Braintrust:

```bash
# When creating agent, specify OTEL exporters
aws bedrock-agentcore create-agent \
  --agent-name "weather-assistant" \
  --observability-config '{
    "otelExporters": [
      {
        "type": "cloudwatch",
        "region": "us-east-1"
      },
      {
        "type": "otlp",
        "endpoint": "https://api.braintrust.dev/otel",
        "headers": {
          "authorization": "Bearer ${BRAINTRUST_API_KEY}"
        }
      }
    ]
  }'
```

Or via YAML config:
```yaml
# config/otel_config.yaml
observability:
  otelExporters:
    - type: cloudwatch
      region: us-east-1

    - type: otlp
      endpoint: https://api.braintrust.dev/otel
      headers:
        authorization: Bearer ${BRAINTRUST_API_KEY}
```

## No Lambda Anywhere!

### What Demo 1 Does NOT Use:
- ❌ AWS Lambda
- ❌ Lambda functions
- ❌ Lambda layers
- ❌ Lambda invocation
- ❌ Any serverless function execution

### What Demo 1 DOES Use:
- ✅ AgentCore Runtime (managed agent hosting)
- ✅ AgentCore Gateway (managed MCP tool hosting)
- ✅ Simple Python CLI script (runs on your laptop/EC2)
- ✅ boto3 SDK to call AgentCore APIs
- ✅ CloudWatch X-Ray (automatic traces)
- ✅ Braintrust (optional additional export)

## Comparison: Lambda Tutorial vs Demo 1

### 05-Lambda-AgentCore-invocation Tutorial (Not Demo 1!)
```
AWS Lambda Function
├── lambda_agentcore_invoker.py (Lambda handler)
├── Triggered by API Gateway / EventBridge / etc.
├── Runs agent code inside Lambda
└── Useful for serverless workflows
```

**Use case:** Serverless agent execution

### Demo 1: Simple Observability (What We're Building)
```
Your Laptop / EC2
├── simple_observability_demo.py (CLI script)
├── Calls AgentCore Runtime API
├── Agent runs in managed Runtime (not Lambda)
└── Useful for demos and tutorials
```

**Use case:** Learning observability patterns

## Why the Confusion Happened

In the original planning docs, I referenced the Lambda tutorial for **code patterns**:

```python
# Good patterns from lambda_agentcore_invoker.py:

# 1. Error handling
try:
    response = client.invoke_agent(...)
except Exception as e:
    logger.exception(f"Agent invocation failed: {e}")
    raise

# 2. Logging with trace IDs
logger.info(
    "Agent invoked",
    extra={"trace_id": response.get("traceId")}
)

# 3. Session tracking
session_id = str(uuid.uuid4())
response = client.invoke_agent(
    agentId=agent_id,
    sessionId=session_id,
    inputText=query
)
```

**These patterns work in ANY Python code - Lambda or CLI script!**

I should have said: "Reuse error handling patterns from Lambda tutorial" instead of "Reuse Lambda handler structure."

## Updated Demo 1 Components (No Lambda)

### What We're Creating

```
07-simple-dual-observability-demo/
├── README.md
│   └── "How to deploy agent to Runtime and run this demo"
│
├── simple_observability_demo.py
│   └── CLI script that calls Runtime API (NOT Lambda!)
│
├── agent_definition/
│   └── strands_agent_config.json
│       └── Agent definition to deploy to Runtime
│
├── config/
│   └── otel_config.yaml
│       └── OTEL exporters (CloudWatch + Braintrust)
│
├── scripts/
│   ├── deploy_agent_to_runtime.sh
│   │   └── Deploy agent definition to AgentCore Runtime
│   ├── setup_gateway.sh
│   │   └── Configure Gateway with MCP tools
│   └── link_agent_to_gateway.sh
│       └── Connect agent to gateway
│
└── docs/
    └── DEMO_GUIDE.md
        └── "Step by step: setup, run, view traces"
```

### Deployment Flow

```bash
# One-time setup
cd 07-simple-dual-observability-demo

# 1. Deploy agent to AgentCore Runtime
./scripts/deploy_agent_to_runtime.sh
# Output: Agent ID: abc123

# 2. Setup Gateway with tools
./scripts/setup_gateway.sh
# Output: Gateway ID: xyz789

# 3. Link them together
./scripts/link_agent_to_gateway.sh --agent-id abc123 --gateway-id xyz789

# Demo execution (every time)
python simple_observability_demo.py --agent-id abc123

# View traces
# 1. Open CloudWatch X-Ray console
# 2. Open Braintrust dashboard
# 3. Search for same trace_id in both
```

## Bottom Line

**Demo 1 = Simple CLI script that calls AgentCore Runtime API**

- No Lambda
- No custom infrastructure
- Just managed services (Runtime + Gateway)
- Python script runs on your laptop
- Traces automatically go to CloudWatch
- Optionally configure Braintrust export

**Lambda was only mentioned for code pattern inspiration, not architecture!**

---

## Corrected GitHub Issue

I should update `demo1-github-issue.md` to clarify this. The issue currently says:

> "Reusable code from Lambda tutorial"

Should be:

> "Reusable code patterns from Lambda tutorial (error handling, logging, session tracking)"

And add a section:

> **Note:** This demo does NOT use AWS Lambda. The agent runs in AgentCore Runtime (managed service). The Lambda tutorial is referenced only for code patterns (error handling, logging) that work in any Python code.
