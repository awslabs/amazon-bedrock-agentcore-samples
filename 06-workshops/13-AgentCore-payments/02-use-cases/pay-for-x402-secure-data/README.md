# Pay for Secure Data (x402)

## Overview

**Amazon Bedrock AgentCore payments** enables AI agents to make autonomous
payments for digital services. Agents never hold private keys or require
human approval for each transaction.

This use case builds a Strands agent that autonomously pays for **secure**
access to a metered x402 service — but only after an independent trust check
clears a guardrail. Before the agent pays a registered target x402 service, it
first pays **t54 x402-secure** to risk-score that exact endpoint. Only if the
score clears the configured threshold (and the endpoint is not flagged as a
scam) does the agent go on to pay the target service and return the content.
The included target is the **Heurist YahooFinanceAgent** market-data endpoint,
but the pattern is generic — register any x402 service.

Both the trust check and the target data call are paid x402 calls. When either
endpoint returns HTTP 402, the `AgentCorePaymentsPlugin` forwards the payment
requirement to AgentCore payments' `ProcessPayment` operation, receives a
signed proof, and retries the request with the proof attached. The agent is
designed never to touch a private key.

Internally, AgentCore payments manages the wallet, the signing keys, and the
on-chain settlement. The agent runtime holds no long-lived payment
credentials: the application supplies `user_id`, `payment_session_id`, and
`payment_instrument_id` **per invocation**, and the runtime uses a payment
execution role to call `ProcessPayment` within the session spending limit.

The trust decision is enforced **in code**, not by the model. A deterministic
gateway (`TrustedX402ServiceGateway`) blocks a target payment whenever the
trust result for that exact endpoint is missing, expired, below threshold,
scam-flagged, or URL-mismatched. The system prompt orders the two tools, but
the gateway is what makes the guardrail non-bypassable.

### Use Case Details

| Information         | Details                                                               |
|:--------------------|:----------------------------------------------------------------------|
| Use case type       | Trust-gated paid x402 service access with autonomous micropayment     |
| AgentCore components| Amazon Bedrock AgentCore payments, AgentCore Runtime                  |
| Wallet providers    | Coinbase CDP ✅                                                       |
| Payment protocol    | x402 (HTTP 402 Payment Required) on the wire                          |
| Guardrail service   | t54 x402-secure direct API                                            |
| Included target     | Heurist YahooFinanceAgent x402 endpoint                              |
| Agent type          | Single                                                                |
| Agentic Framework   | Strands Agents                                                        |
| LLM model           | Anthropic Claude Sonnet 4.5 (Amazon Bedrock, `us.` inference profile) |
| Example complexity  | Intermediate                                                          |
| SDK used            | boto3                                                                 |

### Architecture

Four parties participate in every trust-gated paid request:

1. **Strands agent** — calls exactly two tools: `check_x402_endpoint_trust`
   and `call_trusted_x402_service`. The `AgentCorePaymentsPlugin` intercepts
   HTTP 402 responses on both and handles the payment handshake transparently.
2. **t54 x402-secure** — a paid trust-scoring endpoint. The agent pays it to
   score the target endpoint before paying the target itself.
3. **Amazon Bedrock AgentCore payments** — receives `ProcessPayment`, returns
   a signed x402 proof using the wallet tied to the instrument (Coinbase CDP).
4. **Registered target x402 service** — the paid data endpoint (Heurist
   YahooFinanceAgent), reached only after the trust check passes.

Four IAM roles separate concerns operationally, following the **principle of
least privilege**: each role has only the permissions required for its
specific operation, with explicit `Deny` statements on actions reserved for
other roles:

- `AgentCoreX402SecureDataControlPlaneRole` — manages Manager, Connector, Credential Provider
- `AgentCoreX402SecureDataManagementRole` — manages Instrument and Session (explicit `Deny` on `ProcessPayment`)
- `AgentCoreX402SecureDataProcessPaymentRole` — signs payments and runs the agent runtime; reads Instrument and Session (explicit `Deny` on Instrument/Session management)
- `AgentCoreX402SecureDataResourceRetrievalRole` — assumed by AgentCore payments at runtime to retrieve credentials

