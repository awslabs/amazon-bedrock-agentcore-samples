# Architecture Explanation: Simple Dual Observability Tutorial

## Two Modes of Operation

This tutorial demonstrates **two different deployment modes** for the same agent:

### Mode 1: Local Testing (Development)
### Mode 2: AgentCore Runtime Deployment (Production/Demo)

---

## Mode 1: Local Testing

**Use this for:** Development, debugging, understanding how the agent works

**Files involved:**
- `agent/weather_time_agent.py` - The actual Strands agent code
- `tools/*.py` - Tool implementations
- Test directly: `python -m agent.weather_time_agent "What's the weather in Seattle?"`

**Flow:**
```
Your Terminal
    ↓
agent/weather_time_agent.py
    ↓ (calls Claude API directly)
Anthropic Claude API
    ↓ (tool calls)
tools/weather_tool.py, tools/time_tool.py, tools/calculator_tool.py
    ↓
Response back to terminal
```

**Observability:** None (just local testing)

**Purpose:** Test your agent logic before deploying to production

---

## Mode 2: AgentCore Runtime Deployment (What the Tutorial Demonstrates)

**Use this for:** Production deployment, observability demo

**Files involved:**
- `simple_observability.py` - CLI script that invokes deployed agent
- `agent/strands_agent_config.json` - Agent configuration for deployment
- `scripts/deploy_agent.sh` - Deploys agent to AgentCore Runtime

**Flow:**
```
Your Laptop
    ↓ (runs simple_observability.py)
simple_observability.py (boto3 client)
    ↓ (API call: invoke_agent)
Amazon Bedrock AgentCore Runtime (Managed Service)
    ↓ (your agent code runs here with automatic OTEL)
agent/weather_time_agent.py (deployed and hosted by AWS)
    ↓ (tool calls routed through Gateway)
AgentCore Gateway (Managed Service)
    ↓ (MCP protocol)
tools/*.py (exposed as MCP tools)
    ↓ (traces exported automatically)
CloudWatch X-Ray + Braintrust
```

**Observability:** FULL - automatic OTEL tracing, CloudWatch metrics, Braintrust traces

**Purpose:** Production deployment with zero-code observability

---

## Key Difference: Where Does the Agent Run?

### Local Testing
- Agent code runs **on your machine**
- You call Anthropic API directly
- Tools execute **on your machine**
- No AWS services involved (except Bedrock for model)
- **No observability**

### AgentCore Runtime
- Agent code runs **in AWS (managed by AgentCore Runtime)**
- AgentCore Runtime calls Bedrock for you
- Tools execute **via AgentCore Gateway (MCP)**
- Fully managed AWS services
- **Automatic OTEL instrumentation** - this is the key!

---

## The Observability Magic

When you deploy to AgentCore Runtime, AWS automatically:

1. **Wraps your agent code** with OTEL instrumentation
2. **Creates spans** for:
   - Agent invocation
   - Model calls
   - Tool selection
   - Tool execution (via Gateway)
   - Response formatting

3. **Exports traces** to:
   - CloudWatch X-Ray (AWS-native)
   - Braintrust (via OTEL collector config)

4. **Logs everything** to CloudWatch Logs with correlation IDs

**You don't write any observability code - it's automatic!**

---

## File Structure Explained

```
07-simple-dual-observability/
│
├── agent/
│   ├── weather_time_agent.py          ← Actual agent code (Strands)
│   ├── strands_agent_config.json      ← Configuration for deployment
│   └── __init__.py
│
├── tools/
│   ├── weather_tool.py                ← Tool implementations
│   ├── time_tool.py
│   ├── calculator_tool.py
│   └── __init__.py
│
├── simple_observability.py            ← CLI to invoke DEPLOYED agent
│
├── scripts/
│   ├── deploy_agent.sh                ← Deploys agent to Runtime
│   ├── setup_cloudwatch.sh            ← Sets up CloudWatch dashboard
│   ├── setup_braintrust.sh            ← Sets up Braintrust connection
│   └── setup_all.sh                   ← One-click setup
│
├── config/
│   └── otel_config.yaml               ← OTEL collector config (dual export)
│
└── dashboards/
    ├── cloudwatch-dashboard.json      ← Pre-built CloudWatch dashboard
    └── braintrust-dashboard-export.json
```

