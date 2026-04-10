# RegistryToolProvider — Dynamic Tool Discovery for Strands Agents

A Strands `ToolProvider` that discovers tools from AWS Agent Registry via semantic search. Instead of hardcoding tools at startup, the agent gets only the tools relevant to the current domain.

```
User: "Check my Salesforce pipeline"

Agent (before LLM turn):
  → provider.load_tools()
  → SearchRegistryRecords(query="Salesforce CRM")
  → Registry returns: salesforce_agentforce record (1 tool)
  → LLM sees 1 tool, not 200
```

## Quick Start

```python
from strands import Agent
from registry_tool_provider import RegistryToolProvider

provider = RegistryToolProvider(
    registry_ids=["<your-registry-id>"],
    domains=["order management", "CRM"],
    gateway_url="https://gw-xxx.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp",
    gateway_token_fn=lambda: get_my_token(),
)

agent = Agent(tool_providers=[provider])
agent("Check my open orders and update the CRM")
```

## How It Works

1. Agent calls `load_tools()` before each LLM turn
2. Provider searches Registry with each domain keyword (semantic search)
3. Matching records are parsed based on protocol:
   - **MCP** → extracts tools from `tools`, routes `tools/call` through Gateway
   - **A2A** → creates an `invoke_<agent>` tool, routes through AgentCore Runtime
   - **Custom** → creates a passthrough tool from record metadata
4. Only tools from `APPROVED` records are returned (configurable)
5. Results are cached for `cache_ttl` seconds (default 300)

## Parameters

| Parameter | Default | Description |
|---|---|---|
| `registry_ids` | required | Registry identifiers to search across |
| `domains` | required | Semantic search keywords (e.g., `["CRM", "inventory"]`) |
| `gateway_url` | `None` | Gateway URL for MCP tool invocation (must be HTTPS) |
| `gateway_token_fn` | `None` | Callable returning a Bearer token for the Gateway |
| `region` | `us-west-2` | AWS region for Registry and Runtime API calls |
| `endpoint_url` | `None` | Custom Registry endpoint (must be HTTPS) |
| `max_results` | `10` | Max records per search query |
| `cache_ttl` | `300` | Seconds to cache results. `0` disables caching |
| `required_status` | `APPROVED` | Only load records with this status. `None` disables filtering |
| `allowed_runtime_arns` | `None` | Allowlist of Runtime ARNs for A2A. `None` allows all |
| `fail_open` | `True` | If `True`, search failures return empty. If `False`, raise |

## Supported Protocols

| Protocol | Record contains | Provider creates | Invocation path |
|---|---|---|---|
| MCP | `tools` with tool definitions | One `PythonAgentTool` per tool | Gateway `tools/call` |
| A2A | `agentCard` with skills and endpoint | Single `invoke_<agent>` tool | Runtime `invoke_agent_runtime` |
| Custom | Free-form metadata | Passthrough tool | Returns record metadata |

For A2A records, the runtime ARN or endpoint URL is extracted from the `agentCard.inlineContent` JSON (`url` or `runtimeArn` field). If not found there, falls back to the top-level record field.

## Security

| Concern | Mitigation |
|---|---|
| Tool name injection | Validated against `^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$` |
| Prompt injection via descriptions | Truncated to 256 chars, control characters stripped |
| Arbitrary Runtime ARN invocation | `allowed_runtime_arns` allowlist |
| Token leakage in exceptions | Gateway/Runtime calls wrapped, only exception type exposed |
| Cleartext credentials | `gateway_url` and `endpoint_url` must be HTTPS |
| Oversized payloads | JSON payloads rejected above 1MB before parsing |
| Unapproved records | Only `APPROVED` records loaded by default |
| Cache poisoning | Set `cache_ttl=0` for high-security environments |

## Developer Journey

### Step 1: Install dependencies

```bash
pip install "boto3>=1.42.87" strands-agents httpx
```

### Step 2: Get your Registry ID

```bash
aws bedrock-agentcore-control list-registries --region us-west-2
```

### Step 3: Pick your domain keywords

Think about what your agent does. If it handles customer support, your domains might be `["CRM", "ticketing", "knowledge base"]`. These are the semantic search queries that find relevant tools in the Registry.

### Step 4: Set up auth for the Gateway

Your agent needs a token to call tools through the Gateway:

```python
import boto3, json, httpx

def get_gateway_token():
    sm = boto3.client("secretsmanager", region_name="us-east-1")
    creds = json.loads(sm.get_secret_value(SecretId="my-gateway-mcp-cognito-credentials")["SecretString"])
    resp = httpx.post(f"https://{creds['domain']}/oauth2/token", data={
        "grant_type": "client_credentials",
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "scope": creds["scope"],
    }, headers={"Content-Type": "application/x-www-form-urlencoded"})
    return resp.json()["access_token"]
```

### Step 5: Create the provider and agent

```python
from strands import Agent
from strands.models import BedrockModel
from registry_tool_provider import RegistryToolProvider

provider = RegistryToolProvider(
    registry_ids=["Vf4gtZ5mreKG"],
    domains=["CRM", "ticketing", "knowledge base"],
    gateway_url="https://my-gw.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp",
    gateway_token_fn=get_gateway_token,
    region="us-west-2",
)

agent = Agent(
    model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514"),
    tool_providers=[provider],
)
```

### Step 6: Run it

```python
result = agent("What are my open support tickets?")
```

What happens under the hood:

```
agent("What are my open support tickets?")
  │
  ├─ provider.load_tools()
  │    ├─ SearchRegistryRecords(query="CRM")            → salesforce record (1 tool)
  │    ├─ SearchRegistryRecords(query="ticketing")       → ticketing record (3 tools)
  │    └─ SearchRegistryRecords(query="knowledge base")  → kb record (5 tools)
  │    → 9 tools injected into LLM context (not 200)
  │
  ├─ LLM picks: ask_agentforce, query_tickets
  │
  ├─ provider calls Gateway: tools/call → ask_agentforce
  │    └─ Gateway → Salesforce MCP → response
  │
  ├─ provider calls Gateway: tools/call → query_tickets
  │    └─ Gateway → Ticketing MCP → response
  │
  └─ LLM synthesizes answer from both tool results
```

### Step 7 (optional): Lock down for production

```python
provider = RegistryToolProvider(
    registry_ids=["Vf4gtZ5mreKG"],
    domains=["CRM"],
    gateway_url="https://...",
    gateway_token_fn=get_gateway_token,
    required_status="APPROVED",          # default — only approved records
    allowed_runtime_arns=[               # restrict which A2A agents can be invoked
        "arn:aws:bedrock-agentcore:us-east-1:123:runtime/my-agent"
    ],
    fail_open=False,                     # raise on search failure instead of silent empty
    cache_ttl=60,                        # shorter cache for faster record revocation
)
```

## Example Use Case: Enterprise Customer Support Agent

An org has 50+ tools registered in the Registry across teams:
- Sales registered Salesforce Agentforce (MCP)
- IT registered ServiceNow ticketing (MCP)
- Knowledge team registered 8 knowledge bases (MCP via Gateway)
- Data team registered Databricks SQL (MCP via Gateway)
- Finance registered SAP invoice lookup (MCP via Gateway)
- Platform team registered an escalation agent (A2A on Runtime)

Without RegistryToolProvider, the developer hardcodes all 50 tools — LLM context explodes, slow, expensive, breaks every time a team adds or removes a tool.

With RegistryToolProvider:

```python
provider = RegistryToolProvider(
    registry_ids=["org-registry"],
    domains=["customer support", "ticketing", "account lookup", "knowledge base"],
    gateway_url="https://org-gateway.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp",
    gateway_token_fn=get_token,
)
agent = Agent(tool_providers=[provider])
```

**Request 1:** *"What's the status of ticket INC-4821?"*
→ Provider finds ServiceNow + KB tools (6 tools). LLM picks `query_servicenow_tickets`. Returns ticket status.

**Request 2:** *"Pull last quarter's invoices for Syngenta"*
→ Provider finds SAP + Salesforce tools (4 tools). LLM picks `sap_invoice_lookup` + `get_account_details`. Returns invoices with account context.

**Request 3:** *"This needs to go to a human, customer is upset"*
→ Provider finds escalation agent (A2A). LLM calls `invoke_escalation_agent` with context. Agent on Runtime creates a priority ticket and notifies the team.

Same agent, same code, different tools per request. When the data team adds a new Databricks dashboard tool to the Registry next week, the agent picks it up automatically — no code change, no redeploy.

## Prerequisites

### 1. Python dependencies

```bash
pip install "boto3>=1.42.87" strands-agents httpx
```

> With boto3 >= 1.42.87, the Agent Registry APIs are included natively — no custom endpoints or bundled wheels needed.

### 2. IAM Policy

Attach the following policy to the IAM user or role running the agent. Replace `ACCOUNT_ID` and `REGION` with your values.

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "RegistrySearch",
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:SearchRegistryRecords",
                "bedrock-agentcore:GetRegistryRecord"
            ],
            "Resource": "arn:aws:bedrock-agentcore:REGION:ACCOUNT_ID:registry/*"
        },
        {
            "Sid": "InvokeA2AAgents",
            "Effect": "Allow",
            "Action": "bedrock-agentcore:InvokeAgentRuntime",
            "Resource": "arn:aws:bedrock-agentcore:REGION:ACCOUNT_ID:runtime/*"
        }
    ]
}
```

- `SearchRegistryRecords` — required for semantic search (data plane)
- `GetRegistryRecord` — required to fetch full record details including descriptors
- `InvokeAgentRuntime` — only needed if your registry contains A2A agent records. Omit if you only use MCP tools.

### 3. A Gateway URL and token function (for MCP tools)

MCP tools are invoked through an AgentCore Gateway. You need the gateway URL and a function that returns a Bearer token.

## Files

| File | Description |
|---|---|
| `registry_tool_provider.py` | The `RegistryToolProvider` class |
| `example_tool_provider_agent.py` | Minimal agent using the provider |

## Example Output

```
$ python example_tool_provider_agent.py

INFO:registry_tool_provider:RegistryToolProvider: loaded 6 tools from 3 domain(s)

Discovered 6 tools:
  - ask_agentforce: Send a message to Salesforce Agentforce
  - query_AgentCore_knowledge_base: Query the AgentCore knowledge base
  - query_Sandoz_knowledge_base: Query the Sandoz knowledge base
  - query_daily_notes_kb_knowledge_base: Daily notes knowledge base
  - query_dormakaba_sales_kb_knowledge_base: Dormakaba sales documentation
  - x_amz_bedrock_agentcore_search: Returns a trimmed down list of tools
```

## When to Use This vs Other Patterns

This is the **recommended default** for production Strands agents. See [DISCOVERY_PATTERNS.md](DISCOVERY_PATTERNS.md) for a comparison of all 5 discovery patterns.

| Pattern | When to use |
|---|---|
| **Programmatic Pre-fetch** | Small fixed toolsets (<15 tools) |
| **Registry-as-Tool** | Exploratory agents, unknown domains |
| **ToolProvider (this)** | Production default — bounded context, automatic |
| **Hook Interception** | Fallback/recovery, legacy migration |
| **Planner+Executor** | Multi-step workflows, cost-sensitive |