`test/integration/setup-roles.sh` creates all four with the right policies. See
the public [IAM roles for AgentCore payments](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-iam-roles.html)
reference for the full policy details and an explanation of the
separation-of-duties model.

<div style="text-align:left">
    <img src="images/architecture_pay_for_x402_secure_data.png" alt="Pay for Secure Data (x402) architecture — a swimlane diagram across five lanes: Application backend, AgentCore Runtime container, Strands agent plus deterministic trust gate, External paid services, and AgentCore payments. The application backend sends a prompt plus payment context to the runtime's /invocations endpoint; a PaymentContext extractor reads the user id, session, and instrument, and a request-scoped trust-state ContextVar with a TTL is created. The Strands agent calls check_x402_endpoint_trust against the exact target URL; t54 x402-secure (POST /x402/tools/get_overall_score) returns HTTP 402, AgentCorePaymentsPlugin calls ProcessPayment to sign an x402 proof from the session spending limit and retries, and the trust result (overall_score, risk level, scam flag) is stored. TrustedX402ServiceGateway is a fail-closed guardrail with a Trust pass? decision: on fail it returns a blocked result with no target payment; on pass it calls the registered Heurist YahooFinanceAgent x402 service, which may also return HTTP 402 handled by the same plugin, and paid data is returned to the application with the trust result attached." width="85%"/>
</div>

**Numbered flow (matches the diagram)**

1. The **application backend** invokes **AgentCore Runtime** (`POST /invocations`) with a prompt plus `user_id`, `payment_session_id`, and `payment_instrument_id`.
2. The runtime's `PaymentContext` extractor reads that context, opens a **request-scoped trust state** (a `ContextVar` with a TTL), and starts the Strands agent turn.
3. The agent calls `check_x402_endpoint_trust` against the exact registered target endpoint URL.
4. **t54 x402-secure** (`POST /x402/tools/get_overall_score`) returns **HTTP 402** when payment is required; `AgentCorePaymentsPlugin` calls **AgentCore payments** `ProcessPayment`, attaches the signed x402 proof (drawn from the session spending limit), and retries the trust check.
5. The successful trust response (`overall_score`, `risk_level`, `is_scam`) is stored in the request-scoped trust state.
6. `TrustedX402ServiceGateway` (fail-closed) validates the requested `service_id`, `operation`, payload, and cached trust result before any target service payment.
7. If trust is missing, stale, low-score, scam-flagged, or URL-mismatched, the tool returns a **blocked** result and no target payment starts.
8. If trust passes, the gateway calls the registered target x402 service (**Heurist YahooFinanceAgent**).
9. The target service can also return **HTTP 402**; the same payments plugin calls `ProcessPayment`, attaches the signed proof, and retries.
10. Paid data is returned to the **application** with the trust result attached.

The management role creates payment sessions and instruments; the runtime
payment role only processes payments. Session spending limits and
payment-instrument scope are enforced by AgentCore payments, not by agent
prompt instructions. t54 x402-secure supplies the pre-payment trust signal, and
`call_trusted_x402_service` enforces the trust decision in code before a target
x402 payment can start — the prompt instructs the order, but the gateway blocks
missing, expired, low-score, scam, or URL-mismatched trust state
deterministically.

### Use Case Key Features

* Agent is designed not to hold private keys — AgentCore payments signs every
  charge via the configured `PaymentManager` and `PaymentConnector`
* Pre-payment trust guardrail — t54 x402-secure scores the target endpoint for
  quality, risk, and scam signals before the agent pays it
* Deterministic, code-enforced gate — `TrustedX402ServiceGateway` blocks
  missing, expired, low-score, scam, or URL-mismatched trust state before any
  target payment, independent of the model's prompt
* Human-controlled spending limit via `maxSpendAmount` on the payment session — one
  spending limit covers both the trust check and the target call
* IAM role separation: `ManagementRole` creates sessions, `ProcessPaymentRole`
  signs payments (explicit `Deny` in both directions, enforced by IAM rather
  than documentation)
* Per-invocation payment context — a single AgentCore Runtime deployment
  serves many users and sessions; identifiers travel on the request
