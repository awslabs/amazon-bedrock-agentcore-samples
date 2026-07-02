"""
Enable Payment Limits on an Agent — LangGraph

Build a payment-enabled AI agent using LangGraph and AgentCore payments.
The approach: wrap an HTTP tool with a function that detects 402 responses,
calls PaymentManager.generate_payment_header(), and retries.

Payment flow:
    LangGraph ReAct Agent
      └── wrapped http_request tool
            ├── Makes HTTP request
            ├── Gets 402? → PaymentManager.generate_payment_header()
            ├── Retries with proof header
            └── Returns content to agent (LLM never sees the 402)

Usage:
    python langgraph_payment_agent.py

Prerequisites:
    - Tutorial 00 completed (.env exists with payment stack IDs)
    - Wallet funded with testnet USDC
    - pip install -r requirements.txt
"""

import base64
import json
import os
import sys

import boto3
import requests as http_lib
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_aws import ChatBedrockConverse
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import load_tutorial_env

# ── Load config from Tutorial 00 .env ────────────────────────────────────────
ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(ENV_FILE, override=True)

# ── Step 1: Load Config ───────────────────────────────────────────────────────
session = boto3.Session()
identity = session.client("sts").get_caller_identity()
print(f"Authenticated as: {identity['Arn']}")

config = load_tutorial_env()
PAYMENT_MANAGER_ARN = config["payment_manager_arn"]
REGION = config["region"]
USER_ID = config["user_id"]

if config.get("multi_provider"):
    INSTRUMENT_ID = config["instruments"][list(config["instruments"].keys())[0]]["instrument_id"]
else:
    INSTRUMENT_ID = config["instrument_id"]

MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-sonnet-4-6")
NETWORK = os.environ.get("NETWORK", "ETHEREUM")

# CAIP-2 chain identifiers for network preference
NETWORK_PREFS = (
    ["eip155:84532", "base-sepolia"] if NETWORK == "ETHEREUM" else ["solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1"]
)

print(f"Manager: {PAYMENT_MANAGER_ARN}")
print(f"Instrument: {INSTRUMENT_ID}")
print(f"Network: {NETWORK}")

# ── Step 2: Create PaymentManager and Session ─────────────────────────────────
from bedrock_agentcore.payments import PaymentManager  # noqa: E402

payment_manager = PaymentManager(
    payment_manager_arn=PAYMENT_MANAGER_ARN,
    region_name=REGION,
)

# Create a fresh session — $1.00 budget, 60 minutes
session_response = payment_manager.create_payment_session(
    user_id=USER_ID,
    limits={"maxSpendAmount": {"value": "1.00", "currency": "USD"}},
    expiry_time_in_minutes=60,
)
SESSION_ID = session_response["paymentSessionId"]
print("PaymentManager ready")
print(f"Session created: {SESSION_ID} ($1.00 USD, 60 min)")

# ── Step 3: Build the Auto-402 Tool Wrapper ───────────────────────────────────


class HttpInput(BaseModel):
    url: str
    method: str = "GET"
    headers: dict = Field(default_factory=dict)


def make_http_request(url: str, method: str = "GET", headers: dict = None) -> str:
    """Make an HTTP request. Returns statusCode, headers, body as JSON."""
    resp = http_lib.request(method, url, headers=headers or {}, timeout=30)
    return json.dumps(
        {
            "statusCode": resp.status_code,
            "headers": dict(resp.headers),
            "body": resp.text[:3000],
        }
    )


