# Tutorial 06 — Research Agent with Payment Memory

| Information         | Details                                                              |
|:--------------------|:---------------------------------------------------------------------|
| Tutorial type       | Conversational                                                       |
| Agent type          | Single                                                               |
| Agentic Framework   | Strands Agents                                                       |
| LLM model           | Anthropic Claude Sonnet 4.6                                          |
| Tutorial components | AgentCore payments, AgentCore Memory, AgentCorePaymentsPlugin        |
| Example complexity  | Intermediate                                                         |
| SDK used            | bedrock-agentcore SDK, Strands Agents SDK                            |

## Overview

In previous tutorials the agent is stateless — every session starts from scratch and pays from scratch. This tutorial adds **AgentCore Memory** so the agent builds intelligence across sessions:

- Remembers what topics it already paid to research (avoids re-paying for the same data)
- Learns user preferences (budget tolerance, topic interests)
- Tracks which endpoints were useful versus expensive

The agent recalls past research before each request, decides per-topic whether to reuse memory or pay for fresh data, and reports cost transparently.

### How Payments + Memory work together

```
Session 1 (new user)                    Session 2 (returning user)
  │                                       │
  │ "Research renewable energy outlook"    │ "Research renewable energy AND AI market trends"
  │                                       │
  ├─► Pay $0.05 — renewable energy        ├─► Recall per topic:
  ├─► Return summary                      │     • renewable energy → already in memory ✓
  │                                       │     • AI market trends   → not in memory ✗
  │                                       ├─► Skip payment for renewable energy (free)
  │                                       ├─► Pay $0.05 only for AI market trends
  │                                       ├─► Return both summaries + savings report
  │                                       │
  └─► Memory extracts:                    └─► Result: paid $0.05 instead of $0.10 — memory saved $0.05
      • renewable energy researched ($0.05)
```

## Architecture

```
Strands Agent
  + recall_user_context (@tool)
  + http_request
  + AgentCorePaymentsPlugin
       │              │
       │              │
  AgentCore        AgentCore payments
  Memory           ProcessPayment
  (recall)         Session budget
                          │
                   Wallet Provider
                   Coinbase CDP — or — Stripe Privy
```

Workflow per request: **RECALL** (search memory) → **DECIDE** (pay or skip) → **FETCH** (plugin handles 402) → **REPORT** (cost transparency).

## Two Layers of Budget Control

| Layer | Controls | Enforced by |
|-------|----------|-------------|
| **Session budget** ($0.20, 60 min expiry) | Hard ceiling — cannot exceed | AgentCore payments service |
| **Memory intelligence** | Soft optimization — skip redundant calls | Agent logic (system prompt + recall tool) |

Budget enforcement is structural (IAM + API). Memory is additive intelligence on top.

## Wallet-Agnostic by Design

The agent code is the same whether you configured Coinbase CDP or Stripe (Privy) in Tutorial 00. The plugin receives a `payment_instrument_id` — AgentCore payments knows which wallet provider backs that instrument based on the PaymentConnector. Same code, same memory, same agent — only the `.env` values differ.

## Prerequisites

