# Use Cases

Real-world use cases that demonstrate **Amazon Bedrock AgentCore payments** in action. Each use case is a standalone sample with its own notebook, environment configuration, and supporting infrastructure.

## Available use cases

### [Pay for Data (Heurist)](pay-for-data/)

A finance research agent built with **Strands Agents** that calls paid [Heurist](https://heurist.xyz) x402 endpoints for real-time prices, SEC filings, and macro indicators. The `AgentCorePaymentsPlugin` intercepts HTTP 402 responses, asks the AgentCore payment manager to generate a payment proof against the configured payment instrument and payment session, and retries — tool code stays an ordinary `http_request` call. Data is analyzed in AgentCore Code Interpreter and exported as charts and reports.

**Highlights**
- HTTP 402 payment processing via `AgentCorePaymentsPlugin` — no manual payment code in tools
- Embedded wallet (Coinbase CDP) with USDC as the settlement asset
- AgentCore Code Interpreter for pandas/matplotlib analysis and artifact export
- **Real x402 settlement on Base mainnet against the live [Heurist mesh](https://mesh.heurist.xyz/x402/agents?details=true) registry** — paid calls move actual USDC on-chain

---

More use cases coming soon.
