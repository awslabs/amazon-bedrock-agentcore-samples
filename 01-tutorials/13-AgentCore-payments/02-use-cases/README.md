# Use Cases

Real-world use cases that demonstrate **Amazon Bedrock AgentCore payments** in action. Each use case is a standalone sample with its own notebook, environment configuration, and supporting infrastructure.

## Available use cases

### [Pay for Content (Browser Use)](pay-for-content-browser-use/)

An AI agent built with **Strands Agents** and **AgentCoreBrowser** autonomously navigates a paywalled website, reads the x402 payment requirement from the page DOM, processes a payment via AgentCore payments, and returns the unlocked content. No private keys held by the agent, no human involvement in the payment step.

**Highlights**
- Browser-based x402 flow (DOM-embedded payment requirement, not HTTP 402 interception)
- IAM role separation between session management and payment execution
- Embedded wallet provisioning via Coinbase CDP
- Deployable CDK content-provider stack included for end-to-end testing
- Tested end-to-end on Base Sepolia testnet

### [Pay for Data (Heurist)](pay-for-data/)

A finance research agent built with **Strands Agents** that calls paid [Heurist](https://heurist.xyz) x402 endpoints for real-time prices, SEC filings, and macro indicators. The `AgentCorePaymentsPlugin` intercepts HTTP 402 responses, asks the AgentCore payment manager to generate a payment proof against the configured payment instrument and payment session, and retries — tool code stays an ordinary `http_request` call. Data is analyzed in AgentCore Code Interpreter and exported as charts and reports.

**Highlights**
- HTTP 402 payment processing via `AgentCorePaymentsPlugin` — no manual payment code in tools
- Embedded wallet (Coinbase CDP) with USDC as the settlement asset
- AgentCore Code Interpreter for pandas/matplotlib analysis and artifact export
- Public PyPI dependencies only (`bedrock-agentcore==1.9.0`) — no bundled or file-based SDK components
- Targets x402 on Base mainnet (Heurist endpoints settle on Base)

---

More use cases coming soon.
