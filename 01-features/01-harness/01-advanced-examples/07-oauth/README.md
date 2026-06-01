# OAuth + JWT Auth (Inbound + Outbound)

| Information         | Details                                                                  |
|:--------------------|:-------------------------------------------------------------------------|
| Tutorial type       | Advanced Example                                                         |
| Agent type          | Order management assistant                                               |
| Agentic Framework   | None (direct boto3 + requests)                                           |
| LLM model           | Anthropic Claude Haiku 4.5                                               |
| Tutorial components | AgentCore harness — CUSTOM_JWT inbound auth, OAuth2 outbound auth        |
| Example complexity  | Advanced                                                                 |

## Overview

Production agents need both inbound authentication (who can call your agent) and outbound
authentication (how the agent calls tools). This tutorial provisions two Cognito pools,
an AgentCore gateway, and a Lambda function, then demonstrates the full auth chain:
caller presents JWT → harness validates it → agent calls gateway with M2M token.

## Architecture

![Architecture](images/architecture.jpg)

```
User
  │
  │ Bearer token (User Auth Pool JWT)
  ▼
Harness  ──── CUSTOM_JWT inbound auth ────► Cognito User Pool
  │                                         validates JWT
  │
  │ agent decides to call a tool
  ▼
Harness  ──── outboundAuth.oauth ──────────► Cognito M2M Pool
  │                                          client_credentials grant
  │ M2M token
  ▼
Gateway  ──── CUSTOM_JWT + allowed scopes ─► validates M2M token
  │
  ▼
Lambda function (order management tools)
  │
  ▼
Response flows back to user
```

Three auth mechanisms, zero secrets in the invoke call. The harness handles all token
exchange automatically from the `outboundAuth.oauth` configuration.

## Infrastructure Setup

The script provisions resources via helper functions in `utils/setup_helpers.py`. All helpers
are idempotent — safe to re-run:

| Helper | What it creates |
|:-------|:----------------|
| `create_user_auth_pool` | Cognito User Auth Pool — user pool, app client (`USER_PASSWORD_AUTH`), test user |
| `create_m2m_pool` | Cognito M2M Pool — user pool, resource server + scope, domain, app client (`client_credentials`) |
| `create_credential_provider` | OAuth2 credential provider in AgentCore identity pointing to M2M Pool |
| `deploy_lambda` | IAM role + Lambda function from `utils/lambda_function_code.py` |
| `create_gateway_with_lambda_target` | gateway (`CUSTOM_JWT` → M2M Pool) + Lambda target (`GATEWAY_IAM_ROLE`) |
| `create_harness_execution_role` | IAM role with Bedrock, gateway, Token Vault, CloudWatch, X-Ray permissions |

## Sample Prompts

**Prompt**: "Look up order ORD-001 and tell me its status."
**Expected Behavior**: Agent calls `get_order` tool via gateway with M2M token, returns order details.

**Prompt**: "Update order ORD-002 status to 'shipped'."
**Expected Behavior**: Agent calls `update_order_status` tool, confirms the update.

**Prompt**: "Check all three orders (ORD-001, ORD-002, ORD-003) and summarize their statuses."
**Expected Behavior**: Agent makes three tool calls, provides a summary table.

**Prompt**: "What orders are currently processing?"
**Expected Behavior**: Agent calls `get_order` for all known orders, filters and reports processing ones.

## Key Concepts

**CUSTOM_JWT inbound auth**: The harness validates every caller's bearer token against the configured OIDC discovery URL. Unauthorized callers receive a 401 before reaching the agent.

**outboundAuth.oauth**: The harness fetches an M2M token from the credential provider on every tool call. Your code never handles M2M credentials directly.

**Credential providers**: Registered once with `create_oauth2_credential_provider`. The harness references the provider ARN — no secrets in the harness config or invoke call.

**Event stream parsing**: This script calls the HTTPS endpoint directly (boto3 doesn't support bearer-token invocation for harness). The response is a binary event-stream that requires JSON extraction.

## Troubleshooting

### Issue: `HARNESS_USER_NAME` or `HARNESS_USER_PASS` not set
**Solution**: Export both environment variables before running:
```bash
export HARNESS_USER_NAME="testuser"
export HARNESS_USER_PASS="TestPassword123!"
```

### Issue: Cognito `USER_PASSWORD_AUTH` returns `NotAuthorizedException`
**Solution**: Verify the user was created successfully (`admin_create_user`) and password was set permanently (`admin_set_user_password`). Re-run `create_user_auth_pool` — it's idempotent.

### Issue: HTTP 403 when invoking harness
**Solution**: The bearer token may be expired. Re-authenticate with `cognito.initiate_auth` to get a fresh token.

## AgentCore CLI

The CLI supports both inbound JWT auth and outbound OAuth2 credential providers via the preview channel:

```bash
npm install -g @aws/agentcore@preview
agentcore create --name myauthagent --model-provider bedrock
```

In the interactive wizard, configure **Advanced Settings → Auth** to set up inbound JWT (CUSTOM_JWT) and outbound OAuth2 credential providers. After setup:

```bash
agentcore deploy
```

For invoking a JWT-protected harness, the CLI will handle bearer token acquisition if your identity provider is configured. For programmatic control (as in this tutorial), use the boto3 SDK directly with a pre-fetched bearer token.

## Clean Up

```python
from utils.setup_helpers import cleanup_all
cleanup_all(REGION, "harness-oauth-demo")
```

The `cleanup_all` function deletes all resources in reverse order: harness, gateway, Lambda, IAM roles, both Cognito pools.

## Running the Python Scripts

```bash
pip install -r ../../requirements.txt
pip install requests
```

```bash
export HARNESS_USER_NAME="testuser"
export HARNESS_USER_PASS="TestPassword123!"
python oauth_gateway.py

# Keep resources for exploration
python oauth_gateway.py --skip-cleanup
```
