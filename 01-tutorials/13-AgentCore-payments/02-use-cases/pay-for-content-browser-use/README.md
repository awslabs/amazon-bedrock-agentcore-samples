# Pay for Content — Browser Use Case

## Overview

"Amazon Bedrock AgentCore payments enables AI agents to make autonomous payments for
digital services — without ever holding private keys or requiring human approval for
each transaction."

Without AgentCore payments, an agent that needs to pay for content must either hold
a private key (exposing credentials to the model) or interrupt the user to complete
the payment manually. This use case shows a third path: the agent delegates signing to
AgentCore payments, stays within human-set payment limits, and completes the entire
browse-pay-extract flow autonomously.

The agent uses the **AgentCore Browser Tool** to navigate a paywalled website, reads
the embedded x402 payment requirement from the page DOM, calls `ProcessPayment` to
generate a cryptographic USDC proof, interacts with the paywall UI, and returns the
unlocked content — all without any private key exposure or human intervention.

### Use Case Details

| Information         | Details                                                       |
|:--------------------|:--------------------------------------------------------------|
| Use case type       | Agentic browser automation with autonomous micropayment       |
| Agent type          | Single                                                        |
| Payment protocol    | x402 (HTTP 402 Payment Required)                              |
| Agentic Framework   | Strands Agents                                                |
| LLM model           | Anthropic Claude Sonnet 4.6                                   |
| Complexity          | Intermediate                                                  |
| SDK used            | boto3 + AgentCore SDK + AgentCorePaymentsPlugin (Strands)     |
| Wallet type         | Embedded crypto wallet (AgentCore-provisioned, Coinbase CDP)  |
| Network             | Base Sepolia testnet (`eip155:84532`); Solana Devnet available |

---

## Architecture

There are three distinct phases: **resource provisioning** (runs once), **session setup**
(runs before each agent invocation), and **agent runtime** (the live payment flow).
The content provider is operator-deployed infrastructure — it is not created by the notebook.

```
RESOURCE PROVISIONING  (notebook Step 3, ControlPlaneRole)
─────────────────────────────────────────────────────────────────────────────

  ┌─────────────────────────────────────────────────────────────────────┐
  │  Two-client setup                                                   │
  │                                                                     │
  │  cp_client ──► CP endpoint  ──► CreatePaymentCredentialProvider     │
  │  (bedrock-agentcore-control)    CreatePaymentManager                │
  │                                 CreatePaymentConnector              │
  │                                                                     │
  │  mgmt_client ──► DP endpoint ──► CreatePaymentInstrument            │
  │  (bedrock-agentcore)              (EmbeddedCryptoWallet)            │
  └─────────────────────────────────────────────────────────────────────┘

  AgentCore provisions the on-chain wallet — no pre-existing CDP wallet required.
  Result: CREDENTIAL_PROVIDER_ARN, MANAGER_ARN, PAYMENT_CONNECTOR_ID, PAYMENT_INSTRUMENT_ID


SESSION SETUP  (notebook Step 4, ManagementRole)
─────────────────────────────────────────────────────────────────────────────

  Notebook / App                        AgentCore payments
  ──────────────────                    ──────────────────────────────
  CreatePaymentSession ────────────────► payment limits=$1.00 USD, expiry=60 min
  (ManagementRole via STS)              paymentSessionId ──────────────► passed to agent


AGENT RUNTIME  (notebook Step 6, ProcessPaymentRole)
─────────────────────────────────────────────────────────────────────────────

  User
   │ "Retrieve the article and pay for it"
   ▼
  ┌──────────────────────────────────────────────────────┐
  │  Strands Agent  (Claude Sonnet 4.6)                  │
  │                                                      │
  │  Tool 1: AgentCoreBrowser      Tool 2: process_x402_payment   │
  │  (managed cloud Chromium)      (calls ProcessPayment API)     │
  └───────────┬────────────────────────────┬─────────────┘
              │ HTTPS                      │ AWS API (ProcessPaymentRole)
              ▼                            ▼
  ┌───────────────────────┐    ┌───────────────────────────────┐
  │  Content Provider     │    │  AgentCore payments           │
  │  (team-hosted demo or │    │  ProcessPayment API           │
  │   your own deploy)    │    │                               │
  │                       │    │  ┌────────────────────────┐   │
  │  HTTP 200             │    │  │  Embedded Wallet        │   │
  │  x402 requirement     │    │  │  (Coinbase CDP)         │   │
  │  in DOM script tag    │    │  │  Base Sepolia testnet   │   │
  │                       │    │  └────────────────────────┘   │
  │  proof submitted via  │◄───┤  status: PROOF_GENERATED      │
  │  paywall UI → unlock  │    └───────────────────────────────┘
  └───────────────────────┘
   │ article text
   ▼
  Agent returns content + amount paid to user


OPERATOR CLEANUP  (automatic on session expiry)
─────────────────────────────────────────────────────────────────────────────

  Session expires automatically after expiryTimeInMinutes elapses.
  Agent can no longer spend once the session is past its expiry.
```

