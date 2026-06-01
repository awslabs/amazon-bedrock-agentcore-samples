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

## Running the Use Cases

```bash
cd pay-for-content-browser-use
pip install -r requirements.txt
bash setup_roles.sh        # once per account
cp .env.sample .env        # fill in values
python pay_for_content_browser.py
```

---

More use cases coming soon.
