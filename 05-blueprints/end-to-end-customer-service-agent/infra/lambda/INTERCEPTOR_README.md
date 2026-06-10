# AgentCore Gateway Lambda Interceptor

## Overview

This directory contains the Lambda interceptor for the AgentCore Gateway used in the end-to-end customer service agent blueprint. The interceptor sits between the client and the gateway targets, providing security, observability, and transformation capabilities on every tool call.

## Architecture

```
Client / Agent
      │
      │  MCP tool call (with Bearer token)
      ▼
AgentCore Gateway
      │
      ├── REQUEST interceptor fires (gateway_interceptor.py)
      │         token validation, rate limiting, logging, header injection, input transformation
      │
      ▼
Gateway Target (e.g. Tavily Lambda)
      │
      ├── RESPONSE interceptor fires (gateway_interceptor.py)
      │         PII masking, response logging, error normalisation
      │
      ▼
Client / Agent receives response
```

One Lambda function handles both request and response interception. The gateway determines which path to invoke based on whether `gatewayResponse` is present in the event payload.

## Files

| File | Description |
|------|-------------|
| `gateway_interceptor.py` | Interceptor Lambda — handles request and response paths |
| `tavily_search.py` | Tavily web search tool Lambda |

## What the Interceptor Does

### Request path

**1. Token validation**
Checks that the inbound `Authorization` header is present, uses Bearer scheme, and contains a structurally valid JWT (three base64 segments). Blocks requests with missing or malformed tokens with a `-32001` JSON-RPC error.

For production, replace the structural check in `_validate_token` with full JWT signature verification using the Cognito JWKS endpoint.

**2. Logging and auditing**
Emits a structured JSON log entry to CloudWatch for every tool call:
```json
{"event": "tool_call_request", "caller_id": "...", "method": "tools/call", "tool": "tavily_search", "timestamp": 1234567890}
```
This provides a complete audit trail of who called which tool and when.

**3. Request validation**
Checks the requested tool name against an allowlist (`ALLOWED_TOOLS`). Blocks calls to tools not in the list with a `-32002` error. This prevents agents from calling tools they are not authorised to use even if those tools exist on the gateway.

**4. Rate limiting**
Enforces a per-caller call quota using DynamoDB. Each caller (identified by the `sub` claim in the JWT) gets a counter per time window. If the counter exceeds `RATE_LIMIT_MAX`, the request is blocked with a `-32003` error.

Controlled by environment variables:
- `ENABLE_RATE_LIMIT` — set to `false` to disable (useful for development)
- `RATE_LIMIT_MAX` — max calls per window (default 100)
- `RATE_LIMIT_WINDOW` — window in seconds (default 3600 = 1 hour)

**5. Input transformation**
Normalises parameter names before requests reach the target. For example, the agent may send `search_query` but the Tavily Lambda expects `query`. The interceptor translates these transparently so the agent doesn't need to know each target's exact schema.

**6. Header injection**
Injects downstream authentication and tracing headers:
- `x-api-key` — downstream API key (from `DOWNSTREAM_API_KEY` env var)
- `x-caller-id` — propagates caller identity for downstream audit trails
- `x-request-time` — timestamp for distributed tracing correlation

### Response path

**7. PII masking**
Recursively walks the response body and redacts sensitive data patterns before they reach the agent:
- Email addresses → `[EMAIL]`
- Phone numbers → `[PHONE]`
- US Social Security Numbers → `[SSN]`
- Credit card numbers → `[CARD]`
- ZIP codes → `[ZIP]`

This is critical for a customer service agent that may retrieve customer records containing personal information.

**8. Response logging**
Emits a structured log entry for every tool response:
```json
{"event": "tool_call_response", "method": "tools/call", "has_error": false, "streaming": false, "timestamp": 1234567890}
```

**9. Error normalisation**
Ensures all error responses follow the JSON-RPC error format so the agent always sees a consistent error structure regardless of what the target returned.

## Infrastructure Changes

The following Terraform resources were added to `main.tf`:

| Resource | Purpose |
|----------|---------|
| `aws_iam_role.interceptor_lambda_role` | Execution role for the interceptor Lambda |
| `aws_dynamodb_table.rate_limit_table` | Stores per-caller call counters for rate limiting. PAY_PER_REQUEST billing, TTL enabled for automatic cleanup |
| `aws_iam_role_policy.interceptor_dynamodb_policy` | Least-privilege policy allowing the Lambda to read/write the rate limit table only |
| `aws_lambda_function.gateway_interceptor` | The interceptor Lambda function |
| `aws_lambda_permission.allow_gateway_interceptor` | Allows AgentCore Gateway to invoke the interceptor |

The gateway IAM role policy (`gateway_policy`) was updated to include the interceptor Lambda ARN alongside the Tavily Lambda ARN.

New variables added to `variables.tf`:
- `interceptor_rate_limit_max` (default: 100)
- `interceptor_rate_limit_window` (default: 3600)
- `interceptor_enable_rate_limit` (default: true)

New outputs added to `outputs.tf`:
- `interceptor_lambda_arn`
- `interceptor_lambda_name`
- `rate_limit_table_name`

## Attaching the Interceptor to the Gateway

The AWS Terraform provider (v6.47) does not yet expose gateway interceptor configuration as a Terraform attribute. Attach the interceptor via the AWS console (Gateway → Edit → Interceptors) or CLI after `terraform apply`:

```bash
# Replace <gateway-id> with your gateway ID from terraform output
aws bedrock-agentcore-control update-gateway \
  --gateway-identifier <gateway-id> \
  --request-interceptor-lambda-arn <interceptor-lambda-arn> \
  --response-interceptor-lambda-arn <interceptor-lambda-arn> \
  --region us-east-1
```

Both request and response interceptors point to the same Lambda. Set `Pass request headers: True` for both so the `Authorization` header is available for token validation.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `RATE_LIMIT_TABLE` | DynamoDB table name for rate limit counters | `agentcore-gateway-rate-limits` |
| `RATE_LIMIT_MAX` | Max tool calls per caller per window | `100` |
| `RATE_LIMIT_WINDOW` | Rate limit window in seconds | `3600` |
| `ENABLE_RATE_LIMIT` | Enable/disable rate limiting | `true` |
| `DOWNSTREAM_API_KEY` | API key injected into downstream requests | `""` |

## Local Testing

Test the interceptor Lambda directly without going through the gateway:

```bash
aws lambda invoke \
  --function-name cx-gateway-interceptor \
  --payload '{"mcp":{"gatewayRequest":{"body":{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"tavily_search","arguments":{"query":"test"}}},"headers":{"authorization":"Bearer <your-token>"}}}}' \
  --region us-east-1 \
  --cli-binary-format raw-in-base64-out \
  response.json && cat response.json | python3 -m json.tool
```

Test the Tavily Lambda directly:

```bash
aws lambda invoke \
  --function-name tavily-search-function \
  --payload '{"query":"AWS AgentCore tutorial"}' \
  --region us-east-1 \
  --cli-binary-format raw-in-base64-out \
  tavily_response.json && cat tavily_response.json | python3 -m json.tool
```
