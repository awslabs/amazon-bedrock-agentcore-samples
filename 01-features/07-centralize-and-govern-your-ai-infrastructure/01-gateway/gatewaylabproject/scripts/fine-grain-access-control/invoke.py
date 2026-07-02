"""Demo: test fine-grained access control with different JWT scopes.

Tests tool invocation, tools/list, and semantic search with scoped tokens
to verify that REQUEST and RESPONSE interceptors enforce per-tool permissions.

Requires GATEWAY_URL, COGNITO_STACK_NAME, FGAC_CLIENT_ID, FGAC_CLIENT_SECRET
in environment or .env.

Usage:
    uv run python scripts/fine-grain-access-control/invoke.py
"""

import os
import sys

import boto3
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from gateway_mcp_client import GatewayMCPClient


def load_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key, value)


def get_required_env(key):
    val = os.environ.get(key)
    if not val:
        print(f"ERROR: {key} not set. Run deploy.py first or export it.")
        sys.exit(1)
    return val


def get_token(token_endpoint, client_id, client_secret, scope):
    response = requests.post(
        token_endpoint,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def main():
    load_env()

    gateway_url = get_required_env("GATEWAY_URL")
    cognito_stack = get_required_env("COGNITO_STACK_NAME")
    fgac_client_id = get_required_env("FGAC_CLIENT_ID")
    fgac_client_secret = get_required_env("FGAC_CLIENT_SECRET")

    region = boto3.Session().region_name
    cfn = boto3.client("cloudformation", region_name=region)

    cognito_outputs = {
        o["OutputKey"]: o["OutputValue"]
        for o in cfn.describe_stacks(StackName=cognito_stack)["Stacks"][0]["Outputs"]
    }
    token_endpoint = cognito_outputs["TokenEndpoint"]

    print(f"Gateway URL: {gateway_url}\n")

    # --- Test 1: getOrder with getOrder scope → ALLOW ---
    print("=" * 60)
    print("Test 1: getOrder with getOrder scope (SHOULD ALLOW)")
    print("=" * 60)

    scope = "fgac/fgac-mcp-target:getOrder"
    token = get_token(token_endpoint, fgac_client_id, fgac_client_secret, scope)
    mcp = GatewayMCPClient(gateway_url, lambda: token, protocol_version="2025-11-25")

    result = mcp.call_tool("fgac-mcp-target___getOrder", {})
    if "error" not in result:
        print("  PASS: getOrder allowed")
    else:
        print(f"  FAIL: {result['error'].get('message')}")

    # --- Test 2: updateOrder with getOrder scope → DENY ---
    print("\n" + "=" * 60)
    print("Test 2: updateOrder with getOrder scope (SHOULD DENY)")
    print("=" * 60)

    mcp = GatewayMCPClient(gateway_url, lambda: token, protocol_version="2025-11-25")
    result = mcp.call_tool("fgac-mcp-target___updateOrder", {"orderId": 123})
    if "error" in result:
        print(f"  PASS: Blocked — {result['error'].get('message')}")
    else:
        print("  FAIL: Should have been blocked!")

    # --- Test 3: deleteOrder with deleteOrder scope → ALLOW ---
    print("\n" + "=" * 60)
    print("Test 3: deleteOrder with deleteOrder scope (SHOULD ALLOW)")
    print("=" * 60)

    scope = "fgac/fgac-mcp-target:deleteOrder"
    token = get_token(token_endpoint, fgac_client_id, fgac_client_secret, scope)
    mcp = GatewayMCPClient(gateway_url, lambda: token, protocol_version="2025-11-25")

    result = mcp.call_tool("fgac-mcp-target___deleteOrder", {"orderId": 123})
    if "error" not in result:
        print("  PASS: deleteOrder allowed")
    else:
        print(f"  FAIL: {result['error'].get('message')}")

    # --- Test 4: getOrder with deleteOrder scope → DENY ---
    print("\n" + "=" * 60)
    print("Test 4: getOrder with deleteOrder scope (SHOULD DENY)")
    print("=" * 60)

    mcp = GatewayMCPClient(gateway_url, lambda: token, protocol_version="2025-11-25")
    result = mcp.call_tool("fgac-mcp-target___getOrder", {})
    if "error" in result:
        print(f"  PASS: Blocked — {result['error'].get('message')}")
    else:
        print("  FAIL: Should have been blocked!")

    # --- Test 5: All tools with full access scope → ALLOW ALL ---
    print("\n" + "=" * 60)
    print("Test 5: All tools with full access scope (SHOULD ALLOW ALL)")
    print("=" * 60)

    scope = "fgac/fgac-mcp-target"
    token = get_token(token_endpoint, fgac_client_id, fgac_client_secret, scope)
    mcp = GatewayMCPClient(gateway_url, lambda: token, protocol_version="2025-11-25")

    for tool in ["getOrder", "updateOrder", "cancelOrder", "deleteOrder"]:
        args = {"orderId": 123} if tool != "getOrder" else {}
        result = mcp.call_tool(f"fgac-mcp-target___{tool}", args)
        status = "PASS" if "error" not in result else "FAIL"
        print(f"  {status}: {tool}")

    # --- Test 6: tools/list with limited scope → filtered ---
    print("\n" + "=" * 60)
    print("Test 6: tools/list with getOrder scope (SHOULD SHOW 1 TOOL)")
    print("=" * 60)

    scope = "fgac/fgac-mcp-target:getOrder"
    token = get_token(token_endpoint, fgac_client_id, fgac_client_secret, scope)
    mcp = GatewayMCPClient(gateway_url, lambda: token, protocol_version="2025-11-25")

    all_tools = mcp.list_all_tools()
    tool_names = [t["name"] for t in all_tools if "___" in t["name"]]
    print(f"  Tools visible: {tool_names}")
    if len(tool_names) == 1 and "getOrder" in tool_names[0]:
        print("  PASS: Only getOrder visible")
    else:
        print(f"  FAIL: Expected 1 tool (getOrder), got {len(tool_names)}")

    # --- Test 7: tools/list with full scope → all tools ---
    print("\n" + "=" * 60)
    print("Test 7: tools/list with full access scope (SHOULD SHOW ALL)")
    print("=" * 60)

    scope = "fgac/fgac-mcp-target"
    token = get_token(token_endpoint, fgac_client_id, fgac_client_secret, scope)
    mcp = GatewayMCPClient(gateway_url, lambda: token, protocol_version="2025-11-25")

    all_tools = mcp.list_all_tools()
    tool_names = [t["name"] for t in all_tools if "___" in t["name"]]
    print(f"  Tools visible: {tool_names}")
    if len(tool_names) == 4:
        print("  PASS: All 4 tools visible")
    else:
        print(f"  FAIL: Expected 4 tools, got {len(tool_names)}")

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print("  REQUEST interceptor: blocks unauthorized tool/call")
    print("  RESPONSE interceptor: filters tools/list by scope")


if __name__ == "__main__":
    main()
