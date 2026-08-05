# Tutorial 08 - OpenAI Agents SDK Payment Agent

| Information         | Details                                                                    |
|:--------------------|:---------------------------------------------------------------------------|
| Tutorial type       | Conversational                                                             |
| Agent type          | Single, payment-enabled                                                    |
| Agentic framework   | OpenAI Agents SDK                                                          |
| LLM model           | OpenAI GPT-5.5 (`openai.gpt-5.5`) on Amazon Bedrock                       |
| Components          | OpenAI Agents SDK, `PaymentManager`, x402 endpoint, payment session        |
| Example complexity  | Easy                                                                       |

> **Reads** the shared `.env` from Tutorial 00 (`PAYMENT_MANAGER_ARN`, `USER_ID`,
> `INSTRUMENT_ID`). **Does** create a per-run spending session in code, run one local OpenAI
> Agents SDK agent, and pay an x402 endpoint automatically within the session budget. It does not
> create a wallet, read wallet-provider credentials, or deploy an AgentCore Runtime.
> See [How the pieces fit together](../README.md#cli-vs-sdk).

## Overview

The payment manager, connector, IAM roles, and funded wallet instrument are already provisioned by
[Tutorial 00](../00-setup-agentcore-payments/). This tutorial reuses those resources to show the
smallest payment-enabled agent built with the OpenAI Agents SDK.

The script creates a short-lived spending session with the AgentCore SDK `PaymentManager`, configures
the OpenAI Agents SDK to use GPT-5.5 through Amazon Bedrock's OpenAI-compatible endpoint, and exposes
`x402_fetch` as a function tool. When the endpoint returns HTTP 402, the helper asks AgentCore
Payments for a payment proof and retries the request. The agent receives the paid content and
summarizes it for the user.

The tutorial is wallet-provider agnostic. Coinbase CDP and Stripe/Privy credentials remain in the
Tutorial 00 setup; this agent consumes only the resulting AgentCore resource identifiers.

> **Billable resources.** A successful x402 call spends testnet USDC from the funded wallet and is
> metered by AgentCore Payments. See
> [AgentCore pricing](https://aws.amazon.com/bedrock/agentcore/pricing/).

> **Testnet only.** Use Base Sepolia or Solana Devnet with free USDC from
> [faucet.circle.com](https://faucet.circle.com/). Testnet USDC has no monetary value.

> **Supported AgentCore Payments regions:** `us-east-1`, `us-west-2`, `eu-central-1`,
> `ap-southeast-2`.

## Architecture

```text
User
  |
  v
OpenAI Agents SDK Runner
  |
  +----> OpenAI GPT-5.5 on Amazon Bedrock
  |
  +----> x402_fetch(url)
              |
              +----> Paid endpoint returns HTTP 402
              |
              +----> PaymentManager -> AgentCore Payments
                                      -> budget check
                                      -> delegated signing
                                      -> payment proof
              |
              +----> Retry with payment header -> HTTP 200
  |
  v
Agent summarizes the paid response
```

### How the code works

1. `load_config()` reads the shared resource identifiers and local run settings.
2. `create_payment_session()` creates a 60-minute session with a server-enforced spend limit.
3. `build_model()` connects `OpenAIResponsesModel` to Amazon Bedrock using the current AWS identity.
4. `load_x402_fetch()` supplies the manager, instrument, session, user, and region to the x402 helper.
5. `build_agent()` registers that helper with `function_tool()` on one OpenAI `Agent`.
6. `Runner.run_sync()` runs the agent and prints its final result.

## Prerequisites

- **Tutorial 00 completed.** The shared `.env`, one directory above this tutorial at
  `00-getting-started/.env`, must contain `PAYMENT_MANAGER_ARN`, `USER_ID`, and `INSTRUMENT_ID`.
- **A configured wallet provider.** Follow one of the
  [wallet-provider setup guides](../00-setup-agentcore-payments/providers/). Tutorial 08 does not
  read or copy the provider's API keys or wallet secrets.
- **A funded wallet with delegated signing.** Follow
  [Tutorial 03](../03-user-onboarding-wallet-funding/) to fund the testnet instrument and grant the
  provider permission to sign payments.
- **Python 3.10+** and AWS credentials for the same account as the payment manager. Confirm them with
  `aws sts get-caller-identity`.
- **Access to OpenAI GPT-5.5 on Amazon Bedrock.** The model connection defaults to `us-east-1`.
- **AgentCore CLI (optional).** It is only needed for the inspect step:
  `npm install -g @aws/agentcore` with Node.js 20+.

## Walkthrough

### Step 1 - Confirm Tutorial 00 populated the shared `.env`

From this tutorial directory, confirm the identifiers used by the agent are present:

```bash
grep -E 'PAYMENT_MANAGER_ARN|INSTRUMENT_ID|USER_ID' ../.env
```

If a value is missing, return to [Tutorial 00](../00-setup-agentcore-payments/) before continuing.
The payment region is derived from `PAYMENT_MANAGER_ARN`, which avoids sending payment requests to a
different region from the manager.

### Step 2 - Create the local environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

No additional credential file is required. The OpenAI model connection also uses your AWS
credentials, so this tutorial does not require an OpenAI API key.

### Step 3 - Review the optional run settings

The defaults call the test market-news endpoint with a `$1.00` session budget:

```bash
export PAID_URL="https://x402-test.genesisblock.ai/api/market-news"
export PAYMENT_SESSION_BUDGET="1.00"
export BEDROCK_OPENAI_MODEL_ID="openai.gpt-5.5"
export BEDROCK_OPENAI_MODEL_REGION="us-east-1"
```

You only need to export values that you want to override.

### Step 4 - Run the OpenAI payment agent

```bash
python openai_payment_agent.py
```

The script creates a new budget-bounded session, calls the x402 endpoint, obtains a payment proof,
retries the request, and prints the OpenAI Agents SDK run result. A successful run reports that the
endpoint returned HTTP 200 and that payment succeeded.

This command runs the agent on your local machine. It does not yet run on AgentCore Runtime.

## Try different budgets (payment limits)

The default session allows up to `$1.00` of cumulative spend. To exercise the limit, set a budget
below the endpoint price and run the agent again:

```bash
PAYMENT_SESSION_BUDGET="0.0001" python openai_payment_agent.py
```

The payment is rejected because the session cannot cover the requested amount. Restore the normal
budget for the happy path:

```bash
PAYMENT_SESSION_BUDGET="1.00" python openai_payment_agent.py
```

Budget enforcement belongs to the AgentCore payment session, not to the prompt or the model. The
service tracks cumulative spend and rejects a payment that would exceed `maxSpendAmount`. The agent
cannot raise its own limit.

## What the agent does

| Scenario | How to run it | What it shows |
|:---------|:--------------|:--------------|
| Happy path | Run with the default `$1.00` budget | HTTP 402, payment proof, retry, and HTTP 200 |
| Budget exceeded | Set `PAYMENT_SESSION_BUDGET` below the endpoint price | Service-level spend enforcement |
| Different paid API | Set `PAID_URL` to another HTTPS x402 endpoint | The payment tool is reusable |
| Different model location | Set `BEDROCK_OPENAI_MODEL_ID` and `BEDROCK_OPENAI_MODEL_REGION` | Model configuration is independent of the payment-manager region |

The helper accepts only HTTPS URLs and rejects private, loopback, and link-local addresses before
making a request.

## Inspect / verify

The local output should include the created agent name and an agent response that reports a
successful payment and HTTP 200 response:

```text
Created OpenAI agent with name: OpenAI Payment Agent
...
Payment succeeded: yes
Endpoint returned HTTP 200
```

Inspect the payment infrastructure created by Tutorial 00:

```bash
cd ../00-setup-agentcore-payments/PaymentSetup
agentcore status --type payment
```

You can also confirm which AWS identity the model and payment SDK are using:

```bash
aws sts get-caller-identity
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|:--------|:-------------|:----|
| `Missing PAYMENT_MANAGER_ARN`, `INSTRUMENT_ID`, or `USER_ID` | Tutorial 00 did not populate the shared `.env` | Re-run Tutorial 00 and confirm the three identifiers with the Step 1 command |
| `Payment manager not found` | The manager ARN is stale, deleted, or belongs to a different AWS account | Check `aws sts get-caller-identity`, then recreate or recapture the manager in Tutorial 00 |
| The endpoint returns 402 but payment fails | The wallet is unfunded or delegated signing is not enabled | Complete the funding and delegation steps linked under Prerequisites |
| Budget is exceeded immediately | The session budget is below the endpoint price | Expected for the `$0.0001` exercise; restore `PAYMENT_SESSION_BUDGET=1.00` |
| Bedrock model request is denied | AWS credentials are expired or the configured model/region is unavailable to the account | Refresh AWS authentication and verify the model ID and model region |
| `Only HTTPS URLs are supported` or a private-address error | `PAID_URL` failed the helper's URL safety checks | Use a public HTTPS x402 endpoint |
| Import error for `agents`, `bedrock_agentcore`, or `httpx` | The virtual environment is inactive or dependencies are missing | Activate `.venv` and run `pip install -r requirements.txt` |

## Deploy to AgentCore Runtime

## Clean Up

Each run creates a payment session that expires automatically after 60 minutes. This tutorial
creates no other durable resources.

The shared payment manager, connector, and instrument belong to Tutorial 00. After finishing the
payments tutorial series, follow [Tutorial 00's cleanup instructions](../00-setup-agentcore-payments/#clean-up)
to remove them. Delete the payment instrument before removing its connector and manager.

## Next steps

- Use [Tutorial 02](../02-deploy-to-agentcore-runtime/) as the reference pattern for the Runtime
  service contract, deployment, invocation, payment permissions, logs, and cleanup.
- Continue to [Tutorial 07](../07-multi-agent-payment-orchestrator/) after the single-agent payment
  path is working if you want to compare independent budgets across agents.
- Read the [OpenAI Agents SDK documentation](https://openai.github.io/openai-agents-python/) and the
  [AgentCore Payments developer guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments.html)
  for the underlying APIs.
