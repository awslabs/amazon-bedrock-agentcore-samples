#!/usr/bin/env python3
"""
Gateway smoke test — connects to the Amazon Bedrock AgentCore Gateway and exercises MCP tools directly.

Usage:
  python test/test_gateway.py --persona hr-manager --query "Find all engineers"
  python test/test_gateway.py --persona employee --list-tools
"""

import argparse
import base64
import json
import sys
import uuid

import boto3
import requests

sys.path.insert(0, ".")
from scripts.utils import get_ssm_parameter


def get_token(persona: str) -> str:
    client_id = get_ssm_parameter(f"/app/hrdlp/personas/{persona}/client-id")
    client_secret = get_ssm_parameter(f"/app/hrdlp/personas/{persona}/client-secret")
    token_url = get_ssm_parameter("/app/hrdlp/cognito-token-url")

    if not all([client_id, client_secret, token_url]):
        print(f"ERROR: Credentials not found for persona '{persona}'. Run prereq.sh first.")
        sys.exit(1)

    resp = requests.post(
        token_url,
        data={"grant_type": "client_credentials"},
        auth=(client_id, client_secret),
        timeout=15,
    )
    resp.raise_for_status()
    token = resp.json()["access_token"]
    print(f"[auth] Token acquired for persona: {persona}")
    return token


def call_gateway(gateway_url: str, token: str, method: str, params: dict = None) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "id": uuid.uuid4().hex,
        "method": method,
        "params": params or {},
    }
    resp = requests.post(
        gateway_url,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def list_tools(gateway_url: str, token: str) -> None:
    print("\n[gateway] Listing available tools...")
    result = call_gateway(gateway_url, token, "tools/list")
    tools = result.get("result", {}).get("tools", [])
    if not tools:
        print("  No tools visible for this persona (check scopes).")
    else:
        for t in tools:
            print(f"  ✓ {t['name']}")
    print(f"  Total: {len(tools)} tools")


def call_tool(gateway_url: str, token: str, tool_name: str, arguments: dict) -> None:
    print(f"\n[gateway] Calling tool: {tool_name}")
    result = call_gateway(gateway_url, token, "tools/call", {"name": tool_name, "arguments": arguments})
    content = result.get("result", {}).get("content", [])
    for item in content:
        if item.get("type") == "text":
            try:
                data = json.loads(item["text"])
                body = json.loads(data.get("body", "{}"))
                print(json.dumps(body, indent=2))
            except Exception:
                print(item["text"])


def main():
    parser = argparse.ArgumentParser(description="AgentCore Gateway smoke test")
    parser.add_argument("--persona", default="hr-manager",
                        choices=["hr-manager", "hr-specialist", "employee", "admin"],
                        help="Test persona to use")
    parser.add_argument("--query", default="John Smith", help="Search query")
    parser.add_argument("--list-tools", action="store_true", help="Only list tools, no invocation")
    args = parser.parse_args()

    gateway_url = get_ssm_parameter("/app/hrdlp/gateway-url")
    if not gateway_url:
        print("ERROR: Gateway URL not found in SSM (/app/hrdlp/gateway-url)")
        sys.exit(1)

    token = get_token(args.persona)
    list_tools(gateway_url, token)

    if not args.list_tools:
        call_tool(
            gateway_url, token,
            "hr-lambda-target___search_employee",
            {"query": args.query},
        )


if __name__ == "__main__":
    main()
