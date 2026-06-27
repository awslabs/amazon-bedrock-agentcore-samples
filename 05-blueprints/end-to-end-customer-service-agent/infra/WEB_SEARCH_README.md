# AgentCore Web Search Tool Integration

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
Purpose-built web index (tens of billions of documents)
```

## Key Benefits

- **No API keys or external services** — fully managed by AWS
- **Queries never leave AWS** — served entirely within AWS infrastructure
- **Purpose-built web index** — tens of billions of documents, continuously updated
- **Semantic snippet extraction** — returns relevant passages optimized for LLM context windows
- **Knowledge graph** — high-confidence factual answers for entity-based questions
- **Zero infrastructure** — add as a connector target to your gateway, no Lambda or containers needed

## Setup

### Via AWS Console

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

### Gateway Service Role Permission

The gateway execution role needs permission to invoke the connector. Add this policy:

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

## Input Schema

```json
{
  "query": "The search query string (required, max 200 chars)",
  "maxResults": 10
}
```

## Response Format

Returns MCP-compliant results with:
- `text` — semantically relevant snippet
- `url` — source webpage URL
- `title` — page title
- `publishedDate` — publication date

## Testing

```bash
# List tools (verify WebSearch appears)
curl -s -X POST "<gateway-url>" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | python3 -m json.tool

# Invoke web search
curl -s -X POST "<gateway-url>" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"web-search-target___WebSearch","arguments":{"query":"AWS re:Invent 2025 announcements","maxResults":5}}}' | python3 -m json.tool
```

## Terraform

The AWS Terraform provider does not yet support the `connector` target type. The Terraform code removes the Tavily Lambda resources and documents the CLI/console post-apply step for adding the Web Search connector.

## Availability

Check [AWS documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/) for current regional availability of the Web Search Tool connector.