---

## Deployment Workflow

### Step 1: Deploy Agent to AgentCore Runtime

```bash
cd scripts
./deploy_agent.sh
```

This:
1. Packages `agent/weather_time_agent.py`
2. Uploads to AgentCore Runtime
3. Configures tools via Gateway
4. Sets up OTEL dual export
5. Returns agent ID

### Step 2: Setup Observability

```bash
./setup_cloudwatch.sh
./setup_braintrust.sh
```

This:
1. Creates CloudWatch dashboard
2. Enables X-Ray tracing
3. Configures Braintrust connection
4. Tests OTEL export

### Step 3: Run Demo

```bash
cd ..
python simple_observability.py --agent-id <from-step-1> --scenario all
```

This:
1. Calls AgentCore Runtime API (boto3)
2. Runtime executes your agent code
3. Traces flow to CloudWatch + Braintrust
4. You view traces in both platforms

---

## Why Two Files? (weather_time_agent.py vs simple_observability.py)

**`agent/weather_time_agent.py`:**
- The agent code that **runs in AgentCore Runtime**
- Contains agent logic, tool calling, response formatting
- Gets deployed to AWS
- You can also run it locally for testing

**`simple_observability.py`:**
- The **client** that invokes the deployed agent
- Runs on your laptop
- Uses boto3 to call AgentCore Runtime API
- Manages demo scenarios
- Prints observability links

**Analogy:**
- `weather_time_agent.py` = Your Lambda function code
- `simple_observability.py` = The script that invokes your Lambda

---

## Common Confusion: Where is the Agent?

**Question:** "I run `simple_observability.py` but where is the agent code?"

**Answer:** The agent code (`weather_time_agent.py`) is **deployed to AgentCore Runtime** and runs there. `simple_observability.py` just **calls** it via API.

**Think of it like:**
- You deploy a web service to AWS
- You call it with `curl` or a client script
- The service code runs on AWS, not on your machine

Same here:
- You deploy agent code to AgentCore Runtime
- You call it with `simple_observability.py`
- The agent runs in Runtime, not on your machine

---

## Testing Locally vs Running Demo

### Local Testing (No Observability)

```bash
# Test agent code directly (no AWS, no observability)
python -m agent.weather_time_agent "What's the weather in Seattle?"
```

Uses:
- `agent/weather_time_agent.py` (runs locally)
- `tools/*.py` (runs locally)
- Anthropic API (for Claude model)

### Production Demo (Full Observability)

```bash
# Deploy agent first
cd scripts && ./deploy_agent.sh

# Then run demo
cd .. && python simple_observability.py --agent-id <id> --scenario all
```

Uses:
- `simple_observability.py` (runs locally, just API client)
- `agent/weather_time_agent.py` (runs in AgentCore Runtime)
- `tools/*.py` (exposed as MCP tools via Gateway)
- CloudWatch X-Ray + Braintrust (automatic traces)

---

## Summary

**You asked:** "Where is the Strands agent-based agent.py or similar?"

**Answer:** It's `agent/weather_time_agent.py`!

**But the tutorial demonstrates deploying it to AgentCore Runtime**, not running it locally. That's why you don't see it being imported directly in `simple_observability.py`.

**Two modes:**
1. **Local test:** Run `agent/weather_time_agent.py` directly
2. **Production demo:** Deploy `agent/weather_time_agent.py` to Runtime, then call it with `simple_observability.py`

The tutorial focuses on Mode 2 because that's where the automatic observability happens!
