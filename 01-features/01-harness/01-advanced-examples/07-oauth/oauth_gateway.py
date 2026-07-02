"""
AgentCore Harness with JWT Inbound Auth & OAuth-Protected Gateway.

Demonstrates two Harness security primitives:

  Inbound auth (CUSTOM_JWT) — require callers to present a valid JWT before
  the Harness accepts the request. Uses a Cognito user pool (any OIDC provider works).

  Outbound auth (outboundAuth.oauth) — the Harness automatically fetches an
  OAuth token (client credentials grant) to authenticate to an AgentCore Gateway.
  The credential provider is registered once; the Harness handles token exchange
  on every tool call. No secrets in the invoke request.

Architecture:

  User → [User Pool JWT] → Harness → validates JWT (inbound auth)
                                   → fetches M2M token (outbound auth)
                                   → calls Gateway with M2M token
                                   → Gateway validates M2M token
                                   → invokes Lambda tool
                                   → response flows back to user

Usage:
    # Set credentials via environment variables
    export HARNESS_USER_NAME="testuser"
    export HARNESS_USER_PASS="TestPassword123!"
    python oauth_gateway.py

    # Skip cleanup to inspect resources
    python oauth_gateway.py --skip-cleanup

Prerequisites:
    - AWS CLI configured with credentials
    - pip install -r ../../requirements.txt
    - AWS_DEFAULT_REGION environment variable set
    - HARNESS_USER_NAME environment variable (Cognito test user name)
    - HARNESS_USER_PASS environment variable (Cognito test user password, min 8 chars)
"""

import json
import os
import re
import sys
import time
import urllib.parse
import argparse
from pathlib import Path

import boto3
import requests as http_requests

sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # root utils
sys.path.insert(0, str(Path(__file__).parent))  # local utils/

from utils.setup_helpers import (
    create_user_auth_pool,
    create_m2m_pool,
    create_credential_provider,
    deploy_lambda,
    create_gateway_with_lambda_target,
    create_harness_execution_role,
    cleanup_all,
)

# ── CLI ────────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Harness JWT inbound + OAuth outbound demo")
parser.add_argument("--skip-cleanup", action="store_true", help="Keep all resources after the demo")
args = parser.parse_args()

# ── Configuration ─────────────────────────────────────────────────────────────
REGION = boto3.session.Session().region_name or "us-east-1"
ACCOUNT_ID = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
PREFIX = "harness-oauth-demo"

# Credentials for the test Cognito user
USER1_NAME = os.environ.get("HARNESS_USER_NAME")
USER1_PASS = os.environ.get("HARNESS_USER_PASS")

if not USER1_NAME or not USER1_PASS:
    raise ValueError(
        "Set HARNESS_USER_NAME and HARNESS_USER_PASS environment variables.\n"
        "Example:\n"
        "  export HARNESS_USER_NAME='testuser'\n"
        "  export HARNESS_USER_PASS='TestPassword123!'"
    )

ac_control = boto3.client("bedrock-agentcore-control", region_name=REGION)
cognito = boto3.client("cognito-idp", region_name=REGION)

print(f"Region: {REGION}  Account: {ACCOUNT_ID}")

# ── Step 1: Provision Infrastructure ─────────────────────────────────────────
print("\n=== Step 1a: Cognito User Auth Pool ===")
pool1 = create_user_auth_pool(REGION, PREFIX, USER1_NAME, USER1_PASS)
print(f"Discovery URL: {pool1['discovery_url']}")

print("\n=== Step 1b: Cognito M2M Pool ===")
pool2 = create_m2m_pool(REGION, PREFIX)
print(f"Scope: {pool2['scope']}")
print(f"Discovery URL: {pool2['discovery_url']}")

print("\n=== Step 1c: OAuth2 Credential Provider ===")
cred = create_credential_provider(
    REGION,
    PREFIX,
    discovery_url=pool2["discovery_url"],
    client_id=pool2["client_id"],
    client_secret=pool2["client_secret"],
)

print("\n=== Step 1d: Lambda Function ===")
lam = deploy_lambda(REGION, PREFIX)

print("\n=== Step 1e: Gateway + Lambda Target ===")
gw = create_gateway_with_lambda_target(
    REGION,
    PREFIX,
    ACCOUNT_ID,
    discovery_url=pool2["discovery_url"],
    allowed_client=pool2["client_id"],
    allowed_scope=pool2["scope"],
    lambda_arn=lam["function_arn"],
    lambda_function_name=lam["function_name"],
)
print(f"Gateway ARN: {gw['gateway_arn']}")

print("\n=== Step 1f: Harness Execution Role ===")
harness_role = create_harness_execution_role(REGION, PREFIX, ACCOUNT_ID)

# ── Step 2: Create Harness with CUSTOM_JWT Inbound Auth ──────────────────────
print("\n=== Step 2: Create Harness with CUSTOM_JWT Inbound Auth ===")
HARNESS_NAME = f"{PREFIX}-harness".replace("-", "_")

