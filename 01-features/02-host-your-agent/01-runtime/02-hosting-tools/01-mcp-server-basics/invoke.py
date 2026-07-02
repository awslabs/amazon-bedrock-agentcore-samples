"""
Invoke an MCP server deployed on AgentCore Runtime.

Sends MCP JSON-RPC messages (tools/list, tools/call) via the
invoke_agent_runtime API. The payload is passed through directly
to the MCP server.

Usage:
    python invoke.py
"""

import json
import sys

import boto3


def load_config() -> dict:
    try:
        with open("runtime_config.json") as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: runtime_config.json not found. Run deploy.py first.")
        sys.exit(1)


def send_mcp_rpc(runtime_arn: str, method: str, params: dict, region: str, rpc_id: int = 1) -> dict:
    """Send an MCP JSON-RPC message to the deployed server."""
    client = boto3.client("bedrock-agentcore", region_name=region)

    rpc_message = {
        "jsonrpc": "2.0",
        "method": method,
        "id": rpc_id,
        "params": params,
    }

    response = client.invoke_agent_runtime(
        agentRuntimeArn=runtime_arn,
        payload=json.dumps(rpc_message).encode("utf-8"),
        contentType="application/json",
        accept="application/json, text/event-stream",
    )

    body = response["response"].read().decode("utf-8")
    return json.loads(body)


def main():
    config = load_config()
    runtime_arn = config["runtime_arn"]
    region = config["region"]

    print(f"MCP Server: {runtime_arn}\n")

    # 1. Initialize the MCP session
    print("─── Initialize")
    result = send_mcp_rpc(
        runtime_arn,
        "initialize",
        {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "tutorial-client", "version": "1.0.0"},
        },
        region,
        rpc_id=1,
    )
    print(f"    Server: {json.dumps(result.get('result', {}).get('serverInfo', {}))}\n")

    # 2. List available tools
    print("─── tools/list")
    result = send_mcp_rpc(runtime_arn, "tools/list", {}, region, rpc_id=2)
    tools = result.get("result", {}).get("tools", [])
    for t in tools:
        print(f"    • {t['name']}: {t.get('description', '')}")
    print()

    # 3. Call tools
    print("─── tools/call: add_numbers(5, 3)")
    result = send_mcp_rpc(
        runtime_arn,
        "tools/call",
        {
            "name": "add_numbers",
            "arguments": {"a": 5, "b": 3},
        },
        region,
        rpc_id=3,
    )
    print(f"    Result: {json.dumps(result.get('result', {}))}\n")

    print("─── tools/call: multiply_numbers(7, 6)")
    result = send_mcp_rpc(
        runtime_arn,
        "tools/call",
        {
            "name": "multiply_numbers",
            "arguments": {"a": 7, "b": 6},
        },
        region,
        rpc_id=4,
    )
    print(f"    Result: {json.dumps(result.get('result', {}))}\n")

    print("─── tools/call: greet('Alice', 'spanish')")
    result = send_mcp_rpc(
        runtime_arn,
        "tools/call",
        {
            "name": "greet",
            "arguments": {"name": "Alice", "language": "spanish"},
        },
        region,
        rpc_id=5,
    )
    print(f"    Result: {json.dumps(result.get('result', {}))}\n")


if __name__ == "__main__":
    main()