* Full audit trail via `GetPaymentSession` — the operator sees exactly what
  the agent spent across both paid calls

---

## Payment Protocol Availability

AgentCore payments manages the wallet and signing keys behind a connector, so
the agent code does not change based on the wallet provider — the service picks
the right signer from the connector tied to the instrument. This use case wires
the **Coinbase CDP** provider.

| Wallet Provider | Connector Type | Status | Notes |
|:----------------|:---------------|:-------|:------|
| **Coinbase CDP** | `CoinbaseCDP` | ✅ Available | API Key ID, API Key Secret, Wallet Secret. **Enable "Delegated signing"** under Project → Wallet → Embedded Wallets → Policies (project layer), then grant the per-wallet delegation in the Coinbase Wallet Hub (§5) before use. |

---

## Prerequisites

- **AWS account** with Amazon Bedrock AgentCore payments available in your chosen region
- **Amazon Bedrock access** enabled for **Anthropic Claude Sonnet 4.5** in your chosen region (cross-region inference profile `us.anthropic.claude-sonnet-4-5-20250929-v1:0`)
- **Python 3.10+** with a Jupyter kernel. If you hit "Running cells requires the ipykernel package", install it once: `python3 -m pip install ipykernel==7.3.0 --user`. Any Jupyter frontend works — JupyterLab (4.0+), classic Jupyter Notebook (7.0+), VS Code, or Kiro.
- **AWS Command Line Interface (AWS CLI) v2** configured with credentials (`aws configure`)
- **AWS Cloud Development Kit (CDK) v2** installed globally (`npm install -g aws-cdk@2.1131.0`); used by §8 to deploy the agent runtime
- **Node.js 18+** — required by CDK
- **`jq`** — used by the IAM role setup script
- **AgentCore payments botocore service definitions** available to your boto3 install (so boto3 knows how to call the service). If your account is in the AgentCore payments preview, install the current control- and data-plane service models into `~/.aws/models`. An outdated model still exposes the operations but fails later on the `EMBEDDED_CRYPTO_WALLET` instrument type the live API requires. Verify with `aws bedrock-agentcore-control help` (should list `create-payment-manager`).
- **A Coinbase Developer Platform (CDP) account** — API Key ID, API Key Secret, Wallet Secret
- **A real, deliverable email** for `INSTRUMENT_EMAIL` (see [Security](#security)) — the per-wallet delegated-signing grant is completed by signing in to the Coinbase Wallet Hub with a one-time code sent to it
- **USDC on the settlement chain (Base)** funded to the embedded wallet §5 creates. Unlike samples that deploy their own testnet seller, this use case calls **live external x402 services** (t54 x402-secure and Heurist), which settle real payments. Keep the session spending limit small — see the [cost notice](#cleanup).

---

## Security

The use case relies on AgentCore Identity's **payment credential provider** to
manage wallet provider secrets. Once `CreatePaymentCredentialProvider` runs in
§4, AgentCore Identity stores the Coinbase CDP API keys and wallet secret in
**AWS Secrets Manager**, encrypts them with **AWS Key Management Service (KMS)**
keys, and surfaces only the secret ARN to your agents (see [Configure
credential provider](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/resource-providers.html)).
The agent runtime calls `GetResourcePaymentToken` at signing time to receive a
short-lived vendor-specific token; it never sees the raw API key or wallet
secret.

What AgentCore payments handles for you:

- **Secret storage** — wallet provider secrets land in AWS Secrets Manager
  under AgentCore Identity, encrypted with AWS-owned KMS keys (customer-managed
  KMS keys supported)
- **Secret retrieval** — agents call `GetResourcePaymentToken` and receive a
  vendor token. The agent runtime never receives the underlying API key or
  wallet secret
- **Audit trail** — every `ProcessPayment` call writes to AWS CloudTrail and to
  the AgentCore payments managed log group. Use `GetPaymentSession` for
  operator-visible spend totals
- **Spending limit enforcement** — the operator sets `maxSpendAmount` on the payment
  session. AgentCore payments rejects any `ProcessPayment` that would exceed it
- **IAM least privilege** — the four roles in §2 each receive only the actions
  and resources required for one operation. Cross-role permissions are
  explicitly denied (`ManagementRole` cannot call `ProcessPayment`,
  `ProcessPaymentRole` cannot manage sessions or instruments)

What you handle locally:

- **Initial credential paste** — Coinbase CDP secrets are pasted into `.env`
  once, before §4 runs. The notebook reads them only to call
  `CreatePaymentCredentialProvider`. After that call returns, the secrets are
  inside the AgentCore Identity-managed vault (Secrets Manager) and the local
  `.env` copies are no longer needed by the agent
- **Delegated signing (two one-time layers)** — Coinbase requires delegated
  signing at both the **project** layer (CDP Portal → Wallets → Non-custodial
  Wallet → Security, needs your account 2FA) and the **per-wallet** layer (the
  Coinbase Wallet Hub grant, completed by signing in with `INSTRUMENT_EMAIL`).
  Both are one-time. After both grants, the agent signs each payment
  autonomously within the session spending limit — no per-payment approval. If either
  layer is missing, `ProcessPayment` fails with *"Delegated signing grant is
  not active for the end user wallet."*
- **A real `INSTRUMENT_EMAIL`** — the embedded wallet links to this identity
  and the per-wallet grant sends a one-time code there. A placeholder like
  `alex@example.com` (a reserved, non-deliverable domain) makes the grant
  impossible; the notebook rejects `@example.com` addresses
- **Encryption in transit** — all calls to AgentCore payments, Amazon Bedrock,
  t54 x402-secure, and the target x402 service run over TLS (`https://`). The
  Dockerfile health check is the only HTTP URL and is loopback-only

> **Payment compliance:** This sample settles real USDC through third-party
> wallet and x402 services. If you process payments in production, review your
> obligations under the payment and financial regulations that apply to you
> (for example PCI-DSS where card data is involved) alongside the
> [AWS shared responsibility model](https://aws.amazon.com/compliance/shared-responsibility-model/)
> and [AWS compliance programs](https://aws.amazon.com/compliance/programs/).
> AgentCore payments and the wallet providers each own part of the settlement
> path; confirm the compliance posture of each before going live.

### Production hardening

This is an L100 tutorial. Before deploying anything resembling this sample to
production:

- **Drop `.env` after first run.** Once §4 has called
  `CreatePaymentCredentialProvider`, blank the secret values from `.env`.
  Subsequent runs read the credential provider ARN (non-sensitive) and the
  secrets stay in Secrets Manager
- **Use customer-managed KMS keys.** AgentCore Identity defaults to AWS-owned
  KMS keys; switch to customer-managed keys for additional audit and rotation
  control
- **Tighten IAM role wildcards.** Once Manager IDs are stable, replace
  `payment-manager/*` with the specific Manager ARN, or scope by tag
- **Switch the AgentCore Runtime to VPC mode** with private subnets, VPC
  endpoints for AWS APIs, and an egress allow-list restricted to the t54
  x402-secure and target x402 hosts (the tutorial uses `networkMode=PUBLIC`)
- **Keep the trust threshold and session spending limit tight.** Set
  `X402_TRUST_THRESHOLD` to the strictest value your workload tolerates and
  `PAYMENT_SESSION_MAX_SPEND_USD` to the smallest spending limit that covers a run
- **Pin the `bedrock-agentcore` Python SDK** to a specific version in
  production builds

---

## Running the Use Case

Before opening the notebook, create a Python virtual environment so dependency
installs and notebook state stay isolated from the global Python.

**Option 1 — Terminal (cross-platform)**

```bash
python3 -m venv .venv
source .venv/bin/activate    # On Windows: .venv\Scripts\activate
python3 -m pip install pip==26.1.2 ipykernel==7.3.0
python3 -m ipykernel install --user --name pay-for-x402-secure-data-venv --display-name "Python (pay-for-x402-secure-data-venv)"
```

**Option 2 — VS Code / Kiro**

1. Open `pay-for-x402-secure-data.ipynb`.
2. Choose the kernel selector in the top-right of the notebook (or the Python
   version indicator in the bottom status bar).
3. Choose **Python: Create Environment...**.
4. Choose **Venv**.
5. Pick a Python 3.10+ interpreter. The IDE creates `.venv/` and selects it
   automatically.
6. When prompted to install kernel dependencies (`ipykernel`), accept.

After the venv is active, open `pay-for-x402-secure-data.ipynb` and run cells
in order. The notebook handles dependency install, IAM role creation,
credential prompts, payment provisioning, a no-cost guardrail demo, the live
trust-gated run, optional runtime deploy, and teardown:

- §1 installs the Python dependencies from `requirements.txt`
- §2 creates the four IAM roles and interactively prompts for the Coinbase CDP credentials and a real `INSTRUMENT_EMAIL`
- §3 demonstrates the trust guardrail with **mocks** — no AWS calls and no money — so you can see the approve / low-score-block / scam-block decisions before spending anything
- §4 provisions a Credential Provider + Manager + Connector for Coinbase CDP
- §5 creates one `EMBEDDED_CRYPTO_WALLET` instrument and a spending-limit-capped payment session, then prints the delegated-signing + funding steps
- §6 builds the trust-gated Strands agent — two tools plus the `AgentCorePaymentsPlugin`, wrapped in request-scoped trust state
- §7 runs the agent **live** against t54 x402-secure and the target service (gated behind an explicit opt-in because it settles real USDC)
- §8 optionally deploys the agent to AgentCore Runtime via `agent/cdk/` and invokes it remotely with per-invocation payment context
- §9 inspects the data plane: GetPaymentSession, balance, ListPaymentInstruments, ListPaymentSessions
- §10 tears everything down: session, agent runtime (if §8 was run), and AgentCore payments resources (optional)

---

## Key Notes

- The agent runtime and payment resources deploy to the same region — set by
  `AWS_REGION` in `.env`.
- The trust check and the target call each settle a separate payment, so an
  **approved run spends twice**. The single payment session spending limit covers both.
- The guardrail is enforced by `TrustedX402ServiceGateway` in code, not by the
  prompt. It blocks a target payment whenever the cached trust result for that
  exact endpoint URL is missing, expired, below `X402_TRUST_THRESHOLD`,
  `is_scam`, or does not match the requested service's URL. With
  `X402_TRUST_FAIL_CLOSED=1` (default), a missing trust result blocks rather
  than allows.
- Trust results are **request-scoped**. A successful score for one invocation
  never authorizes a later invocation — each request opens a fresh trust state
  (`use_request_trust_state`).
- The t54 x402-secure client shapes its HTTP 402 into the
  `PAYMENT_REQUIRED: {statusCode, headers, body}` marker that the plugin's
  `GenericPaymentHandler` recognizes. A unit test runs the marker through the
  real handler so the contract cannot drift silently.
- The agent runtime holds no payment identifiers. `user_id`,
  `payment_session_id`, and `payment_instrument_id` arrive on each
  `/invocations` request (or as `X-Payment-*` / `X-User-Id` headers) so one
  deployment serves many users.
- To register a different target x402 service, add it to
  `agent/container/x402_service_registry.py` and point the agent at its
  `service_id`. The trust gate applies to every registered service uniformly.

---

## Cleanup

> ⚠️ **Cost notice:** This use case calls **live, paid external x402 services**.
> Every approved run settles **real USDC twice** — once for the t54 x402-secure
> trust check and once for the target data call. The AgentCore Runtime, Amazon
> ECR, AWS CodeBuild, and AgentCore payments resources also bill on
> per-request and per-resource models. Keep `PAYMENT_SESSION_MAX_SPEND_USD`
> small and run §10 of the notebook to tear everything down when you are done.

§10 of the notebook handles teardown end-to-end:

| Step | What it does | What it removes |
|------|--------------|-----------------|
| Revoke session | `DeletePaymentSession` on the session created in §5 | Active session spending limit (no undelete) |
| Tear down the agent runtime | `cdk destroy` on the agent CDK app (only if §8 was run) | AgentCore Runtime, Amazon ECR repository, AWS CodeBuild project, IAM execution role |
| Tear down AgentCore payments resources | Calls `DeletePaymentInstrument`, `DeletePaymentConnector`, `DeletePaymentManager`, `DeletePaymentCredentialProvider` in dependency order | All Manager / Connector / Instrument / Credential Provider resources created by §4 + §5 |
| Remove local build artifacts | Deletes `.venv/`, `agent/cdk/cdk.out/`, `agent/cdk/outputs.json`, `__pycache__/` | Local working-copy files only — no cloud resources |

The IAM roles created by `setup-roles.sh` in §2 have no standing cost and are
retained for re-runs. To delete them by hand:

```bash
for role in ControlPlaneRole ManagementRole ProcessPaymentRole ResourceRetrievalRole; do
    name="AgentCoreX402SecureData${role}"
    for policy in $(aws iam list-role-policies --role-name "$name" --query 'PolicyNames' --output text); do
        aws iam delete-role-policy --role-name "$name" --policy-name "$policy"
    done
    aws iam delete-role --role-name "$name"
done
```

CloudWatch log groups under `/aws/bedrock-agentcore/` and
`/bedrock-agentcore/payments/` are retained after teardown so you can review
historical traces. Delete them from the CloudWatch console if you want to clear
historical data.

### Manual cleanup (without the notebook)

If the notebook is unavailable, run the same teardown from a shell:

```bash
# 1. Destroy the agent runtime stack (only if §8 was run)
bash test/integration/destroy-agent.sh

# 2. AgentCore payments resources require boto3 calls — see §10 of the
#    notebook for the exact API sequence. Delete the instrument first,
#    then the connector, manager, and credential provider.
```

### Verify cleanup succeeded

Confirm no CloudFormation stacks remain:

```bash
aws cloudformation list-stacks \
    --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
    --query "StackSummaries[?starts_with(StackName, 'AgentCorePaymentsX402SecureData')].StackName"
```

The output should be empty.

Do not commit `.env`, live ARNs, payment IDs, wallet addresses, or payment
proofs.

---

## Conclusion

This use case demonstrates how Amazon Bedrock AgentCore payments enables an AI
agent to pay for a paid x402 service **safely** — gating every target payment
behind an independent, paid trust check without holding private keys or
requiring per-transaction human approval. The same agent settled two real x402
payments in sequence (the t54 x402-secure trust check and the Heurist target
call), while a deterministic in-code gateway guaranteed the target was never
paid on a missing, stale, low-score, or scam-flagged trust result.

Key takeaways:

- **Trust before spend** — the agent pays a scoring service to vet an endpoint
  before paying that endpoint, and the decision is enforced in code rather than
  by the model's prompt.
- **Separation of concerns** — IAM roles isolate session creation, payment
  signing, and credential retrieval. The trust boundary is enforced by IAM, not
  by code.
- **Spending limit control** — operators set a maximum spend per session. AgentCore
  Payments enforces it across both paid calls, and `GetPaymentSession` provides
  a full audit trail.
- **Wire format** — x402 (HTTP 402 Payment Required) is the open spec on the
  wire. The `AgentCorePaymentsPlugin` handles the protocol so the application
  code stays a normal tool call.

Use the [Learn more](#learn-more) links to go deeper, and adapt the trust-gated
pattern to your own paid-service integrations.

---

## Learn more

Public AgentCore payments documentation:

- [Overview](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments.html)
- [How it works](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-how-it-works.html)
- [Core concepts](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-concepts.html)
- [Prerequisites](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-prerequisites.html)
- [IAM roles](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-iam-roles.html)
- [Set up a credential provider](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-setup-credential-provider.html)
- [Create a payment manager](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-create-manager.html)
- [Create a payment instrument](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-create-instrument.html)
- [Create a payment session](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-create-session.html)
- [Process a payment](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-process-payment.html) — plugin reference, interrupt contract, network preferences, `auto_payment=False` for human-in-the-loop flows
- [Connect to Bazaar](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-connect-bazaar.html) — make a service discoverable through the AgentCore Registry

Announcement:
[Agents that transact — Introducing Amazon Bedrock AgentCore payments](https://aws.amazon.com/blogs/machine-learning/agents-that-transact-introducing-amazon-bedrock-agentcore-payments-built-with-coinbase-and-stripe/)