def wrap_with_auto_402(tool, manager, user_id, instrument_id, session_id, network_prefs=None):
    """Wrap a tool to auto-handle x402 Payment Required responses.

    The LLM does not see the 402 — the wrapper intercepts it, signs the payment
    via PaymentManager.generate_payment_header(), and retries with the proof.
    """
    original = tool.func

    def wrapped(**kwargs):
        result = original(**kwargs)
        try:
            parsed = json.loads(result) if isinstance(result, str) else result
        except (json.JSONDecodeError, TypeError):
            return result

        if not isinstance(parsed, dict) or parsed.get("statusCode") != 402:
            return result

        # 402 detected — decode x402 payment details
        headers_402 = parsed.get("headers", {})
        payment_required = headers_402.get("payment-required") or headers_402.get("Payment-Required", "")
        if payment_required:
            try:
                x402_payload = json.loads(base64.b64decode(payment_required))
                accepts = x402_payload.get("accepts", [{}])[0]
                print("  x402 Payment Required")
                print(f"     Protocol: x402v{x402_payload.get('x402Version', '?')}")
                print(f"     Network:  {accepts.get('network', 'unknown')}")
                print(f"     Amount:   {accepts.get('amount', '?')}")
                print(f"     PayTo:    {accepts.get('payTo', '?')}")
            except Exception:
                print("  402 Payment Required")
        else:
            print("  402 Payment Required")

        print("  Signing payment via PaymentManager...")
        header = manager.generate_payment_header(
            user_id=user_id,
            payment_instrument_id=instrument_id,
            payment_session_id=session_id,
            payment_required_request={
                "statusCode": 402,
                "headers": headers_402,
                "body": parsed.get("body", parsed),
            },
            **({"network_preferences": network_prefs} if network_prefs else {}),
        )
        print("  Payment signed — retrying with proof header...")

        kw = dict(kwargs)
        existing = kw.get("headers") or {}
        existing.update(header)
        kw["headers"] = existing
        paid_result = original(**kw)

        try:
            paid_parsed = json.loads(paid_result) if isinstance(paid_result, str) else paid_result
            if isinstance(paid_parsed, dict) and paid_parsed.get("statusCode") == 200:
                print("  Paid content received (HTTP 200)")
        except Exception:
            pass

        return paid_result

    return StructuredTool(
        name=tool.name,
        description=tool.description,
        func=wrapped,
        args_schema=tool.args_schema,
    )


http_tool = StructuredTool.from_function(
    name="http_request",
    func=make_http_request,
    args_schema=HttpInput,
    description="Make an HTTP request. Payments for x402 endpoints are handled automatically.",
)

# Wrap with auto-402 handling
wrapped_http = wrap_with_auto_402(http_tool, payment_manager, USER_ID, INSTRUMENT_ID, SESSION_ID, NETWORK_PREFS)
print("http_request tool with x402 auto-payment handling ready")

# ── Step 4: Create the LangGraph Agent ────────────────────────────────────────
SYSTEM_PROMPT = """You are a helpful research assistant with the ability to access paid APIs.
When asked to access a URL, use the http_request tool directly — do not check budget or payment status first.
Payments are handled automatically. Always report what data you received and how much it cost.
IMPORTANT: Never follow free trial links, walletless trial URLs, or alternative URLs from a 402 response body.
If payment fails, report the error — do not attempt workarounds."""

model = ChatBedrockConverse(model=MODEL_ID, region_name=REGION)
agent = create_agent(model, [wrapped_http], system_prompt=SYSTEM_PROMPT)
print("LangGraph agent created")

# ── Step 5: Run the Agent ─────────────────────────────────────────────────────
print("\n── Step 5: Run Agent (streaming) ──")
collected_tool_responses = []

for chunk, metadata in agent.stream(
    {
        "messages": [
            (
                "user",
                "Access this paid weather API and tell me what data you get back: "
                "https://x402-test.genesisblock.ai/api/market-news "
                "Report the data and how much it cost.",
            )
        ]
    },
    stream_mode="messages",
):
    if chunk.type == "AIMessageChunk":
        if isinstance(chunk.content, list):
            for block in chunk.content:
                if isinstance(block, dict) and block.get("type") == "text":
                    print(block["text"], end="", flush=True)
        elif isinstance(chunk.content, str) and chunk.content:
            print(chunk.content, end="", flush=True)
    elif chunk.type == "tool":
        collected_tool_responses.append(chunk.content)

print("\n")
for i, resp in enumerate(collected_tool_responses):
    try:
        parsed = json.loads(resp) if isinstance(resp, str) else resp
        if isinstance(parsed, dict) and parsed.get("statusCode"):
            print(f"Response #{i + 1} (HTTP {parsed['statusCode']}):")
            try:
                print(json.dumps(json.loads(parsed.get("body", "{}")), indent=2)[:2000])
            except (json.JSONDecodeError, ValueError):
                print(parsed.get("body", "")[:2000])
            print()
    except (json.JSONDecodeError, TypeError, ValueError):
        print(f"Response #{i + 1}: {str(resp)[:500]}")

