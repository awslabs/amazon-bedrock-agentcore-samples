# Agents That Transact — Amazon Bedrock AgentCore payments

Amazon Bedrock AgentCore payments is a fully managed service that enables microtransaction payments in AI agents to access paid APIs, MCP servers, and content. AI agents increasingly handle complex tasks by calling APIs, accessing MCP servers, and interacting with other agents. As more services monetize through pay-per-use models, developers face challenges integrating payments into agentic workflows. Transactions are typically microtransactions (often under $1 or fractions of a cent), making traditional payment methods cost-prohibitive due to high minimum transaction fees. Meanwhile, content providers and publishers are introducing paywalls for AI agents to access their content. AgentCore payments provides a suite of developer-friendly capabilities that help you develop solutions to enable secure, instant payments to paid services using stablecoin, open protocols like x402 for cost-effective microtransactions, and configurable guardrails to help control agent spending. This can reduce developer effort from months to days.

![AgentCore payments](00-getting-started/00-setup-agentcore-payments/images/main-image.png)

> **Preview** — AgentCore payments is currently available as a preview. Features and APIs may change before general availability.

> **Testnet only.** All samples use Base Sepolia (Ethereum) or Solana Devnet with free USDC from [faucet.circle.com](https://faucet.circle.com/). Testnet USDC has no real-world value.

## Start here

New? Begin with [`00-getting-started/00-setup-agentcore-payments/`](00-getting-started/00-setup-agentcore-payments/) to create IAM roles and the payment stack that all other tutorials depend on.

## Top-level layout

| Folder | What's inside |
|--------|---------------|
| [`00-getting-started/`](00-getting-started/) | Seven step-by-step tutorials covering setup → local agents → runtime deploy → wallet ops → gateway → browser payments → multi-agent orchestration |
| [`02-use-cases/`](02-use-cases/) | Real-world end-to-end use cases deployed on AgentCore runtime |

## How this tree is organized

Tutorials in `00-getting-started/` build on each other — start with Tutorial 00 which provisions the payment stack, then run any of 01–06 in the order that fits your use case. `02-use-cases/` contains production-style deployments that demonstrate complete end-to-end payment flows.

## Finding things

- **Payment stack setup** → `00-getting-started/00-setup-agentcore-payments/`
- **Strands agent with automatic payments** → `00-getting-started/01-agents-payments-and-limits/strands_payment_agent.py`
- **LangGraph agent with payments** → `00-getting-started/01-agents-payments-and-limits/langgraph_payment_agent.py`
- **Deploy payment agent to runtime** → `00-getting-started/02-deploy-to-agentcore-runtime/`
- **Wallet lifecycle (fund, delegate, balance)** → `00-getting-started/03-user-onboarding-wallet-funding/`
- **Discover paid tools via gateway** → `00-getting-started/04-agent-with-coinbase-bazaar-via-gateway/`
- **Browser + payment pattern** → `00-getting-started/05-agent-with-browser-tool-pay-for-content/`
- **Multi-agent with per-agent budgets** → `00-getting-started/06-multi-agent-payment-orchestrator/`
- **End-to-end browser paywall use case** → `02-use-cases/pay-for-content-browser-use/`

## Resources

- [AgentCore payments documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments.html)
- [Launch blog post](https://aws.amazon.com/blogs/machine-learning/agents-that-transact-introducing-amazon-bedrock-agentcore-payments-built-with-coinbase-and-stripe/)
- [Coinbase announcement](https://www.coinbase.com/en-ca/blog/introducing-amazon-bedrock-agentcore-payments-powered-by-x402-and-coinbase)
- [Stripe announcement](https://stripe.com/newsroom/news/aws-stripe-agentcore-privy)

## Prerequisites

- Python 3.10+
- AWS CLI configured (`aws sts get-caller-identity` to verify)
- AWS account with access to AgentCore payments preview
- Wallet provider credentials — Coinbase CDP or Stripe (Privy) — see `00-getting-started/00-setup-agentcore-payments/providers/`

## Running the Python Scripts

```bash
pip install -r 00-getting-started/00-setup-agentcore-payments/requirements.txt

# Tutorial 00 — one-time payment stack setup
python 00-getting-started/00-setup-agentcore-payments/setup_agentcore_payments.py

# Tutorial 01 — Strands agent with automatic payments
python 00-getting-started/01-agents-payments-and-limits/strands_payment_agent.py

# Tutorial 01 — LangGraph agent with payments
python 00-getting-started/01-agents-payments-and-limits/langgraph_payment_agent.py
```

## Security

- All tutorials use **testnet only** (Base Sepolia / Solana Devnet). No real funds are involved.
- Never commit `.env` files or private keys. Use AWS Secrets Manager for production credentials.
- Follow IAM least-privilege: separate ControlPlaneRole, ManagementRole, and ProcessPaymentRole.
