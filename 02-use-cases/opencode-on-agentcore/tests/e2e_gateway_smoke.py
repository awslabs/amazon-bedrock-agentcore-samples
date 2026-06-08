#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""E2E smoke tests against the live OpenCode Gateway."""
import asyncio
import json
import os
import subprocess
import sys

GATEWAY_URL = os.environ["OPENCODE_GATEWAY_URL"]
CLIENT_ID = os.environ["COGNITO_CLIENT_ID"]
USER = os.environ["COGNITO_USER"]
PASSWORD = os.environ["COGNITO_PASSWORD"]
REGION = os.environ.get("AWS_REGION", "us-east-1")

def get_token():
    r = subprocess.run([
        "aws", "cognito-idp", "initiate-auth",
        "--auth-flow", "USER_PASSWORD_AUTH",
        "--client-id", CLIENT_ID,
        "--auth-parameters", f"USERNAME={USER},PASSWORD={PASSWORD}",
        "--region", REGION,
        "--query", "AuthenticationResult.IdToken",
        "--output", "text",
    ], capture_output=True, text=True)
    token = r.stdout.strip()
    if not token or token == "None":
        print(f"AUTH FAILED: {r.stderr}", file=sys.stderr)
        sys.exit(1)
    return token

async def run_tests():
    import httpx
    token = get_token()
    print("1. Cognito auth: PASS")

    client = httpx.AsyncClient(timeout=30)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    # Test: initialize
    resp = await client.post(GATEWAY_URL, json={
        "jsonrpc": "2.0", "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "0.1.0"},
    }, headers=headers)
    data = resp.json()
    assert data["result"]["serverInfo"]["name"] == "opencode-gateway", f"Unexpected: {data}"
    print("2. MCP initialize: PASS")

    # Test: tools/list
    resp = await client.post(GATEWAY_URL, json={
        "jsonrpc": "2.0", "id": 2,
        "method": "tools/list", "params": {},
    }, headers=headers)
    data = resp.json()
    tools = data.get("result", {}).get("tools", [])
    names = [t["name"] for t in tools]
    print(f"3. tools/list: PASS ({len(tools)} tools: {names})")

    # Test: unknown method returns error
    resp = await client.post(GATEWAY_URL, json={
        "jsonrpc": "2.0", "id": 3,
        "method": "nonexistent_method", "params": {},
    }, headers=headers)
    data = resp.json()
    assert "error" in data, f"Expected error: {data}"
    print("4. Unknown method → error: PASS")

    # Test: unauthenticated request rejected
    resp = await client.post(GATEWAY_URL, json={
        "jsonrpc": "2.0", "id": 4,
        "method": "initialize", "params": {},
    }, headers={"Content-Type": "application/json"})
    assert resp.status_code in (401, 403) or "error" in resp.json()
    print(f"5. No-auth rejected (HTTP {resp.status_code}): PASS")

    await client.aclose()
    print("\nAll e2e smoke tests passed.")

asyncio.run(run_tests())