- Tutorial 00 completed (`.env` with `PAYMENT_MANAGER_ARN`, `PAYMENT_INSTRUMENT_ID`, `PAYMENT_CONNECTOR_ID`)
- Wallet funded with testnet USDC from [faucet.circle.com](https://faucet.circle.com/)
- IAM permissions for AgentCore Memory in addition to the payments permissions from Tutorial 00 — see below

### IAM permissions for AgentCore Memory

The caller identity that runs this script needs AgentCore Memory permissions in addition to the payments permissions from Tutorial 00. On a local laptop with an admin profile this is automatic. On SageMaker or other restricted environments, attach the following policy. Scope the resource ARN to your AWS account and region. `CreateMemory` and `ListMemories` are account-level actions and require `Resource: "*"` — narrow them further with condition keys (e.g. `aws:RequestTag`) if needed.

```json
[
  {
    "Effect": "Allow",
    "Action": [
      "bedrock-agentcore:CreateMemory",
      "bedrock-agentcore:ListMemories"
    ],
    "Resource": "*"
  },
  {
    "Effect": "Allow",
    "Action": [
      "bedrock-agentcore:GetMemory",
      "bedrock-agentcore:DeleteMemory",
      "bedrock-agentcore:BatchCreateMemoryRecords",
      "bedrock-agentcore:RetrieveMemoryRecords"
    ],
    "Resource": "arn:aws:bedrock-agentcore:<REGION>:<ACCOUNT_ID>:memory/*"
  }
]
```

Without these, `create_memory` returns `AccessDeniedException` in Step 3.

## Setup

This tutorial declares its own dependencies in `requirements.txt`. Install once per tutorial — Tutorial 00's environment does not cover them.

```bash
pip install -r requirements.txt
```

## Running the Python Script

```bash
python research_agent_with_memory.py
```

The script runs end to end without prompts: creates memory, hydrates it with simulated prior research, runs four queries against the agent (memory hit, budget recall, partial hit, recap), prints session spend, demonstrates budget enforcement with a tiny session, and deletes the memory resource at the end.

If a Python dependency is missing, the script prints the exact `pip install` command and exits — before any AWS resources are created.

## What the Script Does

| Step | Action | Notes |
|------|--------|-------|
| 1 | Load config from `.env` | Reads `PAYMENT_MANAGER_ARN`, instrument, connector, region, model |
| 2 | Verify instrument and create session | $0.20 budget, 60 min expiry |
| 3 | Create AgentCore Memory | Semantic strategy, polls until ACTIVE |
| 4 | Hydrate memory | 4 records: profile, two past research entries, tool preferences |
| 5 | Build agent | Strands `Agent` with `recall_user_context`, `http_request`, payments plugin |
| 6 | Run 4 queries | Memory hit, budget recall, partial hit (the payoff), session recap |
| 7 | Check session spend | `get_payment_session` shows remaining budget |
| 8 | Budget enforcement demo | Tiny $0.0001 session — payment rejected at API level |
| 9 | View payment traces | Prints CloudWatch GenAI Observability Dashboard URL |
| Cleanup | Delete memory resource | Sessions expire automatically; payment manager belongs to Tutorial 00 |

## Key Concepts

**AgentCore Memory** — A managed memory service for AI agents. Records are indexed and retrieved semantically. The script uses one *semantic strategy* with one namespace per user (`/actor/{USER_ID}/facts/`). Memory must reach `ACTIVE` status before record operations work.

**Memory namespace** — A path-like key that scopes records. The script uses `/actor/{USER_ID}/facts/` so multiple users could share the same Memory resource without colliding.

**Hydration** — Pre-populating memory with simulated prior research so the demo doesn't need a multi-session run to show value. The hydrated records use `yesterday`'s date so the agent's freshness rule (7 days) treats them as authoritative.

**Two-step paid-call pattern** — The Coinbase x402 *discovery search* endpoint is a free catalog. Calling it does not cost anything. To actually obtain research data the agent must call one of the `resource` URLs the catalog returns; that's where the 402 → payment → retry flow runs. The system prompt encodes this pattern so the agent's spend reports stay honest.

**Hard limit vs soft optimization** — The session's `maxSpendAmount` is enforced by AgentCore payments at the API level — the LLM cannot exceed it. Memory is an additive optimization that lets the agent stretch the same budget further by skipping redundant calls.

**`recall_user_context` tool** — A `@tool`-decorated function that wraps `RetrieveMemoryRecords`. The agent's system prompt mandates a recall before any paid call.

## Troubleshooting

### `create_memory` returns AccessDeniedException

Your caller identity is missing AgentCore Memory permissions. Attach the policy from the IAM section above. On SageMaker, add it to the execution role.

### Memory stays in CREATING for a long time

Normal startup is 30–90 seconds. The script polls every 10 seconds. If it stays CREATING beyond 5 minutes, call `get_memory` once to inspect `failureReason`. Check CloudWatch logs in the bedrock-agentcore log group for index build errors.

## Role Separation for Deployed Agents

This tutorial runs locally under your AWS credentials. When deployed, the runtime process runs under **ProcessPaymentRole** — the plugin calls `ProcessPayment` on behalf of the agent within the budget set by the app backend. The runtime cannot create sessions, modify limits, or provision wallets. The agent (LLM) never calls `ProcessPayment` directly. The memory tool and payment plugin work the same way when deployed. See Tutorial 02 for the full role separation implementation.

To test role separation locally, pass an assumed-role session to the SDK client:

```python
from utils import assume_role
import boto3

# App backend (ManagementRole) creates the session
manager = PaymentManager(payment_manager_arn=ARN, region_name=REGION)
session = manager.create_payment_session(user_id=USER_ID, ...)

# Agent runs under ProcessPaymentRole — can only ProcessPayment
agent_session = assume_role(boto3.Session(), PROCESS_PAYMENT_ROLE_ARN, "agent")
agent_manager = PaymentManager(payment_manager_arn=ARN, boto3_session=agent_session)
# Pass agent_manager to the plugin — restricted credentials
```

## Clean Up

The script deletes the memory resource at the end. Payment sessions expire automatically after their `expiryTimeInMinutes`. Payment resources (Manager, Connector, Instrument) belong to Tutorial 00 — run the cleanup section in `setup_agentcore_payments.py` when you are done with all tutorials.

> **Cost notice:** AgentCore Memory may incur AWS charges based on storage and retrieval usage. The script's automatic cleanup keeps these costs minimal, but if the script aborts before reaching cleanup, delete the memory manually:
>
> ```bash
> aws bedrock-agentcore-control delete-memory --memory-id <id>
> ```

## Next Steps

- **Tutorial 07** — `../07-multi-agent-payment-orchestrator/` — Multi-agent orchestration with per-agent budgets and provider-separated wallets
- **Use case: Browser paywall** — `../../02-use-cases/pay-for-content-browser-use/` — End-to-end use case with a deployable x402 paywall server on AgentCore runtime
