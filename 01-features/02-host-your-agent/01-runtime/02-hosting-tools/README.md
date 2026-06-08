# Hosting MCP Tools on AgentCore runtime

## Overview

AgentCore runtime can host [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) servers, making your tools available to any MCP-compatible client. When you set the protocol to `MCP`, AgentCore runtime expects a stateless streamable-HTTP MCP server on `0.0.0.0:8000/mcp`.

## How MCP Hosting Differs from Agent Hosting

| Aspect | Agent (HTTP) | MCP Server |
|:-------|:-------------|:-----------|
| `serverProtocol` | `HTTP` | `MCP` |
| SDK pattern | `@app.entrypoint` | `app.mcp_app = mcp` |
| Port | 8080 | 8000 |
| Path | `/invocations` | `/mcp` |
| Communication | Free-form JSON | JSON-RPC 2.0 (MCP spec) |
| Client sends | Any JSON payload | MCP methods: `tools/call`, `resources/read`, etc. |

## Writing an MCP Server

Use the `mcp` Python SDK's `FastMCP` class and assign it to the `BedrockAgentCoreApp`:

```python
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("my-tools")

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

app = BedrockAgentCoreApp()
app.mcp_app = mcp  # ← this tells the SDK to serve MCP instead of HTTP

if __name__ == "__main__":
    app.run()
```

## Deploying an MCP Server

The deployment is identical to agents — only `serverProtocol` and `entryPoint` change:

```python
control = boto3.client("bedrock-agentcore-control")

control.create_agent_runtime(
    agentRuntimeName="my-mcp-server",
    agentRuntimeArtifact={
        "codeConfiguration": {
            "code": {"s3": {"bucket": "my-bucket", "prefix": "my-server/code.zip"}},
            "runtime": "PYTHON_3_12",
            "entryPoint": ["mcp_server.py"],  # ← your MCP server file
        }
    },
    roleArn=role_arn,
    networkConfiguration={"networkMode": "PUBLIC"},
    protocolConfiguration={"serverProtocol": "MCP"},  # ← MCP protocol
)
```

> **IAM note**: MCP tool servers typically don't call LLMs, so the IAM role only needs CloudWatch logging permissions. Add permissions for any AWS services your tools access (DynamoDB, S3, etc.).

## Invoking an MCP Server

Clients send MCP JSON-RPC messages through `invoke_agent_runtime`. The payload is passed through directly to your MCP server:

```python
data = boto3.client("bedrock-agentcore")

# MCP JSON-RPC message
msg = {
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 1,
    "params": {"name": "add", "arguments": {"a": 5, "b": 3}},
}

response = data.invoke_agent_runtime(
    agentRuntimeArn=arn,
    payload=json.dumps(msg).encode(),
)
result = json.loads(response["response"].read().decode())
# {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "8"}]}}
```

## MCP Feature Support on AgentCore runtime

| Category | Feature | Spec Methods | Supported |
|:---------|:--------|:-------------|:---------:|
| **Server** | Tools | `tools/list`, `tools/call` | ✅ |
| **Server** | Resources | `resources/list`, `resources/read` | ✅ |
| **Server** | Prompts | `prompts/list`, `prompts/get` | ✅ |
| **Client** | Sampling | `sampling/createMessage` | ✅ |
| **Client** | Elicitation | `elicitation/create` | ✅ |
| **Protocol** | Lifecycle | `initialize`, `ping` | ✅ |
| **Protocol** | Transports | Streamable HTTP | ✅ |
| **Utilities** | Progress | `notifications/progress` | ✅ |
| **Utilities** | Logging | `logging/setLevel` | ✅ |

## Key Technical Details

- **Transport**: Stateless streamable HTTP — AgentCore provides session isolation via the `Mcp-Session-Id` header automatically
- **Port**: MCP server runs on port `8000` at path `/mcp` (this is the default for most MCP SDKs)
- **Content types**: Supports both `application/json` and `text/event-stream` responses
- **Payload passthrough**: The `invoke_agent_runtime` payload is forwarded directly to your MCP server as-is

## Tutorials

| Tutorial | What You'll Learn |
|:---------|:------------------|
| [01-mcp-server-basics](01-mcp-server-basics/) | Define tools, deploy, invoke with `tools/list` and `tools/call` |
| [02-mcp-server-features](02-mcp-server-features/) | Resources, prompts, and the full MCP feature set |
