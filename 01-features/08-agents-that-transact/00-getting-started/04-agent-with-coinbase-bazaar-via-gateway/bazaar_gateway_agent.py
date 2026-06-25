"""
Integrate Your Agent with Coinbase Bazaar via AgentCore Gateway

The Coinbase x402 Bazaar is an MCP marketplace where paid tools are listed
with semantic descriptions, pricing, and input/output schemas. Agents discover
tools via search_resources and call them via proxy_tool_call — the Bazaar
handles 402 detection and payment routing.

Architecture:
    Developer Code
      Strands Agent
      + AgentCorePaymentsPlugin
      + MCPClient (streamable HTTP)
           │ MCP protocol
      AgentCore Gateway
      Target: Coinbase x402 Bazaar
           │
      Coinbase x402 Bazaar
      search_resources → discover
      proxy_tool_call  → call + pay
           │ HTTP 402 → pay → retry
      AgentCore payments
      ProcessPayment (sign + proof)

The key difference from Tutorial 01: the agent doesn't know which URLs to call.
It discovers tools at runtime via search_resources, then calls them via
proxy_tool_call. The payment infrastructure is the same.

Usage:
    python bazaar_gateway_agent.py

Prerequisites:
    - Tutorial 00 completed (.env exists with payment manager, instrument)
    - Wallet funded with testnet USDC from https://faucet.circle.com/
    - AgentCore Gateway created with Coinbase x402 Bazaar as a target
    - GATEWAY_URL set in .env (from Gateway creation)
    - pip install -r requirements.txt
"""

import os
import sys
from datetime import timedelta

import boto3
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import load_tutorial_env, print_summary

ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(ENV_FILE, override=True)

# ── Verify AWS credentials ────────────────────────────────────────────────────
session = boto3.Session()
identity = session.client("sts").get_caller_identity()
print(f"Authenticated as: {identity['Arn']}")
print(f"Account: {identity['Account']}")
print(f"Region: {session.region_name}")

# ── Step 1: Gateway Setup (manual) ───────────────────────────────────────────
print("""
── Step 1: Create AgentCore Gateway with Bazaar Target (manual) ──

Option A: AgentCore Console (recommended)
  1. Open https://console.aws.amazon.com/bedrock-agentcore/
  2. Navigate to Gateway → Create Gateway → Add Target
  3. Target type: Integrations
  4. Select: Coinbase x402 Bazaar
  5. No outbound auth needed

Option B: AgentCore CLI
  agentcore create --name BazaarAgent --defaults
  agentcore add gateway --name BazaarGateway
  agentcore add gateway-target \\
    --name CoinbaseBazaar \\
    --type mcp-server \\
    --endpoint https://api.cdp.coinbase.com/platform/v2/x402/discovery/mcp \\
    --gateway BazaarGateway
  agentcore deploy -y
  agentcore fetch access --name BazaarGateway --type gateway

Save the Gateway URL to .env:
  GATEWAY_URL=https://<gateway-id>.gateway.bedrock-agentcore.<region>.amazonaws.com/mcp
  (Optional, for CUSTOM_JWT auth: CLIENT_ID, CLIENT_SECRET, TOKEN_URL)
""")

# ── Step 2: Load Payment Config ───────────────────────────────────────────────
config = load_tutorial_env()
PAYMENT_MANAGER_ARN = config["payment_manager_arn"]
REGION = config["region"]
USER_ID = config["user_id"]

if config.get("multi_provider"):
    PROVIDER = list(config["instruments"].keys())[0]
    INSTRUMENT_ID = config["instruments"][PROVIDER]["instrument_id"]
else:
    INSTRUMENT_ID = config["instrument_id"]
    PROVIDER = config.get("provider_type", "unknown")

GATEWAY_URL = os.environ.get("GATEWAY_URL", "")
if not GATEWAY_URL:
    raise ValueError(
        "GATEWAY_URL not set in .env. Create the Gateway in Step 1 above, "
        "then add GATEWAY_URL=<your-gateway-url> to .env and re-run."
    )

from bedrock_agentcore.payments import PaymentManager  # noqa: E402

manager = PaymentManager(payment_manager_arn=PAYMENT_MANAGER_ARN, region_name=REGION)
instr = manager.get_payment_instrument(user_id=USER_ID, payment_instrument_id=INSTRUMENT_ID)
instr_status = instr.get("status", "UNKNOWN")
assert instr_status == "ACTIVE", f"Instrument is {instr_status} — fund and delegate in Tutorial 00/03 first"

print_summary(
    "Payment Config",
    manager_arn=PAYMENT_MANAGER_ARN,
    region=REGION,
    provider=PROVIDER,
    instrument_id=INSTRUMENT_ID,
    instrument_status=instr_status,
    gateway_url=GATEWAY_URL,
)

# ── Step 3: Create Payment Session ────────────────────────────────────────────
print("\n── Step 3: Create Payment Session ──")
sess_resp = manager.create_payment_session(
    user_id=USER_ID,
    limits={"maxSpendAmount": {"value": "1.00", "currency": "USD"}},
    expiry_time_in_minutes=60,
)
SESSION_ID = sess_resp["paymentSessionId"]
print(f"Session: {SESSION_ID} (budget: $1.00)")

# ── Step 4: Connect to Gateway and Create Agent ───────────────────────────────
print("\n── Step 4: Connect to Gateway and Create Agent ──")
from mcp.client.streamable_http import streamablehttp_client  # noqa: E402
from strands import Agent  # noqa: E402
from strands.models import BedrockModel  # noqa: E402
from strands.tools.mcp.mcp_client import MCPClient  # noqa: E402

