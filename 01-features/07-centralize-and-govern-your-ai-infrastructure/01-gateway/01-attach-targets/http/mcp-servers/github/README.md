# GitHub MCP Server through the Gateway

Front the [GitHub MCP server](https://github.com/github/github-mcp-server) (`https://api.githubcopilot.com/mcp/`) through an AgentCore Gateway as an `http.passthrough` target with `protocolType=MCP`. The gateway uses **no inbound authorization** and **JWT passthrough** for outbound: it forwards the caller's `Authorization` header (the client's own GitHub token) to the GitHub MCP server unchanged.

The GitHub MCP server exposes GitHub repositories, issues, pull requests, and more as MCP tools. It requires a GitHub token with appropriate access.

## Architecture

<!-- ![Architecture](images/architecture.png) -->

| Component | Role |
| :-- | :-- |
| AgentCore Gateway | Fronts `api.githubcopilot.com` as an `http.passthrough` MCP target; no inbound auth, forwards the caller's Authorization header outbound |
| GitHub MCP server | Hosted MCP server serving GitHub repository, issue, and pull-request tools |

```mermaid
sequenceDiagram
    participant Client
    participant GW as AgentCore Gateway
    participant GH as GitHub MCP

    Client->>GW: 1. MCP request to /github/mcp (Authorization: Bearer github-token)
    Note over GW: No inbound auth (authorizerType NONE)
    GW->>GH: 2. Forward to api.githubcopilot.com/mcp/ (Authorization passed through)
    GH-->>GW: 3. MCP response
    GW-->>Client: 4. MCP response
```

Path-based routing forwards `{GATEWAY_URL}/{targetName}/{path}` to `https://api.githubcopilot.com/mcp/{path}`.

## Tutorial details

| Item | Value |
| :-- | :-- |
| Target type | HTTP passthrough, `protocolType=MCP` |
| Endpoint | `https://api.githubcopilot.com/mcp/` |
| Inbound auth | None (`authorizerType=NONE`) |
| Outbound auth | JWT passthrough (forwards the caller's `Authorization` header) |
| Gateway | Shared no-auth `context7-gateway` (no protocol type) |

> [!IMPORTANT]
> No-auth gateways accept unauthenticated requests from anyone who can reach the gateway URL. Use them only for token-forwarding targets like this one, or add your own access controls (for example, an interceptor). For a gateway that validates the inbound token before forwarding it, use `CUSTOM_JWT` inbound with `JWT_PASSTHROUGH` outbound instead.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) installed
- Node.js >= 22.7.5
- [AgentCore CLI](https://www.npmjs.com/package/@aws/agentcore): `npm install -g @aws/agentcore`
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) configured with credentials (`aws configure`)
- [IAM permissions](https://github.com/aws/agentcore-cli/blob/main/docs/PERMISSIONS.md)
- A GitHub token with access to the GitHub MCP server (a personal access token or GitHub Copilot access)

## Deployment Steps

> [!IMPORTANT]
> All commands in this tutorial run from the [`gatewaylabproject/`](../../../../../gatewaylabproject/) directory. Navigate there before proceeding.

### Step 1: Create the no-auth gateway

HTTP passthrough targets attach to a gateway that has no protocol type set. This script creates a no-auth gateway (`authorizerType=NONE`), or reuses it if it already exists. The gateway is shared with the [Context7 MCP](../context7/) lab.

```bash
uv run python scripts/github-mcp-passthrough/deploy_gateway.py
```

Capture the gateway URL:

```bash
export GATEWAY_URL=$(grep GATEWAY_URL scripts/github-mcp-passthrough/.env | cut -d= -f2)

echo "Gateway URL: $GATEWAY_URL"
```

### Step 2: Create the GitHub passthrough target

Attach `https://api.githubcopilot.com/mcp/` as a passthrough target with `protocolType=MCP` and `JWT_PASSTHROUGH` outbound, so the caller's `Authorization` header is forwarded to the GitHub MCP server unchanged.

```bash
uv run python scripts/github-mcp-passthrough/deploy.py
```

The script calls `create_gateway_target` with this configuration:

```json
{
  "targetConfiguration": {
    "http": {
      "passthrough": {
        "endpoint": "https://api.githubcopilot.com/mcp/",
        "protocolType": "MCP"
      }
    }
  },
  "credentialProviderConfigurations": [
    { "credentialProviderType": "JWT_PASSTHROUGH" }
  ]
}
```

- `protocolType: MCP` gets a default schema, so no `schema` is needed (unlike `CUSTOM`).
- `JWT_PASSTHROUGH` forwards the inbound `Authorization` header outbound unchanged. The gateway does not store a GitHub token; the client supplies its own. This is supported on passthrough targets with `NONE` or `CUSTOM_JWT` inbound auth.

### Step 3: Verify

```bash
agentcore status
```

The `github` target should reach `READY`.

## Demo

Call the GitHub MCP server through the gateway. With `authorizerType=NONE`, no gateway token is needed; send your GitHub token as the `Authorization` header, which the gateway forwards to GitHub.

```bash
export GITHUB_TOKEN="<your-github-token>"

curl -sS -X POST "${GATEWAY_URL}/github/mcp" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

The GitHub MCP server exposes tools for repositories, issues, and pull requests. A valid GitHub token is required (unlike Context7, the GitHub MCP server has no unauthenticated tier).

You can also point any MCP client at `${GATEWAY_URL}/github/mcp` with the same `Authorization` header.

## Cleanup

From the [`gatewaylabproject/`](../../../../../gatewaylabproject/) directory:

```bash
uv run python scripts/github-mcp-passthrough/cleanup.py
```

> [!NOTE]
> The `context7-gateway` is shared with the Context7 MCP lab. Cleanup removes only this lab's `github` target. It deletes the shared gateway and its IAM role only when no targets remain (that is, the Context7 lab has also been cleaned up).

## Documentation

- [AgentCore Gateway Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html)
- [HTTP targets](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-targets-http.html)
- [GitHub MCP server](https://github.com/github/github-mcp-server)
