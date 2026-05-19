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

---

More use cases coming soon.
