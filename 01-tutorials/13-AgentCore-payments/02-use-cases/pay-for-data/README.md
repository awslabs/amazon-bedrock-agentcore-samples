# Pay for Data — Heurist Finance Agent

## Overview

A finance research agent that pays for real-time market data using **Amazon Bedrock AgentCore payments**. The agent calls paid [Heurist](https://heurist.xyz) endpoints for live prices, SEC filings, and macro indicators, analyzes the data with AgentCore Code Interpreter, and returns charts and reports as S3 presigned URLs — all without any manual payment code in the tools.

The agent is deployed to **AgentCore Runtime**: a managed container endpoint with HTTPS invocation, SigV4 auth, and automatic observability via CloudWatch.

Heurist endpoints use the [x402 protocol](https://x402.org) — they return HTTP 402 until a valid payment proof is attached. The `AgentCorePaymentsPlugin` handles payment end-to-end: it intercepts 402 responses, generates a USDC proof via the AgentCore payment manager, attaches it, and retries. Your tool code stays a plain `http_request` call.

## Architecture

```
App Backend (ManagementRole)              AgentCore Runtime
  |                                        +------------------------------+
  | create_session(budget=$X)              |  runtime_agent.py            |
  |                                        |  BedrockAgentCoreApp         |
  |-- invoke(manager_arn, session_id, -->  |  + AgentCorePaymentsPlugin   |
  |         instrument_id, prompt)         |                              |
  |                                        |  http_request -> 402         |
  |<-- {response, artifacts: [{url}]} ---  |  -> ProcessPayment -> retry  |
  |                                        |  -> Code Interpreter         |
  | get_session(check spend)               |  -> export to S3             |
                                           +------------------------------+
                                                      |
                                                      v
                                          CloudWatch GenAI Observability
                                          (automatic via OpenTelemetry)
```

## How It Works

`AgentCorePaymentsPlugin` handles the entire x402 payment lifecycle:

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
    tools=[http_request, code_interpreter, export_artifact_to_s3, ...],
    plugins=[payment_plugin],
)
```

See [`runtime_agent.py`](heurist_finance_agent/runtime_agent.py) for the full implementation.

## Sample Details

| | |
|---|---|
| AgentCore components | AgentCore payments, AgentCore Code Interpreter, AgentCore Runtime |
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
- Node.js 20+ (for the `@aws/agentcore` CLI)
- Docker (running, for `agentcore deploy` container build)
- [AWS CDK](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html) installed globally

## Layout

```
pay-for-data/
├── README.md
├── requirements.txt
├── .env.example
├── pay-for-data.ipynb                    # notebook: deploy and invoke via AgentCore Runtime
└── heurist_finance_agent/
    ├── runtime_agent.py                  # AgentCore Runtime entry point (BedrockAgentCoreApp)
    ├── catalog.py                        # fetches Heurist registry, formats for system prompt
    ├── catalog_live_cache.json           # synced catalog (bundled in Runtime image)
    ├── config.py                         # loads .env
    └── scripts/
        └── sync_registry.py              # CLI: refreshes cached Heurist catalog
```

## Quick Start

Open [`pay-for-data.ipynb`](pay-for-data.ipynb) and run the cells in order:

| Step | What happens |
|------|-------------|
| 1 | Configure credentials and confirm AWS identity |
| 2 | Sync the Heurist tool catalog (bundled in the container image) |
| 3 | Create the S3 artifacts bucket |
| 4 | Install the AgentCore CLI, scaffold and deploy |
| 5 | Add IAM permissions to the execution role |
| 6 | Invoke the deployed agent and inspect results |
| 7 | View observability traces in CloudWatch |
| 8 | Cleanup |

## Payment Flow

When the agent calls a paid Heurist endpoint:

1. `http_request` sends a POST to the endpoint URL.
2. Heurist returns HTTP 402 with x402 payment terms (network, asset, amount, recipient).
3. `AgentCorePaymentsPlugin` intercepts the response.
4. The plugin asks the AgentCore payment manager to generate a payment proof.
5. The payment manager uses the payment instrument to sign a USDC transfer and returns a proof.
6. The plugin attaches the proof as `X-PAYMENT` and retries — Heurist validates and returns the data.

The plugin retries up to 3 times per tool call. Payment limits are enforced at the session scope — the agent cannot exceed `maxSpendAmount`.

## How the Runtime Agent Works

`runtime_agent.py` implements the AgentCore Runtime service contract with full feature parity:

**Stateless, payload-driven**
All payment config (manager ARN, session ID, instrument ID) comes from the invocation payload. The container holds no credentials. The app backend (ManagementRole) creates payment sessions with spending limits before each invocation. The Runtime execution role (ProcessPaymentRole) can only spend within those limits.

**AgentCore Code Interpreter**
Code Interpreter is a remote AWS API — it works identically from a Runtime container as from any other environment. The agent uses it for pandas/matplotlib analysis and chart generation.

**S3 artifact storage**
Artifacts produced by Code Interpreter are uploaded to S3 and returned as presigned download URLs. The response shape is:

```json
{
  "response": "<markdown research summary>",
  "artifacts": [
    {"name": "chart.png", "url": "https://...", "expires_in": 3600}
  ]
}
```

If `CI_ARTIFACTS_BUCKET` is not configured, the agent degrades gracefully: charts become markdown tables, text returns inline.

**Observability**
The `agentcore deploy` CLI configures the container to run under `opentelemetry-instrument`. Combined with `aws-opentelemetry-distro` (included in `pyproject.toml`), this provides:
- Strands agent spans (LLM calls, tool calls, agent turns) → CloudWatch GenAI Observability
- Code Interpreter calls stitched as child spans via W3C `traceparent` botocore instrumentation
- Payment calls (`ProcessPayment`, `GetPaymentInstrument`) as boto3 child spans

No instrumentation code required in `runtime_agent.py`.

**Execution role permissions** (attached by the notebook, Step 5):

| Permission set | Actions | Resource scope |
|---|---|---|
| Payment data-plane | `ProcessPayment`, `GetPaymentInstrument`, `GetPaymentSession` | `payment-manager/*` |
| Code Interpreter | `StartCodeInterpreterSession`, `InvokeCodeInterpreter`, `StopCodeInterpreterSession` | `code-interpreter/*` |
| S3 artifacts | `PutObject`, `GetObject` | `<bucket>/heurist-finance-artifacts/*` |

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

These values are passed in the invocation payload at runtime. The `.env` bundled in the container image contains only non-sensitive service config: `CI_ARTIFACTS_BUCKET`, `AWS_REGION`, `BEDROCK_MODEL_ID`.

## Notes

- Payment sessions expire. Create a fresh session before each invocation in automated workflows.
- Each paid call settles USDC on Base. Ensure your payment instrument is funded.
- Sync the catalog cache before building the container image (`sync_registry.py`). The cache is bundled in the image — the container does not call the Heurist registry at startup.
- Presigned artifact URLs expire after `CI_ARTIFACTS_TTL` seconds (default: 1 hour). Download or forward the URL to the end user promptly.
