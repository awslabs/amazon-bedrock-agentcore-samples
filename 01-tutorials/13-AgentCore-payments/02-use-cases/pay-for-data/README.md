# Pay for Data — Heurist Finance Agent

> **Caution:** This sample is provided for experimental and educational purposes only. It is not intended for direct use in production environments.

## Overview

A finance research agent that pays for real-time market data using **Amazon Bedrock AgentCore payments**. The agent fetches live prices, SEC filings, and macro indicators from [Heurist](https://heurist.xyz), analyzes the data with AgentCore Code Interpreter, and exports charts and reports.

Heurist endpoints use the [x402 protocol](https://x402.org) — they return HTTP 402 until a valid payment proof is attached. The `AgentCorePaymentsPlugin` drives payment processing end-to-end: it intercepts 402 responses, asks the AgentCore payment manager to generate a payment proof against your payment instrument, attaches it, and retries the request. Tool code stays an ordinary `http_request` call.

```
User prompt → Strands Agent (Claude on Bedrock)
  → http_request to Heurist endpoint
    → 402 → AgentCorePaymentsPlugin → payment proof → retry → 200
  → Code Interpreter (pandas + matplotlib)
  → Artifact export
```

## How It Works

See [`agent.py`](heurist_finance_agent/agent.py) for the full implementation. The relevant setup:

```python
from bedrock_agentcore.payments.integrations.strands import (
    AgentCorePaymentsPlugin,
    AgentCorePaymentsPluginConfig,
)

payment_plugin = AgentCorePaymentsPlugin(
    config=AgentCorePaymentsPluginConfig(
        payment_manager_arn=PAYMENT_MANAGER_ARN,
        user_id=USER_ID,
        payment_instrument_id=PAYMENT_INSTRUMENT_ID,
        payment_session_id=PAYMENT_SESSION_ID,
        region="us-west-2",
    )
)

agent = Agent(
    model=BedrockModel(model_id=MODEL_ID),
    tools=[http_request, code_interpreter, ...],
    plugins=[payment_plugin],
)
```

## Sample Details

| | |
|---|---|
| AgentCore components | AgentCore payments, AgentCore Code Interpreter |
| Agent framework | [Strands Agents](https://strandsagents.com/) |
| Model | Claude Sonnet 4 on Amazon Bedrock (configurable) |
| Payment protocol | [x402](https://x402.org) |
| Payment network | Base (USDC) |

## Data Sources

Fetched at runtime from the [Heurist mesh registry](https://mesh.heurist.xyz/x402/agents?details=true). By default the sample loads tools from four agents:

| Agent | Representative tools | Typical price |
|-------|----------------------|---------------|
| `YahooFinanceAgent` | `price_history`, `quote_snapshot`, `futures_snapshot` | $0.002 |
| `FredMacroAgent` | `macro_series_snapshot`, `macro_regime_context` | $0.003 |
| `SecEdgarAgent` | `filing_timeline`, `filing_diff`, `xbrl_fact_trends` | $0.002 |
| `ExaSearchDigestAgent` | `exa_web_search`, `exa_scrape_url` | $0.005 |

Override with the `HEURIST_AGENT_IDS` environment variable.

## Prerequisites

- Completed the setup tutorial under [`00-getting-started/`](../../00-getting-started/):
  - AgentCore payment manager created
  - Payment instrument created and funded (embedded crypto wallet, USDC on Base)
  - Payment session created (with your desired payment limits)
- Python 3.11+
- AWS credentials with Bedrock and AgentCore access in `us-west-2`

## Layout

```
pay-for-data/
├── README.md
├── requirements.txt
├── .env.example
├── pay-for-data.ipynb                # notebook entry point
└── heurist_finance_agent/
    ├── agent.py                      # agent definition + plugin config
    ├── catalog.py                    # fetches Heurist registry, formats for system prompt
    ├── config.py                     # loads .env
    ├── artifact_export.py            # pulls files from Code Interpreter to local disk
    ├── artifacts/                    # output directory
    └── scripts/
        ├── run.py                    # CLI: python -m heurist_finance_agent.scripts.run
        └── sync_registry.py          # CLI: refreshes cached Heurist catalog
```

## Installation

```bash
cd 01-tutorials/13-AgentCore-payments/02-use-cases/pay-for-data

# Create a virtual environment
python -m venv .venv && source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure credentials
cp .env.example .env
# Edit .env — see Environment Variables below
```

## Quick Start

Open [`pay-for-data.ipynb`](pay-for-data.ipynb) and run the cells in order — that's the main walkthrough.

If you prefer the command line:

```bash
# Sync the Heurist tool catalog (one-time, cached on disk)
python -m heurist_finance_agent.scripts.sync_registry

# Run the agent (default prompt: US macro summary via FredMacroAgent)
python -m heurist_finance_agent.scripts.run

# Or with a custom prompt
python -m heurist_finance_agent.scripts.run "What are the current US inflation and interest rate trends?"
```

Outputs land in `heurist_finance_agent/artifacts/`.

## Payment Flow

When the agent calls a paid Heurist endpoint:

1. `http_request` sends a POST to the endpoint URL.
2. Heurist returns HTTP 402 with x402 payment terms (network, asset, amount, recipient).
3. `AgentCorePaymentsPlugin` intercepts the response.
4. The plugin asks the AgentCore payment manager to generate a payment proof for those terms.
5. The payment manager uses the configured payment connection and payment instrument to sign a USDC transfer, and returns a payment proof.
6. The plugin attaches the proof as an `X-PAYMENT` header and retries the request.
7. Heurist validates the proof, settles on-chain, and returns the data.

The plugin retries up to 3 times per tool call. If payment processing fails (e.g., insufficient balance, payment limits exceeded), it raises an interrupt the agent can surface to the user.

## Environment Variables

See [`.env.example`](.env.example). Required:

| Variable | Description |
|----------|-------------|
| `PAYMENT_MANAGER_ARN` | ARN of the AgentCore payment manager |
| `PAYMENT_SESSION_ID` | ID of an active payment session |
| `PAYMENT_INSTRUMENT_ID` | ID of a funded payment instrument (embedded crypto wallet) |
| `USER_ID` | User identifier for payment tracking |
| `BEDROCK_MODEL_ID` | Bedrock model (default: Claude Sonnet 4) |
| `HEURIST_AGENT_IDS` | Comma-separated Heurist agents to load |

## Notes

- Payment sessions expire. Create a fresh payment session before long runs.
- Each paid call settles USDC on Base. Ensure your payment instrument is funded.
- Payment limits are enforced at the payment session scope (`maxSpendAmount`). See the tutorials for configuring them.
- The agent's system prompt includes the full endpoint catalog (URLs, parameters, prices) so it knows what to call via `http_request`.