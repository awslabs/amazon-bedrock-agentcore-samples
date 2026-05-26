# Use Cases

Real-world use cases that demonstrate **Amazon Bedrock AgentCore payments** in action. Each use case is a standalone sample with its own Python scripts, environment configuration, and supporting infrastructure.

## Available Use Cases

### [Pay for Content (Browser Use)](pay-for-content-browser-use/)

An AI agent built with **Strands Agents** and **AgentCoreBrowser** autonomously navigates a paywalled website, reads the x402 payment requirement from the page DOM, processes a payment via AgentCore payments, and returns the unlocked content. No private keys held by the agent, no human involvement in the payment step.

**Highlights**
- Browser-based x402 flow (DOM-embedded payment requirement, not HTTP 402 interception)
- IAM role separation between session management and payment execution
- Embedded wallet provisioning via Coinbase CDP
- Deployable CDK content-provider stack included for end-to-end testing
- Full observability via AgentCore payments dashboard (vended log delivery)
- Deployed to AgentCore runtime via AgentCore CLI

---

### [Pay for API](pay-for-api-agent/)

An AI agent built with **Strands Agents** autonomously pays for metered access to an HTTP API through AgentCore payments. The seller is a "Fun Facts" Amazon API Gateway and AWS Lambda service deployed via AWS CDK that charges $0.01 per call and accepts payment on either EVM or Solana. When the agent hits HTTP 402, the `AgentCorePaymentsPlugin` forwards the requirement to AgentCore payments, attaches the signed proof, and retries. The agent's tool code stays a plain `http_request` call.

**Highlights**
- HTTP 402 interception via `AgentCorePaymentsPlugin` (no browser, no manual handshake)
- Multi-provider: the same agent code runs against Coinbase CDP and Stripe via Privy
- Multi-network: EVM (Base Sepolia) and Solana (Solana Devnet) on testnets
- Four IAM roles enforce separation of duties between control plane, management, payment signing, and credential retrieval
- Self-contained: `pay_for_api.py` provisions the AgentCore payments stack inline and deploys the seller from an included CDK app
- AgentCore Runtime deploy with CloudWatch Transaction Search and the GenAI Observability dashboard

## Running the Use Cases

Pay for Content (Browser Use):

```bash
cd pay-for-content-browser-use
pip install -r requirements.txt
bash setup_roles.sh        # once per account
cp .env.sample .env        # fill in values
python pay_for_content_browser.py
```

Pay for API:

```bash
cd pay-for-api-agent
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp env-sample.txt .env                 # fill in values
bash test/integration/setup-roles.sh   # once per account
bash test/integration/setup-env.sh     # generates USER_ID
python pay_for_api.py
```

---

More use cases coming soon.
