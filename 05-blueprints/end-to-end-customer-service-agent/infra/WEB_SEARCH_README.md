# AgentCore Web Search Tool integration

Provides web search capability for the customer service agent using the AgentCore managed Web Search Tool connector — zero infrastructure, no API keys, queries stay within AWS.

## Architecture

```
Agent / Client
    │
    ▼
AgentCore Gateway (auth + interceptor)
    │
    │ Managed connector (no Lambda, no external API)
    ▼
AgentCore Web Search Tool
    │
    ▼
Purpose-built web index (continuously updated)
```

## Key benefits

- **No API keys or external services** — fully managed by AWS
- **Queries never leave AWS** — served entirely within AWS infrastructure
- **Purpose-built web index** — broad coverage, continuously updated within minutes
- **Semantic snippet extraction** — returns relevant passages optimized for LLM context windows
- **Knowledge graph** — high-confidence factual answers for entity-based questions
- **Zero infrastructure** — add as a connector target to your gateway, no Lambda or containers needed

For the latest details on coverage, freshness, and capabilities, see the [Web Search Tool documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/).

## Setup

### Via AWS console

1. Go to **Bedrock → AgentCore → Gateways → your gateway**
2. Click **Targets** → **Add**
3. Select **Connectors** → **Web Search**
4. Target name: `web-search-target`
5. Click **Add target**

### Via CLI

```bash
aws bedrock-agentcore-control create-gateway-target \
  --gateway-identifier <gateway-id> \
  --name "web-search-target" \
  --target-configuration '{"mcp":{"connector":{"connectorId":"web-search"}}}' \
  --region <your-region>
```

### Gateway service role permissions

The gateway execution role needs permission to invoke the connector. Add this policy to your gateway's IAM role. Refer to the [official documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/) for the latest IAM action names:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["bedrock-agentcore:InvokeConnector"],
      "Resource": "*"
    }
  ]
}
```

> **Note:** If the above action doesn't work, check the official docs for the correct action string — IAM action names are case-sensitive and may change between preview and GA.

## Input schema

```json
{
  "query": "The search query string (required, max 200 chars)",
  "maxResults": 10
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | Yes | Search query, max 200 characters |
| `maxResults` | integer | No | Results to return (1-25, default 10) |

## Response format

Returns MCP-compliant results with:
- `text` — semantically relevant snippet
- `url` — source webpage URL
- `title` — page title
- `publishedDate` — publication date

## Testing

### List tools (verify WebSearch appears)

```bash
curl -s -X POST "<gateway-url>" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | python3 -m json.tool
```

Expected: `web-search-target___WebSearch` in the tools list with `query` (required) and `maxResults` (optional) parameters.

### Invoke web search

```bash
curl -s -X POST "<gateway-url>" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"web-search-target___WebSearch","arguments":{"query":"latest AWS announcements","maxResults":5}}}' | python3 -m json.tool
```

Expected response:
```json
{
  "isError": false,
  "content": [
    {
      "type": "text",
      "text": "{\"results\":[{\"text\":\"...\",\"url\":\"https://...\",\"title\":\"...\",\"publishedDate\":\"2026-06-25\"}]}"
    }
  ]
}
```

### Invoke via Python

```python
import boto3, json

# Assumes gateway token is already obtained
response = gateway_client.invoke(
    method="tools/call",
    params={
        "name": "web-search-target___WebSearch",
        "arguments": {"query": "AWS AgentCore Web Search Tool", "maxResults": 3}
    }
)
print(json.dumps(response["results"], indent=2))
```

## Terraform

The AWS Terraform provider does not yet support the `connector` target type. After `terraform apply`, add the Web Search target via the console or CLI as described above.

## Availability

Check [AWS documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/) for current regional availability of the Web Search Tool connector.
