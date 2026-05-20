# MCP Server Advanced Features

## Overview

Beyond basic tools, MCP servers can expose **resources** (data sources), **prompts** (reusable templates), and support **sampling** (server-initiated LLM calls). This example demonstrates all three on AgentCore runtime.

> **If you're new to MCP on AgentCore**, start with the [MCP Server Basics](../01-mcp-server-basics/) example first.

## MCP Capabilities Demonstrated

### Tools — functions the LLM can call

Tools are the most common MCP feature. They let clients discover and execute functions:

```python
@mcp.tool()
def search_documents(query: str, max_results: int = 5) -> str:
    """Search a document database."""
    # Your search logic here
    return json.dumps(results)
```

Clients call tools via `tools/call`:
```json
{"jsonrpc": "2.0", "method": "tools/call", "id": 1,
 "params": {"name": "search_documents", "arguments": {"query": "machine learning"}}}
```

### Resources — data the client can read

Resources expose data at URIs. Unlike tools, resources are read-only and don't take arbitrary arguments:

```python
@mcp.resource("config://app")
def get_app_config() -> str:
    """Application configuration settings."""
    return json.dumps({"version": "2.1.0", "environment": "production"})

@mcp.resource("data://system-status")
def get_system_status() -> str:
    """Current system health metrics."""
    return json.dumps({"status": "healthy", "uptime_hours": 142.5})
```

Clients discover resources with `resources/list` and read them with `resources/read`:
```json
{"jsonrpc": "2.0", "method": "resources/read", "id": 1, "params": {"uri": "config://app"}}
```

### Prompts — reusable templates

Prompts are parameterized templates that clients can retrieve and fill in. They're useful for standardizing how LLMs interact with your tools:

```python
@mcp.prompt()
def code_review(code: str, language: str = "python") -> str:
    """Generate a code review prompt."""
    return (
        f"Review this {language} code for bugs, performance, and security:\n\n"
        f"```{language}\n{code}\n```"
    )
```

Clients discover prompts with `prompts/list` and get them with `prompts/get`:
```json
{"jsonrpc": "2.0", "method": "prompts/get", "id": 1,
 "params": {"name": "code_review", "arguments": {"code": "def add(a, b): return a + b"}}}
```

## Invoking All Features

The `invoke.py` script exercises every MCP feature through `invoke_agent_runtime`:

```python
# Helper to send MCP JSON-RPC messages
def mcp_rpc(client, arn, method, params, rpc_id):
    msg = {"jsonrpc": "2.0", "method": method, "id": rpc_id, "params": params}
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=arn,
        payload=json.dumps(msg).encode(),
        contentType="application/json",
        accept="application/json",
    )
    return json.loads(resp["response"].read().decode())

# Initialize session
mcp_rpc(client, arn, "initialize", {...}, 1)

# Tools
mcp_rpc(client, arn, "tools/list", {}, 2)
mcp_rpc(client, arn, "tools/call", {"name": "search_documents", "arguments": {...}}, 3)

# Resources
mcp_rpc(client, arn, "resources/list", {}, 4)
mcp_rpc(client, arn, "resources/read", {"uri": "config://app"}, 5)

# Prompts
mcp_rpc(client, arn, "prompts/list", {}, 6)
mcp_rpc(client, arn, "prompts/get", {"name": "code_review", "arguments": {...}}, 7)
```

All MCP JSON-RPC messages are passed through `invoke_agent_runtime` directly to your MCP server. AgentCore runtime handles session isolation via the `Mcp-Session-Id` header.

## Files

| File | Description |
|:-----|:------------|
| `mcp_server.py` | MCP server with tools (`search_documents`, `analyze_sentiment`, `get_timestamp`), resources (`config://app`, `data://system-status`), and prompts (`code_review`, `summarize_document`) |
| `requirements.txt` | `mcp`, `boto3`, `bedrock-agentcore` |
| `deploy.py` | Same deployment pattern with `serverProtocol='MCP'` |
| `invoke.py` | Exercises all MCP features: `tools/list`, `tools/call`, `resources/list`, `resources/read`, `prompts/list`, `prompts/get` |
| `cleanup.py` | Same cleanup pattern |

## Quick Start

```bash
python deploy.py     # Deploy MCP server
python invoke.py     # Exercise all MCP features
python cleanup.py    # Clean up
```
