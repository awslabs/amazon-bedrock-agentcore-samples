# Multi-Tenant Tool Isolation with Cedar Policies on AgentCore Gateway

Demonstrate how a single AI agent serves multiple tenants with per-tenant tool
visibility enforced by Cedar policies on an AgentCore MCP Gateway. Each tenant's
JWT scope determines which tools are visible and callable. The agent code has
zero tenant-specific logic.

## Architecture

```
                     +--------------------------------------------+
                     |     AgentCore MCP Gateway                  |
                     |                                            |
+--------------+     |  +-------------------------------------+   |
| HealthCo     | JWT |  | Cedar Policy Engine (ENFORCE)       |   |
| scope:       |---->|  |                                     |   |
| platform/    |     |  | scope like "*platform/insurance*"   |   |
| insurance    |     |  |   -> 6 tools visible                |   |
+--------------+     |  |                                     |   |
                     |  | scope like "*platform/banking*"     |   |
+--------------+     |  |   -> 3 tools visible                |   |
| FinBank      | JWT |  |                                     |   |
| scope:       |---->|  +-------------------------------------+   |
| platform/    |     |                   |                        |
| banking      |     +------------------+-------------------------+
+--------------+                         |
                                         | permitted only
                                         v
      +-----------------+  +-----------------+  +-----------------+
      | submit_decision |  | query_claims    |  | flag_suspicious |
      | notify_team     |  | query_accounts  |  | query_accounts  |
      | (insurance)     |  | query_members   |  | query_txns      |
      +-----------------+  | (shared)        |  | (banking)       |
                           +-----------------+  +-----------------+
```

**Key insight**: In ENFORCE mode, tools without a matching `permit` policy are
removed from the `tools/list` response entirely. The LLM never learns they exist,
so prompt injection cannot trick the agent into calling cross-tenant tools.

## Prerequisites

- Python 3.12+
- AWS CLI configured with credentials
- Amazon Bedrock model access (Claude Sonnet or Nova Lite) in your region
- AgentCore access enabled in your account

## Quick Start

```bash
pip install -r requirements.txt

# Deploy: Cognito (2 M2M clients), Gateway, Lambda tools, Cedar policies
python deploy.py

# Test: show each tenant sees different tools
python demo.py

# Clean up all AWS resources
python cleanup.py
```

## How It Works

### Step 1: Two Cognito M2M Clients with Different Scopes

Each tenant gets its own Cognito app client with a distinct OAuth scope:

- `healthco-client` → custom scope `platform/insurance`
- `finbank-client` → custom scope `platform/banking`

The JWT `scope` claim auto-maps to a Cedar principal tag. No custom Lambda
trigger needed for scope-based policies.

### Step 2: Cedar Policies Match on Scope

```cedar
// policies/insurance_permit.cedar
permit(
  principal,
  action in [
    AgentCore::Action::"submit-decision___submit_decision",
    AgentCore::Action::"notify-team___notify_team",
    AgentCore::Action::"query-tools___query_claims",
    AgentCore::Action::"query-tools___query_members",
    AgentCore::Action::"query-tools___query_providers",
    AgentCore::Action::"query-tools___query_benefits"
  ],
  resource
)
when {
  principal.hasTag("scope") &&
  principal.getTag("scope") like "*platform/insurance*"
};
```

```cedar
// policies/banking_permit.cedar
permit(
  principal,
  action in [
    AgentCore::Action::"flag-suspicious___flag_suspicious",
    AgentCore::Action::"query-tools___query_accounts",
    AgentCore::Action::"query-tools___query_transactions"
  ],
  resource
)
when {
  principal.hasTag("scope") &&
  principal.getTag("scope") like "*platform/banking*"
};
```

### Step 3: Agent Forwards JWT (One Line of Tenancy Logic)

The agent connects to the Gateway via MCP and passes the tenant's Bearer token.
Gateway + Cedar handle the rest. No `if tenant == X` in agent code.

```python
mcp_client = MCPClient(
    lambda: streamablehttp_client(
        gateway_url,
        headers={"Authorization": f"Bearer {tenant_token}"},
    )
)
tools = mcp_client.list_tools_sync()  # only permitted tools appear
agent = Agent(model="us.anthropic.claude-sonnet-4-20250514", tools=tools)
```

## Differences from the Single-Tenant ABAC Sample

| Aspect | `02-policy/` (parent) | This sample |
|--------|----------------------|-------------|
| Tenancy | Single tenant, ABAC on claims | Multi-tenant, scope-based isolation |
| Clients | 1 Cognito client | 2 Cognito clients (one per tenant) |
| Policies | Department/group/identity checks | Scope-wildcard matching per tenant |
| Demo | NL2Cedar + fine-grained ABAC | Tenant A vs. Tenant B tool visibility |
| Use case | Per-user access control | Per-tenant tool isolation for SaaS |

## Files

| File | Description |
|:-----|:------------|
| `deploy.py` | Deploys Cognito, Gateway, Lambdas, Cedar policies |
| `demo.py` | Shows each tenant's tool list and tests cross-tenant denial |
| `cleanup.py` | Deletes all resources |
| `policies/insurance_permit.cedar` | Cedar policy for insurance tenant |
| `policies/banking_permit.cedar` | Cedar policy for banking tenant |
| `utils/agent_with_gateway.py` | Minimal Strands agent with MCP gateway |
| `utils/lambda_tools/handler.py` | Mock Lambda tools (all tenants) |
| `requirements.txt` | Python dependencies |

## Additional Resources

- [Cedar Policy Language](https://docs.cedarpolicy.com/)
- [AgentCore Policy Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html)
- [AgentCore Gateway Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html)
