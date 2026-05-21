# AgentCore payments — Getting Started Tutorials

Step-by-step Python scripts for building payment-enabled AI agents with **Amazon Bedrock AgentCore payments**.

AgentCore payments handles payment orchestration for the x402 protocol, configurable payment limits, and third-party wallet integration with Coinbase CDP and Stripe (Privy) stablecoin wallets.

> **Testnet only.** All tutorials use Base Sepolia (Ethereum) or Solana Devnet with free USDC from [faucet.circle.com](https://faucet.circle.com/). Testnet USDC has no real-world value.

## Top-level layout

| Folder | What's inside |
|--------|---------------|
| [`00-setup-agentcore-payments/`](00-setup-agentcore-payments/) | Create IAM roles, PaymentManager, Connector, embedded wallet, and a budgeted PaymentSession |
| [`01-agents-payments-and-limits/`](01-agents-payments-and-limits/) | Strands and LangGraph agents that pay x402 endpoints automatically with budget enforcement |
| [`02-deploy-to-agentcore-runtime/`](02-deploy-to-agentcore-runtime/) | Package and deploy a payment agent to AgentCore runtime with role separation and observability |
| [`03-user-onboarding-wallet-funding/`](03-user-onboarding-wallet-funding/) | User onboarding, wallet funding, delegation, balance checks, multi-network instruments |
| [`04-agent-with-coinbase-bazaar-via-gateway/`](04-agent-with-coinbase-bazaar-via-gateway/) | Discover 10,000+ paid MCP tools via AgentCore gateway and pay on call |
| [`05-agent-with-browser-tool-pay-for-content/`](05-agent-with-browser-tool-pay-for-content/) | Intercept 402 paywalls in a browser session and pay for web content |
| [`06-multi-agent-payment-orchestrator/`](06-multi-agent-payment-orchestrator/) | Multiple agents with separate wallets, per-agent budgets, and runtime deploy |

## Shared files

| File | Purpose |
|------|---------|
| `utils.py` | IAM role creation (`setup_payment_roles()`), config persistence, observability setup, display helpers |
| `.env` | Shared config created by Tutorial 00, loaded by all downstream tutorials (git-ignored) |

## Choose your path

### Path A: Single provider (Tutorials 00–06)

```
1. Pick ONE provider and run its setup script:
      providers/coinbase_cdp_account_setup.py   ← writes Coinbase keys to .env
   OR providers/stripe_privy_account_setup.py    ← writes Privy keys to .env

2. Run Tutorial 00 (setup_agentcore_payments.py)
      Creates IAM roles, PaymentManager, Connector, Instrument, Session
      Writes resource IDs back to .env

3. Run Tutorials 01–06 in any order
      Each loads .env and uses the resources Tutorial 00 created
```

### Path B: Multi-provider (Tutorial 06)

```
1. Run BOTH provider setup scripts
2. Run multi_provider_setup.py instead of Tutorial 00
      Creates one PaymentManager with two Connectors (Coinbase + Privy)
3. Run Tutorial 06
```

## AgentCore payments features → tutorial mapping

| Feature | Description | Tutorials |
|---------|-------------|-----------|
| Payment processing | x402 protocol orchestration, transaction signing, proof generation | 01, 02, 04, 05, 06 |
| Payment limits | Session budgets (`maxSpendAmount`), expiry, overspend rejection | 00, 01, 03, 06 |
| Wallet integration | Coinbase CDP and Stripe (Privy) embedded wallets, delegation, funding | 00, 03, 06 |
| Endpoint discoverability | Coinbase x402 Bazaar via AgentCore gateway, MCP tool search | 04 |
| observability | AgentCore observability (vended logs, traces via CloudWatch) | 00, 02, 06 |

## Prerequisites

- Python 3.10+
- AWS CLI configured (`aws sts get-caller-identity` to verify)
- AWS account with access to AgentCore payments
- Wallet provider credentials (Coinbase CDP or Stripe/Privy) — see Tutorial 00

## Running the Python Scripts

```bash
pip install -r 00-setup-agentcore-payments/requirements.txt

# Provider setup (pick one)
python 00-setup-agentcore-payments/providers/coinbase_cdp_account_setup.py
# OR
python 00-setup-agentcore-payments/providers/stripe_privy_account_setup.py

# Tutorial 00
python 00-setup-agentcore-payments/setup_agentcore_payments.py

# Tutorial 01
python 01-agents-payments-and-limits/strands_payment_agent.py
python 01-agents-payments-and-limits/langgraph_payment_agent.py

# Tutorial 02
python 02-deploy-to-agentcore-runtime/deploy_payment_agent.py

# Tutorial 03
python 03-user-onboarding-wallet-funding/user_onboarding.py

# Tutorial 04
python 04-agent-with-coinbase-bazaar-via-gateway/bazaar_gateway_agent.py

# Tutorial 05
python 05-agent-with-browser-tool-pay-for-content/browser_paywall_payments.py

# Tutorial 06
python 06-multi-agent-payment-orchestrator/multi_agent_payments.py
```

## Cleanup

> **Warning:** Cleanup is irreversible. Run after completing all tutorials.

1. Run the cleanup section in `setup_agentcore_payments.py` to delete the Payment Manager and all child resources.
2. Delete the four IAM roles from the IAM console.
3. Delete CloudWatch log groups: `/aws/vendedlogs/bedrock-agentcore/<manager-id>`.
4. For runtime deployments: `cd PaymentAgent && agentcore remove all -y`
