"""
Exercise all MCP features: tools, resources, and prompts.

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


def mcp_rpc(client, arn: str, method: str, params: dict, rpc_id: int) -> dict:
    msg = {"jsonrpc": "2.0", "method": method, "id": rpc_id, "params": params}
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=arn,
        payload=json.dumps(msg).encode("utf-8"),
        contentType="application/json",
        accept="application/json, text/event-stream",
    )
    return json.loads(resp["response"].read().decode("utf-8"))


def main():
    config = load_config()
    client = boto3.client("bedrock-agentcore", region_name=config["region"])
    arn = config["runtime_arn"]
    rpc_id = 0

    print(f"MCP Server: {arn}\n")

    # Initialize
    rpc_id += 1
    mcp_rpc(
        client,
        arn,
        "initialize",
        {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "tutorial", "version": "1.0"},
        },
        rpc_id,
    )

    # ── Tools ────────────────────────────────────────────────────────────
    print("═══ TOOLS ═══")
    rpc_id += 1
    result = mcp_rpc(client, arn, "tools/list", {}, rpc_id)
    for t in result.get("result", {}).get("tools", []):
        print(f"  • {t['name']}: {t.get('description', '')}")

    rpc_id += 1
    result = mcp_rpc(
        client,
        arn,
        "tools/call",
        {
            "name": "search_documents",
            "arguments": {"query": "machine learning", "max_results": 3},
        },
        rpc_id,
    )
    print("\n  search_documents('machine learning'):")
    print(f"  {json.dumps(result.get('result', {}), indent=4)}")

    rpc_id += 1
    result = mcp_rpc(
        client,
        arn,
        "tools/call",
        {
            "name": "analyze_sentiment",
            "arguments": {"text": "This is a great product and I love using it every day!"},
        },
        rpc_id,
    )
    print("\n  analyze_sentiment(...):")
    print(f"  {json.dumps(result.get('result', {}), indent=4)}")

    # ── Resources ────────────────────────────────────────────────────────
    print("\n═══ RESOURCES ═══")
    rpc_id += 1
    result = mcp_rpc(client, arn, "resources/list", {}, rpc_id)
    for r in result.get("result", {}).get("resources", []):
        print(f"  • {r['uri']}: {r.get('name', '')}")

    rpc_id += 1
    result = mcp_rpc(client, arn, "resources/read", {"uri": "config://app"}, rpc_id)
    print("\n  config://app:")
    print(f"  {json.dumps(result.get('result', {}), indent=4)}")

    # ── Prompts ──────────────────────────────────────────────────────────
    print("\n═══ PROMPTS ═══")
    rpc_id += 1
    result = mcp_rpc(client, arn, "prompts/list", {}, rpc_id)
    for p in result.get("result", {}).get("prompts", []):
        print(f"  • {p['name']}: {p.get('description', '')}")

    rpc_id += 1
    result = mcp_rpc(
        client,
        arn,
        "prompts/get",
        {
            "name": "code_review",
            "arguments": {"code": "def add(a, b): return a + b", "language": "python"},
        },
        rpc_id,
    )
    print("\n  code_review prompt:")
    messages = result.get("result", {}).get("messages", [])
    for msg in messages:
        print(f"  {msg.get('content', {}).get('text', '')[:200]}")

    print("\n✓ All MCP features exercised successfully")


if __name__ == "__main__":
    main()