try:
    harness_resp = ac_control.create_harness(
        harnessName=HARNESS_NAME,
        executionRoleArn=harness_role["role_arn"],
        authorizerConfiguration={
            "customJWTAuthorizer": {
                "discoveryUrl": pool1["discovery_url"],
                "allowedClients": [pool1["client_id"]],
            }
        },
        model={"bedrockModelConfig": {"modelId": "us.anthropic.claude-haiku-4-5-20251001-v1:0"}},
        systemPrompt=[
            {
                "text": (
                    "You are an order management assistant. "
                    "Use the gateway tools to look up and update orders. "
                    "Always confirm the order details before making changes."
                )
            }
        ],
        tools=[
            {
                "type": "agentcore_gateway",
                "name": "order-gateway",
                "config": {
                    "agentCoreGateway": {
                        "gatewayArn": gw["gateway_arn"],
                        "outboundAuth": {
                            "oauth": {
                                "providerArn": cred["arn"],
                                "scopes": [pool2["scope"]],
                                "grantType": "CLIENT_CREDENTIALS",
                            }
                        },
                    }
                },
            }
        ],
    )
    HARNESS_ID = harness_resp["harness"]["harnessId"]
    HARNESS_ARN = harness_resp["harness"]["arn"]
    print(f"Harness created: {HARNESS_ID}")
except ac_control.exceptions.ConflictException:
    HARNESS_ID = None
    for h in ac_control.list_harnesses().get("harnesses", []):
        if h.get("harnessName") == HARNESS_NAME:
            HARNESS_ID = h["harnessId"]
            HARNESS_ARN = h["arn"]
            break
    if not HARNESS_ID:
        raise RuntimeError(f"Harness {HARNESS_NAME} conflict but not found")
    print(f"Harness already exists: {HARNESS_ID}")

print(f"Harness ID:  {HARNESS_ID}")
print(f"Harness ARN: {HARNESS_ARN}")

print("Waiting for harness READY...")
for _ in range(30):
    h_status = ac_control.get_harness(harnessId=HARNESS_ID)["harness"]["status"]
    print(f"  {h_status}")
    if h_status == "READY":
        break
    time.sleep(10)
print(f"Harness status: {h_status}")

# ── Step 3: Get Bearer Token from User Auth Pool ──────────────────────────────
print("\n=== Step 3: Authenticate User — Get Bearer Token ===")
auth_result = cognito.initiate_auth(
    ClientId=pool1["client_id"],
    AuthFlow="USER_PASSWORD_AUTH",
    AuthParameters={"USERNAME": USER1_NAME, "PASSWORD": USER1_PASS},
)
BEARER_TOKEN = auth_result["AuthenticationResult"]["AccessToken"]
print(f"Got bearer token (first 20 chars): {BEARER_TOKEN[:20]}...")

# ── Step 4: Invoke Harness with Bearer Token ─────────────────────────────────
print("\n=== Step 4: Invoke Harness with Bearer Token ===")
import uuid  # noqa: E402

escaped_arn = urllib.parse.quote(HARNESS_ARN, safe="")
url = f"https://bedrock-agentcore.{REGION}.amazonaws.com/harnesses/invoke?harnessArn={escaped_arn}"
SESSION_ID = f"demo-session-{uuid.uuid4().hex}"

headers = {
    "Authorization": f"Bearer {BEARER_TOKEN}",
    "Content-Type": "application/json",
    "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": SESSION_ID,
}
payload = {
    "messages": [
        {
            "role": "user",
            "content": [{"text": "Look up order ORD-001 and tell me its status."}],
        }
    ]
}

print(f"Session:  {SESSION_ID}")
print(f"Endpoint: {url[:80]}...")
print()

resp = http_requests.post(url, headers=headers, json=payload, timeout=120, stream=True)
print(f"HTTP Status: {resp.status_code}")

if resp.status_code == 200:
    full_text = []
    raw = resp.content
    # Extract JSON objects from the binary event-stream
    json_objects = re.findall(rb"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", raw)
    for obj_bytes in json_objects:
        try:
            obj = json.loads(obj_bytes.decode("utf-8", errors="ignore"))
            delta = obj.get("delta", {})
            if "text" in delta:
                full_text.append(delta["text"])
                print(delta["text"], end="", flush=True)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
    print()
    if full_text:
        print(f"\n--- Full response ({len(''.join(full_text))} chars) ---")
        print("".join(full_text))
    else:
        print("\n(No text deltas found in stream)")
        print(f"Raw first 500 bytes: {repr(raw[:500])}")
else:
    print(f"Error {resp.status_code}: {resp.text[:1000]}")

print("\n=== What just happened? ===")
print("1. You sent a User Auth Pool JWT → harness validated it (inbound auth)")
print("2. Agent decided to call get_order → harness fetched an M2M token from M2M Pool")
print("3. Harness called the Gateway with the M2M token (outbound auth)")
print("4. Gateway validated it, invoked Lambda, order details flowed back")
print("Three auth mechanisms, zero secrets in the invoke call.")

# ── Step 5: Cleanup ───────────────────────────────────────────────────────────
if not args.skip_cleanup:
    print("\n=== Step 5: Cleanup ===")
    cleanup_all(REGION, PREFIX)
else:
    print("\n=== Skipping cleanup (--skip-cleanup) ===")
    print(f"Harness ID:  {HARNESS_ID}")
    print(f"Gateway ARN: {gw['gateway_arn']}")
    print("Run 'python oauth_gateway.py' again to reuse existing resources.")
