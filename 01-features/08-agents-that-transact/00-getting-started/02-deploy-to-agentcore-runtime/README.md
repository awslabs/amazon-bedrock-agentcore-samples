# Tutorial 02 — Deploy a Payment Agent to AgentCore Runtime

| Information         | Details                                                                     |
|:--------------------|:-----------------------------------------------------------------------------|
| Tutorial type       | Runtime deployment                                                          |
| Agent type          | Single, payment-enabled                                                     |
| Agentic Framework   | Strands Agents                                                              |
| LLM model           | Anthropic Claude Sonnet 4.6 (`us.anthropic.claude-sonnet-4-6`)              |
| Components          | AgentCore CLI (`create` / `deploy` / `status` / `invoke` / `logs` / `remove`), AgentCore Runtime, `AgentCorePaymentsPlugin`, AgentCore SDK `PaymentManager` (`create_payment_session` / `get_payment_session`) |
| Example complexity  | Intermediate                                                               |

> **Reads** `PAYMENT_MANAGER_ARN`, `USER_ID`, `INSTRUMENT_ID`, `AWS_REGION` from the shared `.env`. **Does** deploy `payment_agent.py` to AgentCore Runtime with the CLI, mint a budgeted session with the AgentCore SDK `PaymentManager`, and invoke the deployed agent over HTTPS — writing `AGENT_RUNTIME_ARN` back to `.env`. → [How the pieces fit together](../README.md#cli-vs-sdk)

## Overview

Tutorial 01 ran a payment-enabled Strands agent locally. Here you deploy the **same agent** to **AgentCore Runtime** with the **AgentCore CLI** so it can be invoked over HTTPS with SigV4 auth from any AWS-authenticated client. You use two complementary tools: the **AgentCore CLI** provisions and runs the runtime (`agentcore create` → `deploy` → `invoke` → `logs`), and the **AgentCore SDK** `PaymentManager` (`manager.create_payment_session(...)`) mints each request's budgeted payment session before you invoke. The Payment Manager, connector, and wallet instrument already exist from Tutorial 00; this tutorial reads their IDs from the shared `.env` and reuses them.

The deployed agent runs under its own execution role. Its `AgentCorePaymentsPlugin` intercepts HTTP 402 responses and calls `ProcessPayment` within the session budget, so the LLM never calls payment APIs directly. All payment context (manager ARN, session, instrument, user) arrives in the invocation payload, keeping the agent stateless — the same deployed binary can serve different users with different budgets.

> **Billable resources.** `agentcore deploy` creates real AWS resources (AgentCore Runtime, IAM execution role, CloudWatch). See [AgentCore pricing](https://aws.amazon.com/bedrock/agentcore/pricing/). First deploy takes a few minutes for IAM role propagation; later deploys are faster.

> **Testnet only.** The agent pays x402 endpoints on Base Sepolia (network `ETHEREUM`) with free testnet USDC from [faucet.circle.com](https://faucet.circle.com/). Testnet USDC has no monetary value.

> **Supported regions:** `us-east-1`, `us-west-2`, `eu-central-1`, `ap-southeast-2`. Set `AWS_REGION` in the shared `.env` to one of these.

## Architecture

![Architecture](images/high_level_architecture.png)

```
App Backend                          AgentCore Runtime
  │                                   ┌──────────────────────────┐
  │ create_payment_session($0.50)     │  Payment Agent            │
  │  (PaymentManager SDK)             │  (execution role)         │
  │── invoke(session, instrument) ──►│  Plugin: ProcessPayment   │
  │  (agentcore invoke)               │  Scope: ProcessPayment    │
  │◄── weather data + cost ─────────│   only — spends within the │
  │                                   │   session budget set by    │
  │ get_payment_session(check spend)  │   the backend             │
  │  (PaymentManager SDK)             └──────────────────────────┘
```

### How the agent code works (`payment_agent.py`)

1. **`BedrockAgentCoreApp` + `@app.entrypoint`** — the standard AgentCore Runtime service contract. This file is copied into the scaffolded project as `app/PaymentAgent/main.py`.
2. **Payload-driven config** — the agent reads all payment context (`payment_manager_arn`, `user_id`, `payment_session_id`, `payment_instrument_id`) from the invocation payload. This keeps the agent stateless.
3. **`AgentCorePaymentsPlugin`** — built per request from the payload context (network preferences `eip155:84532` / `base-sepolia`); it intercepts HTTP 402 responses and calls `ProcessPayment` automatically within the session budget.

## Prerequisites

- **Tutorial 00 completed** — the shared `.env` (one directory up, `00-getting-started/.env`) is populated with `PAYMENT_MANAGER_ARN`, `USER_ID`, `INSTRUMENT_ID`, `AWS_REGION`, etc.
- **Tutorial 01 completed** — you understand the local agent + plugin flow.
- **Funded wallet** — the instrument from Tutorial 00 has testnet USDC and delegated signing granted ([faucet.circle.com](https://faucet.circle.com/)).
- **AgentCore CLI** (Node.js 20+): `npm install -g @aws/agentcore`
- **AWS CDK** (used by `agentcore deploy`): `npm install -g aws-cdk`
- **Python 3.10+** and AWS CLI configured (`aws sts get-caller-identity`).

```bash
pip install -r requirements.txt
```

## Walkthrough

Run these steps top to bottom. Steps 1–5 provision and deploy the runtime with the CLI; steps 6–8 mint a budgeted session with the AgentCore SDK and invoke the deployed agent.

### Step 1 — (Optional) test locally before deploying

Confirm the agent starts cleanly on your machine first.

```bash
python payment_agent.py
# In another terminal:
curl -s http://localhost:8080/ping
# Stop the agent (Ctrl+C) before continuing.
```

### Step 2 — Scaffold the AgentCore project

`agentcore create` generates a runtime project (CDK app, Dockerfile, and an `app/PaymentAgent/` package) wired for a Strands agent served over HTTP with a Bedrock model and no memory.

```bash
agentcore create --name PaymentAgent --framework Strands --protocol HTTP --model-provider Bedrock --memory none
cd PaymentAgent
```

### Step 3 — Copy the agent into the project

Replace the scaffold's placeholder entrypoint with your payment agent.

```bash
cp ../payment_agent.py app/PaymentAgent/main.py
```

### Step 4 — Set the project dependencies

The runtime build installs from `app/PaymentAgent/pyproject.toml`. `payment_agent.py` imports `strands_tools`, `dotenv`, and the payments plugin (`bedrock_agentcore.payments.integrations.strands`), so list those libraries in `[project].dependencies`, then remove the stale lock so the build regenerates it with the new deps.

Edit `app/PaymentAgent/pyproject.toml` so its `[project]` dependencies include:

```toml
[project]
name = "payment-agent"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "bedrock-agentcore[strands-agents]>=1.9.0",
    "strands-agents>=1.0.0",
    "strands-agents-tools>=0.2.0",
    "python-dotenv>=1.0.0",
    "boto3>=1.43.5",
]
```

Then remove the old lock so it is regenerated with these dependencies:

```bash
rm -f app/PaymentAgent/uv.lock
```

### Step 5 — Deploy and attach payment permissions

`agentcore deploy` builds the image and provisions the Runtime, its execution role, and CloudWatch (~2–3 min on first run while IAM roles propagate).

```bash
agentcore deploy -y
agentcore status
```

Tutorial 00 already provisioned the Payment Manager and connector, so this project deploys a plain runtime. After the deploy, attach the payment data-plane permissions the agent needs at request time — `ProcessPayment`, `GetPaymentInstrument`, and `GetPaymentSession` — to the auto-created execution role. Find the role name in the `agentcore status` output (it contains `PaymentAgent` and `Execution`), then attach an inline policy scoped to your payment manager:

```bash
# Replace <EXECUTION_ROLE_NAME> with the PaymentAgent execution role from `agentcore status`,
# and <REGION>/<ACCOUNT_ID> with your values.
aws iam put-role-policy \
  --role-name <EXECUTION_ROLE_NAME> \
  --policy-name PaymentDataPlaneAccess \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:ProcessPayment",
        "bedrock-agentcore:GetPaymentInstrument",
        "bedrock-agentcore:GetPaymentSession"
      ],
      "Resource": "arn:aws:bedrock-agentcore:<REGION>:<ACCOUNT_ID>:payment-manager/*"
    }]
  }'
```

### Step 6 — Mint a budgeted session (AgentCore SDK)

Sessions are per-request and carry a spend budget, so you create one before each invoke, scoped to the user you serve and the budget you want to allow. The **simplest path** is to let the CLI manage the session for you: `agentcore invoke --auto-session` creates (and reuses) a session with the manager's default spend limit, so you can skip straight to Step 7. When you want to **control the budget explicitly**, mint the session with the AgentCore SDK `PaymentManager` and pass its ID to `agentcore invoke`.

Run this short script from the tutorial directory to mint a $0.50 session and print its ID:

```python
# mint_session.py — creates a budgeted payment session for the invoke in Step 7
import os
from pathlib import Path
from dotenv import load_dotenv
from bedrock_agentcore.payments import PaymentManager

# Load the shared .env (one directory up, at 00-getting-started/.env)
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

REGION = os.environ["AWS_REGION"]
PAYMENT_MANAGER_ARN = os.environ["PAYMENT_MANAGER_ARN"]
USER_ID = os.environ["USER_ID"]

manager = PaymentManager(payment_manager_arn=PAYMENT_MANAGER_ARN, region_name=REGION)

session = manager.create_payment_session(
    user_id=USER_ID,
    limits={"maxSpendAmount": {"value": "0.50", "currency": "USD"}},
    expiry_time_in_minutes=60,
)
print(session["paymentSessionId"])
```

```bash
SESSION_ID=$(python mint_session.py)
echo "$SESSION_ID"
```

Copy the printed `paymentSessionId` for the invoke in Step 7.

### Step 7 — Invoke the deployed agent

This agent reads its payment context from the payload, so pass the manager ARN, user, session, and instrument in the JSON — the agent requires all four. Use the `SESSION_ID` you minted in Step 6. `agentcore invoke` is project-scoped, so run it from inside the scaffolded `PaymentAgent/` directory (where `agentcore.json` lives):

```bash
cd PaymentAgent   # agentcore invoke reads the project config here
agentcore invoke '{"prompt": "Access this paid weather API and tell me what data you get back: https://x402-test.genesisblock.ai/api/weather", "payment_manager_arn": "<MANAGER_ARN>", "user_id": "<USER_ID>", "payment_session_id": "<SESSION_ID>", "payment_instrument_id": "<INSTRUMENT_ID>"}'
```

If you skipped the explicit session in Step 6, let the CLI manage it instead: add `--auto-session` (with `--payment-user-id <USER_ID>`) and `agentcore invoke` creates or reuses a session with the manager's default spend limit, so you omit `payment_session_id` from the payload.

> **This agent is payload-driven.** `handle_request` reads `payment_manager_arn`, `user_id`, `payment_session_id`, and `payment_instrument_id` from the payload dict and returns `{"error": "Missing required fields in payload: ..."}` if any are absent.

### Step 8 — Check the spend (AgentCore SDK)

Confirm the paid call debited the session as expected. This reads the session back with the SDK and prints the remaining budget:

```python
# check_spend.py — reads the remaining budget for the session from Step 6
import os, sys
from pathlib import Path
from dotenv import load_dotenv
from bedrock_agentcore.payments import PaymentManager

# Load the shared .env (one directory up, at 00-getting-started/.env)
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

REGION = os.environ["AWS_REGION"]
PAYMENT_MANAGER_ARN = os.environ["PAYMENT_MANAGER_ARN"]
USER_ID = os.environ["USER_ID"]
SESSION_ID = sys.argv[1]  # pass the session ID from Step 6

manager = PaymentManager(payment_manager_arn=PAYMENT_MANAGER_ARN, region_name=REGION)

session = manager.get_payment_session(user_id=USER_ID, payment_session_id=SESSION_ID)
print("Max budget:      ", session["limits"]["maxSpendAmount"])
print("Available budget:", session["availableLimits"]["availableSpendAmount"])
```

```bash
python check_spend.py "$SESSION_ID"
```

## What the agent does

The agent calls the paid weather endpoint with `http_request`. The endpoint returns HTTP 402; the `AgentCorePaymentsPlugin` intercepts it, settles the payment via `ProcessPayment` against the instrument within the session budget, retries the request, and returns the weather data plus the cost. The agent's scope is `ProcessPayment` only — it spends within the session budget the backend set, and it does not create sessions, override the budget, or provision wallets.

The full request path — invoke → 402 → `ProcessPayment` → retry → `200` + data — looks like this:

![Payment Flow Sequence](images/payment_flow_sequence.png)

## Inspect / verify

Run these from the scaffolded project directory (`PaymentAgent/`), where the AgentCore project config lives.

```bash
# Runtime status (deployed agent)
agentcore status

# Stream runtime logs
agentcore logs
```

Confirm the Runtime ARN was written to the shared `.env`:

```bash
grep AGENT_RUNTIME_ARN ../../.env
```

CloudWatch GenAI observability dashboard: `https://<region>.console.aws.amazon.com/cloudwatch/home?region=<region>#gen-ai-observability/agent-core`

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `agentcore: command not found` | AgentCore CLI not installed | `npm install -g @aws/agentcore` (Node.js 20+) |
| Deploy build fails on import (`strands_tools` / `dotenv` / payments plugin) | Project `pyproject.toml` missing the agent's dependencies | Add the Step 4 dependencies and `rm -f app/PaymentAgent/uv.lock`, then redeploy |
| Deploy fails with CDK bootstrap error | Account/region not bootstrapped | `cdk bootstrap aws://<account-id>/<region>` |
| `Missing required fields in payload` | Payload missing one of `payment_manager_arn`, `user_id`, `payment_session_id`, `payment_instrument_id` | Include all four fields in the invoke JSON (this agent is payload-driven) |
| Access-denied on `ProcessPayment` after deploy | Execution role lacks payment data-plane permissions | Attach `ProcessPayment`/`GetPaymentInstrument`/`GetPaymentSession` to the execution role with the `aws iam put-role-policy` command in Step 5 |
| `Instrument not found` at invoke | `user_id` doesn't match the instrument's owner | Use the exact `USER_ID` from Tutorial 00's `.env` |
| `Delegated signing grant is not active` | Wallet consent not completed | Complete the funding/delegation step from Tutorial 00 / 03 |

## Clean Up

> **Warning:** Cleanup is irreversible.

```bash
cd PaymentAgent
agentcore remove all -y
```

This deletes the AgentCore Runtime deployment and its AWS resources (CDK stack, CloudWatch logs). Payment sessions expire automatically. The shared Payment Manager, connector, and instrument from Tutorial 00 remain in place — tear those down with Tutorial 00's cleanup. The connector and manager teardown uses the AgentCore CLI (`agentcore remove payment-connector` / `remove payment-manager`, then `agentcore deploy -y` to apply). The instrument is deleted with the AgentCore SDK `PaymentManager` — pass the connector id and user id alongside the instrument id (all read from the shared `.env`):

```python
import os
from pathlib import Path
from dotenv import load_dotenv
from bedrock_agentcore.payments import PaymentManager

# Load the shared .env (one directory up, at 00-getting-started/.env)
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

REGION = os.environ["AWS_REGION"]
PAYMENT_MANAGER_ARN = os.environ["PAYMENT_MANAGER_ARN"]
PAYMENT_CONNECTOR_ID = os.environ["PAYMENT_CONNECTOR_ID"]
INSTRUMENT_ID = os.environ["INSTRUMENT_ID"]
USER_ID = os.environ["USER_ID"]

manager = PaymentManager(payment_manager_arn=PAYMENT_MANAGER_ARN, region_name=REGION)

manager.delete_payment_instrument(
    payment_instrument_id=INSTRUMENT_ID,
    payment_connector_id=PAYMENT_CONNECTOR_ID,
    user_id=USER_ID,
)
```

## Next steps

- **Tutorial 03** — [`../03-user-onboarding-wallet-funding/`](../03-user-onboarding-wallet-funding/) — Per-user wallet onboarding, funding, delegation, balance checks (SDK).
- **Tutorial 04** — [`../04-agent-with-coinbase-bazaar-via-gateway/`](../04-agent-with-coinbase-bazaar-via-gateway/) — Discover paid MCP tools via AgentCore Gateway (CLI + SDK).