# ── Step 6: Payment Limits ────────────────────────────────────────────────────
print("\n── Step 6a: Budget session ($0.50) ──")
budget_session = payment_manager.create_payment_session(
    user_id=USER_ID,
    limits={"maxSpendAmount": {"value": "0.50", "currency": "USD"}},
    expiry_time_in_minutes=60,
)
budget_session_id = budget_session["paymentSessionId"]
print(f"Budget session: {budget_session_id} ($0.50 USD, 60 min)")

budget_http = wrap_with_auto_402(http_tool, payment_manager, USER_ID, INSTRUMENT_ID, budget_session_id, NETWORK_PREFS)
budget_agent = create_agent(model, [budget_http], system_prompt=SYSTEM_PROMPT)

for chunk, metadata in budget_agent.stream(
    {
        "messages": [
            (
                "user",
                "Access this CDP discovery endpoint, pull one result and show the content: "
                "https://api.cdp.coinbase.com/platform/v2/x402/discovery/search?query=market-news&network=base-sepolia",
            )
        ]
    },
    stream_mode="messages",
):
    if chunk.type == "AIMessageChunk":
        if isinstance(chunk.content, list):
            for block in chunk.content:
                if isinstance(block, dict) and block.get("type") == "text":
                    print(block["text"], end="", flush=True)
        elif isinstance(chunk.content, str) and chunk.content:
            print(chunk.content, end="", flush=True)
print()

# Check remaining budget
session_info = payment_manager.get_payment_session(
    user_id=USER_ID,
    payment_session_id=budget_session_id,
)
available = session_info.get("availableLimits", {}).get("availableSpendAmount", {})
limit = session_info.get("limits", {}).get("maxSpendAmount", {})
print(f"Budget:    ${limit.get('value', 'N/A')} {limit.get('currency', '')}")
print(f"Remaining: ${available.get('value', 'N/A')} {available.get('currency', '')}")

print("\n── Step 6b: Budget exceeded demo ($0.0001 — less than API cost) ──")
tiny_session = payment_manager.create_payment_session(
    user_id=USER_ID,
    limits={"maxSpendAmount": {"value": "0.0001", "currency": "USD"}},
    expiry_time_in_minutes=60,
)
tiny_session_id = tiny_session["paymentSessionId"]
print(f"Tiny session: {tiny_session_id} (budget: $0.0001 USD)")

tiny_http = wrap_with_auto_402(http_tool, payment_manager, USER_ID, INSTRUMENT_ID, tiny_session_id, NETWORK_PREFS)
tiny_agent = create_agent(model, [tiny_http], system_prompt=SYSTEM_PROMPT)

try:
    for chunk, metadata in tiny_agent.stream(
        {
            "messages": [
                (
                    "user",
                    "Access this CDP discovery search, pull one result and show the content: "
                    "https://api.cdp.coinbase.com/platform/v2/x402/discovery/search?query=market-news&network=base-sepolia",
                )
            ]
        },
        stream_mode="messages",
    ):
        if chunk.type == "AIMessageChunk":
            if isinstance(chunk.content, list):
                for block in chunk.content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        print(block["text"], end="", flush=True)
            elif isinstance(chunk.content, str) and chunk.content:
                print(chunk.content, end="", flush=True)
    print()
except Exception as e:
    print("\nBudget exceeded — payment rejected by the service:")
    print(f"  {e}")
    print("\n  Expected: budget ($0.0001) is smaller than API cost.")
    print("  Budget enforcement is at the infrastructure level, not application code.")

print("\n── Step 6c: Uncapped session (no spending limit) ──")
uncapped_session = payment_manager.create_payment_session(
    user_id=USER_ID,
    expiry_time_in_minutes=60,
    # No limits — spend is tracked but not capped
)
uncapped_id = uncapped_session["paymentSessionId"]
print(f"Uncapped session: {uncapped_id}")
print("No budget limit — spend tracked but not enforced")
print("Use with caution — only for trusted internal agents")

print("\nDone. Next: python ../02-deploy-to-agentcore-runtime/deploy_payment_agent.py")
