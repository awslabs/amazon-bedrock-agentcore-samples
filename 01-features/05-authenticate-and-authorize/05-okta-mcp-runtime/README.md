# Okta-Authenticated MCP Server on AgentCore Runtime

| Information         | Details                                                              |
|:--------------------|:---------------------------------------------------------------------|
| Tutorial type       | Step-by-step                                                         |
| Agent type          | MCP Server runtime (no agent runtime)                                |
| Tutorial components | AgentCore runtime, Okta Custom Authorization Server, Bedrock KB      |
| Example complexity  | Intermediate                                                         |
| SDK used            | boto3, mcp (FastMCP)                                                 |
| Inbound Auth        | Okta JWT via Authorization Code + PKCE                               |
| Outbound Auth       | None (read-only Knowledge Base query)                                |

## Overview

This sample deploys a **FastMCP server** to Amazon Bedrock AgentCore Runtime,
protected by **Okta JWT validation** via `customJWTAuthorizer`. The MCP server
wraps an Amazon Bedrock Knowledge Base and exposes a single read-only tool
(`query_knowledge_base`) that performs semantic search and returns answers with
source citations.

**Pick this pattern when:**
- You have an MCP server that should only accept requests from authenticated users
- Your organization uses Okta as an identity provider
- You want AgentCore to handle JWT validation (no auth code in your server)
- Your MCP server calls AWS services via an IAM execution role (no user token forwarding)

## Architecture

```
1. MCP Client → Okta (Authorization Code + PKCE) → access token (JWT)
2. MCP Client + Bearer JWT → AgentCore Runtime → customJWTAuthorizer validates:
     - iss: Okta Custom Authorization Server
     - aud: matches allowedAudience
     - client_id: matches allowedClients
3. AgentCore → FastMCP container → Bedrock RetrieveAndGenerate (IAM role)
4. Response (answer + citations) → MCP Client
```

### Key design points

| Aspect | Detail |
|--------|--------|
| Auth flow | Authorization Code + PKCE (public client, no client secret) |
| Token validation | AgentCore validates JWT; container never sees raw token |
| `client_id` claim | Okta must be configured with a custom claim mapping (see OKTA_SETUP.md) |
| Bedrock access | Container uses IAM execution role, not user tokens |

## Prerequisites

- **AWS CLI** configured with a profile that has permissions to create IAM roles, ECR repositories, and AgentCore runtimes
- **Docker** with `buildx` support (for linux/arm64 builds)
- **Python 3.12+** with `pip install requests boto3`
- **Okta admin access** to configure a Custom Authorization Server and Native Application (see [OKTA_SETUP.md](OKTA_SETUP.md))
- **An existing Bedrock Knowledge Base** — this sample queries an existing KB, it does not create one

## Step 1 — Configure Okta

Follow [OKTA_SETUP.md](OKTA_SETUP.md) to:
1. Set up a Custom Authorization Server with an audience
2. Create a Native Application (OIDC, Authorization Code + PKCE)
3. Add the `client_id` custom claim (required by AgentCore)

## Step 2 — Set environment variables

```bash
# Okta
export OKTA_DOMAIN="dev-12345678.okta.com"
export OKTA_AUTH_SERVER_ID="aus1234567890abcdef"
export OKTA_CLIENT_ID="0oa1234567890abcdef"
export OKTA_AUDIENCE="api://my-mcp"

# Bedrock Knowledge Base
export KNOWLEDGE_BASE_ID="ABCDEFGHIJ"
export KB_REGION="us-east-1"
export BEDROCK_MODEL_ARN="arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-sonnet-4-20250514"
```

## Step 3 — Deploy

```bash
pip install requests boto3
python okta_mcp_runtime.py
```

This will:
1. Create an IAM execution role with Bedrock KB and model permissions
2. Build and push a Docker image (linux/arm64) to ECR
3. Create an AgentCore MCP Runtime with Okta JWT validation
4. Wait for the runtime to reach READY status
5. Open your browser for Okta sign-in (PKCE flow)
6. Run test invocations against the MCP endpoint

## Step 4 — Connect an MCP client

After deployment, the script prints a Claude Code config snippet. Add it to
`~/.claude.json`:

```json
{
  "mcpServers": {
    "knowledge-base": {
      "type": "http",
      "url": "https://bedrock-agentcore.<region>.amazonaws.com/runtimes/<encoded-arn>/invocations?qualifier=DEFAULT",
      "oauth": {
        "clientId": "<your-okta-client-id>",
        "authServerMetadataUrl": "https://<your-okta-domain>/oauth2/<auth-server-id>/.well-known/openid-configuration",
        "callbackPort": 8090
      }
    }
  }
}
```

### Client compatibility

| Client | Status | Notes |
|--------|--------|-------|
| Claude Code | Supported | Native OAuth + Streamable HTTP |
| Cursor | Supported | Native OAuth + Streamable HTTP |
| VS Code Copilot | Not supported | Requires Dynamic Client Registration (DCR) |

**Requirements:** The MCP client must support Streamable HTTP transport, a
pinned redirect URI (`http://localhost:8090/callback`), and a pre-registered
client ID (no DCR).

## Invoke only (re-test after deploy)

```bash
python okta_mcp_runtime.py --invoke
```

Reads the saved config and runs the PKCE flow + MCP invocation without redeploying.

## Clean up

```bash
python okta_mcp_runtime.py --cleanup
```

Deletes the AgentCore runtime, IAM role, and ECR repository.

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `401 Unauthorized` | Missing or invalid Bearer token | Re-run `--invoke` to get a fresh token |
| `invalid_client` from Okta | Wrong client ID or app type | Verify OKTA_CLIENT_ID; must be a Native Application |
| `redirect_uri mismatch` | Okta app redirect URI doesn't match | Set redirect URI to `http://localhost:8090/callback` |
| `client_id claim missing` | Custom claim not configured | Follow Step 3 in OKTA_SETUP.md |
| `Role validation failed` | IAM role not yet propagated | Script retries automatically; wait and retry |
| `CREATE_FAILED` | Container startup error | Check CloudWatch logs for the runtime |

## Files

| File | Purpose |
|------|---------|
| `okta_mcp_runtime.py` | Deploy, invoke, and cleanup orchestration |
| `mcp_server.py` | FastMCP server with `query_knowledge_base` tool |
| `Dockerfile` | Container image for AgentCore (arm64) |
| `requirements.txt` | Python dependencies for the MCP server |
| `OKTA_SETUP.md` | Okta admin configuration guide |

## Sample prompts

Once the MCP server is deployed and connected to a client, try:

- "What topics does this knowledge base cover?"
- "Summarize the main concepts in the documentation."
- "How do I get started with [topic from your KB]?"

The responses will include an answer generated by the model and citations
pointing back to the source documents in the knowledge base.

## Disclaimer

The examples provided in this repository are for experimental and educational
purposes only. They demonstrate concepts and techniques but are not intended
for direct use in production environments. Make sure to have Amazon Bedrock
Guardrails in place to protect against
[prompt injection](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-injection.html).