**Key design points:**

- **Embedded wallet:** AgentCore provisions the on-chain wallet — no pre-existing CDP
  wallet or funded account is required. The `linkedAccounts` email field ties the wallet
  to a user identity. Coinbase embedded wallets are provisioned synchronously (no OTP step).
- **Two clients, two endpoints:** `cp_client` → CP (`bedrock-agentcore-control.{region}.amazonaws.com`)
  for all control-plane operations including `CreatePaymentCredentialProvider`; `mgmt_client` /
  `agent_dp_client` → DP (`bedrock-agentcore.{region}.amazonaws.com`) for instrument, session, and payment.
- The notebook (not the agent) creates the session via `ManagementRole`. The agent only
  ever uses `ProcessPaymentRole`, which has an explicit IAM Deny on session management.
- The content provider must be deployed to a public HTTPS URL before running the agent —
  `AgentCoreBrowser` is a cloud-managed browser and cannot reach `localhost`.
- The agent never holds a private key. Signing is delegated to the AgentCore-managed
  embedded wallet. This example uses Coinbase CDP; it can be adapted for Stripe/Privy by
  swapping the credential provider configuration in Step 3.

---

## Prerequisites

- AWS account with Amazon Bedrock AgentCore access
- Python 3.10+ and Jupyter Notebook (or JupyterLab)
- AWS CLI v2 configured with credentials (`aws configure`)
- IAM roles created — run `bash setup_roles.sh` and record the ARNs in `.env`
- Content provider deployed to AWS — run `cd content-provider && PAY_TO=0x<your-wallet> bash deploy.sh` and set `CONTENT_DISTRIBUTION_URL` in `.env` (Node.js 18+ and AWS CDK v2 required; see [content-provider/README.md](content-provider/README.md))
- A Coinbase Developer Platform (CDP) account with an API key
  - API key name, private key, and wallet secret are required (see `.env.sample`)
  - **Enable Delegated Signing** in your CDP project before running the agent:
    go to [portal.cdp.coinbase.com](https://portal.cdp.coinbase.com) → your project → **Wallet** → **Embedded Wallets** → **Policies** → enable **Delegated signing**
  - No pre-existing wallet needed — AgentCore provisions the embedded wallet for you
  - After provisioning, fund the wallet via the Circle faucet (https://faucet.circle.com)

> **Note:** This use case provisions an **embedded crypto wallet** via AgentCore.
> You do not need a pre-existing Coinbase wallet. The credential provider (CDP API key)
> authorises AgentCore to create and manage the wallet on your behalf. After provisioning,
> Step 3 prints a **WalletHub URL** — open it to fund the wallet and grant signing permission.

> **Important:** `AgentCoreBrowser` is a cloud-managed browser — it cannot reach
> `localhost`. The content provider `CONTENT_DISTRIBUTION_URL` must be a public HTTPS URL.
> Deploy the included CDK stack first — see [content-provider/README.md](content-provider/README.md)
> — then set `CONTENT_DISTRIBUTION_URL` in `.env` to the printed CloudFront URL.

---

## Running the Use Case

### Step 0 — Create IAM roles

Run `setup_roles.sh` to create the required IAM roles (only needed once per account):

```bash
bash setup_roles.sh
```

### Step 1 — Configure your environment

```bash
cp .env.sample .env
# Edit .env and fill in your values
```

Key variables to set:
- `CDP_API_KEY_NAME` / `CDP_API_KEY_PRIVATE_KEY` / `CDP_WALLET_SECRET` — Coinbase CDP API key
- `WALLET_EMAIL` — email address to associate with the embedded wallet
- `CONTROL_PLANE_ROLE_ARN` / `MANAGEMENT_ROLE_ARN` / `PROCESS_PAYMENT_ROLE_ARN` — from `setup_roles.sh`
- `CONTENT_DISTRIBUTION_URL` — set to the CloudFront URL printed after deploying the content provider CDK stack

After the first run, copy `MANAGER_ARN`, `PAYMENT_CONNECTOR_ID`, and `PAYMENT_INSTRUMENT_ID`
from the Step 3 output back into `.env` to skip provisioning on subsequent runs.

### Step 2 — Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 3 — Run the notebook

```bash
jupyter notebook pay_for_content_browser.ipynb
```

Run all cells in order. The notebook will:
1. Load configuration and verify environment variables
2. Initialise all three boto3 clients
3. Provision the embedded wallet resource stack (once per user):
   CredentialProvider → PaymentManager → PaymentConnection → EmbeddedCryptoWallet Instrument
   — then pause for you to fund the wallet via WalletHub and the Circle faucet
3e. Verify wallet USDC balance via `GetPaymentInstrumentBalance` (ProcessPaymentRole)
4. Create a payment session with payment limits (operator-controlled)
5. Build a Strands agent with `AgentCoreBrowser` and `process_x402_payment`
6. Invoke the agent to retrieve a premium article
7. Verify the spend was recorded via `GetPaymentSession`
8. Cleanup — curtail session with minimum expiry

---

## Key Notes and Caveats

### Endpoints

The notebook constructs both endpoints from the AWS region you set in `AWS_REGION`:
- `CP_ENDPOINT` = `https://bedrock-agentcore-control.{region}.amazonaws.com` — credential provider, manager, connector
- `DP_ENDPOINT` = `https://bedrock-agentcore.{region}.amazonaws.com` — instrument, session, process payment

`CreatePaymentCredentialProvider` lives on the standard `bedrock-agentcore-control` endpoint.
A separate ACPS endpoint is not required.

### Embedded wallet — Coinbase CDP (provider-agnostic design)

This use case provisions an **embedded crypto wallet** via Coinbase CDP. AgentCore
creates and manages the on-chain wallet — you provide CDP API credentials, not a wallet
address. The design is provider-agnostic: swapping to **StripePrivy** requires only
changing the credential provider configuration in Step 3a and 3c; all agent logic and
payment tool code remain unchanged.

After CreatePaymentInstrument, Step 3 prints a **WalletHub URL**. Open this URL to:
- Log in with your `WALLET_EMAIL`
- Fund the wallet with testnet USDC via the Circle faucet (https://faucet.circle.com)
- Grant signing permission to AgentCore payments

> Coinbase embedded wallets are provisioned synchronously — no OTP step required.
> StripePrivy embedded wallets require OTP email verification during provisioning.

### Supported networks

| Network alias  | Chain ID                                   | Status         |
|:---------------|:-------------------------------------------|:---------------|
| `base-sepolia` | `eip155:84532`                             | Default; tested |
| `solana-devnet`| `solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1` | Placeholder; not yet tested |

Set `NETWORK` in `.env` to switch networks. Solana Devnet requires an extra `feePayer`
field in the payment proof — the notebook includes a comment for this.

### Testnet only

This use case targets testnet networks. There is no persistent merchant address
guaranteed by any party — if the content provider's wallet address changes, update
`PAY_TO` in the content provider deployment.

### DOM selectors are sample-specific

The element IDs used by the browser agent (`pay-btn`, `proof-input`, `verify-btn`,
`content`) are specific to the **demo content provider** in `content-provider/`.
Real x402 sites will have different selectors — the agent discovers payment form
elements dynamically using semantic cues (button text, input types, aria-labels)
rather than hardcoded IDs.

### Alternative: x402 via AgentCore Gateway

You can also access x402-protected endpoints directly via **Amazon Bedrock AgentCore
Gateway**, which handles the payment header exchange at the API level without a browser.
See the **Pay for Data** use case for that pattern.

---

## IAM Role Design

| Role | Operations | Denied |
|:-----|:-----------|:-------|
| `ControlPlaneRole` | `CreatePaymentCredentialProvider`, `CreatePaymentManager`, `CreatePaymentConnector`, `CreatePaymentInstrument` | `ProcessPayment`, session management |
| `ManagementRole` | `CreatePaymentSession`, `GetPaymentSession` | `ProcessPayment` |
| `ProcessPaymentRole` | `ProcessPayment`, `GetPaymentInstrumentBalance` | All setup and session management ops |

The notebook assumes all three roles via STS at startup. The agent only ever uses
`ProcessPaymentRole` credentials — it cannot modify its own session payment limits, create
new sessions, or access wallet credentials.

---

## Cleanup

The payment session created in Step 4 expires automatically after `SESSION_EXPIRY_MINUTES`
(60 minutes by default) and stops accepting payments — no API call required.

To tear down the IAM roles created by `setup_roles.sh`, delete the four
`AgentCorePayments*` roles from the IAM console or via the AWS CLI.