from bedrock_agentcore.payments.integrations.strands import (  # noqa: E402
    AgentCorePaymentsPlugin,
    AgentCorePaymentsPluginConfig,
)

# Gateway auth — auto-detect from .env
gateway_headers = {}
CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
TOKEN_URL = os.environ.get("TOKEN_URL")

if CLIENT_ID and CLIENT_SECRET and TOKEN_URL:
    from utils import get_oauth_token

    token = get_oauth_token(TOKEN_URL, CLIENT_ID, CLIENT_SECRET)
    gateway_headers = {"Authorization": f"Bearer {token}"}
    print("Gateway auth: CUSTOM_JWT (OAuth token acquired)")
else:
    print("Gateway auth: NONE (no CLIENT_ID/CLIENT_SECRET/TOKEN_URL in .env)")

mcp_client = MCPClient(
    lambda: streamablehttp_client(
        GATEWAY_URL,
        headers=gateway_headers,
        timeout=timedelta(seconds=120),
    )
)

payment_plugin = AgentCorePaymentsPlugin(
    config=AgentCorePaymentsPluginConfig(
        payment_manager_arn=PAYMENT_MANAGER_ARN,
        user_id=USER_ID,
        payment_instrument_id=INSTRUMENT_ID,
        payment_session_id=SESSION_ID,
        region=REGION,
        network_preferences_config=["eip155:84532", "base-sepolia"],
    )
)

SYSTEM_PROMPT = """You are a research agent with access to the Coinbase x402 Bazaar — a marketplace of paid tools.

You can:
1. Use search_resources to discover available paid tools (filter by network, query, etc.)
2. Use proxy_tool_call to call a discovered tool — payment is handled automatically

When asked to find information:
- First search for relevant tools on the Bazaar
- Then call the most relevant tool
- Report what you found and what it cost

Always be transparent about payments."""

with mcp_client:
    tools = mcp_client.list_tools_sync()
    agent = Agent(
        model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-6", streaming=True),
        tools=tools,
        plugins=[payment_plugin],
        system_prompt=SYSTEM_PROMPT,
    )
    print(f"Agent created with {len(tools)} Bazaar tools + payment plugin")

    # ── Step 5a: Discover and Call a Paid Tool ───────────────────────────────
    print("\n── Step 5a: Discover and Call a Paid Tool ──")
    result = agent(
        "Search the Bazaar for paid data sources related to market news on Base Sepolia. "
        "Tell me what tools are available, their prices, and what data they provide. "
        "Then pick the most relevant one, call it, and summarize the results with the cost."
    )
    print(result.message)

    # ── Step 5b: Multi-Tool Discovery ────────────────────────────────────────
    print("\n── Step 5b: Multi-Tool Discovery — Compare Prices Across Categories ──")
    result = agent(
        "Search the Bazaar for three different categories of paid tools on Base Sepolia: "
        "1) market news, 2) weather data. "
        "For each category, list the available tools with their prices. "
        "Then tell me which tool in each category is the cheapest."
    )
    print(result.message)

    # ── Step 5c: Budget-Aware Tool Selection ─────────────────────────────────
    print("\n── Step 5c: Budget-Aware Tool Selection ──")
    mid_session = manager.get_payment_session(
        user_id=USER_ID,
        payment_session_id=SESSION_ID,
    )
    current = mid_session.get("availableLimits", {}).get("availableSpendAmount", {})
    print(f"Remaining budget: {current}")

    result = agent(
        f"My remaining budget is {current} out of a $1.00 budget. "
        "Search the Bazaar for tools under $0.10 on Base Sepolia. "
        "Pick the cheapest one and call it. "
        "If nothing is under $0.10, tell me what the cheapest option costs."
    )
    print(result.message)

    # ── Step 5d: Multiple Bazaar Calls in One Session ─────────────────────────
    print("\n── Step 5d: Multiple Bazaar Calls in One Session ──")
    result = agent(
        "I want a comprehensive research report. Do the following in order:\n"
        "1. Search the Bazaar for a market news tool and call it for the latest market updates\n"
        "2. Search for a weather data tool and call it for San Francisco weather\n"
        "After each call, note the cost. At the end, summarize all results "
        "and the total amount spent across all calls."
    )
    print(result.message)

# ── Step 6: Check Session Spend ──────────────────────────────────────────────
print("\n── Step 6: Check Session Spend ──")
session_info = manager.get_payment_session(
    user_id=USER_ID,
    payment_session_id=SESSION_ID,
)
available = session_info.get("availableLimits", {}).get("availableSpendAmount", {})
budget = session_info.get("limits", {}).get("maxSpendAmount", {})
try:
    spent = float(budget.get("value", 0)) - float(available.get("value", budget.get("value", 0)))
    spent_str = f"${spent:.4f} USD"
except (ValueError, TypeError):
    spent_str = "N/A"

print_summary(
    "Session After Bazaar Calls",
    session_id=SESSION_ID,
    budget_limit=f"${budget.get('value', 'N/A')} {budget.get('currency', '')}",
    remaining=f"${available.get('value', 'N/A')} {available.get('currency', '')}",
    spent=spent_str,
)

print(
    f"\nView traces: https://{REGION}.console.aws.amazon.com/cloudwatch/home?"
    f"region={REGION}#gen-ai-observability/agent-core"
)
print("\nDone. Sessions expire automatically.")
print("Next: python ../05-agent-with-browser-tool-pay-for-content/browser_paywall_payments.py")
