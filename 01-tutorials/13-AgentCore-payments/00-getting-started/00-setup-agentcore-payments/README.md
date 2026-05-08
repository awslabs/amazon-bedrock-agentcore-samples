# Set Up AgentCore payments

## Overview

This tutorial walks you through the complete setup of Amazon Bedrock AgentCore payments using the AWS SDK (boto3). You'll create IAM roles, configure wallet credentials, and provision the payment stack — everything needed before building payment-enabled agents.

AgentCore payments is wallet-provider agnostic. This tutorial covers both Coinbase CDP and Stripe (Privy) providers.

### Resource hierarchy

One PaymentManager per application. Connectors and instruments are child resources:

```
PaymentManager (1 per app — holds auth config + service role)
  ├── Connector: CoinbaseCDP (links to credential provider)
  │    └── Instrument (embedded wallet per user per network)
  ├── Connector: StripePrivy (links to credential provider)
  │    └── Instrument (embedded wallet per user per network)
  └── Session (budget + expiry, works with any instrument)
```

You don't need separate managers per wallet provider. One manager, multiple connectors. The session budget applies regardless of which instrument the agent uses.

### Tutorial Details

| Information         | Details                                                    |
|:--------------------|:-----------------------------------------------------------|
| Tutorial type       | Task-based                                                 |
| Agent type          | N/A (setup only)                                           |
| Agentic Framework   | N/A                                                        |
| LLM model           | N/A                                                        |
| Tutorial components | IAM roles, Payment Manager, Connector, Instrument, Session |
| Tutorial vertical   | Cross-vertical                                             |
| Example complexity  | Easy                                                       |
| SDK used            | boto3 (AWS SDK)                                            |

### Tutorial Key Features

* IAM role separation (4 roles: ControlPlane, Management, ProcessPayment, ResourceRetrieval)
* Control Plane setup: Credential Provider → Payment Manager → Payment Connector
* Data Plane setup: Payment Instrument (wallet) → Payment Session (budget)
* Support for both Coinbase CDP and Stripe (Privy) wallet providers
* Wallet funding instructions (testnet USDC)
* Complete cleanup

## Prerequisites

* Python 3.10+
* AWS credentials configured (`aws sts get-caller-identity` to verify)
* AWS account allowlisted for AgentCore payments preview
* For Coinbase: CDP API keys from https://portal.cdp.coinbase.com/
* For Stripe (Privy): Developer account from https://dashboard.privy.io/

## Manual Steps (actions outside the notebook)

Most of this tutorial is automated (run cells top to bottom). Three steps require action outside the notebook:

| When | What | Where | Time |
|------|------|-------|------|
| **Before running** | Get wallet provider credentials | Run `providers/coinbase_cdp_account_setup.ipynb` or `providers/stripe_privy_account_setup.ipynb` | ~15 min |
| **Step 7b** | Fund wallet with testnet USDC | [faucet.circle.com](https://faucet.circle.com/) → paste wallet address → request 10 USDC | ~2 min |
| **Step 7b** | Delegate signing permission | **Coinbase:** CDP Portal → Wallets → Embedded Wallet → Policies → enable Delegated Signing. **Privy:** Privy reference frontend at localhost:3000 → log in → choose Connect agent | ~5 min |

Without the funding and delegation steps, `ProcessPayment` will fail in Tutorial 01. The notebook prints a clear ✋ ACTION callout when you reach Step 7b.

## Cleanup

When done with all tutorials, clean up resources to avoid charges:

1. Run the cleanup cell at the bottom of `setup_agentcore_payments.ipynb` to delete the Payment Manager and all child resources.
2. Delete the four IAM roles from the IAM console if no longer needed.
3. Delete CloudWatch log groups: `/aws/vendedlogs/bedrock-agentcore/<manager-id>`.

Payment sessions expire automatically after their configured `expiryTimeInMinutes`.

## Conclusion

This tutorial sets up the complete AgentCore payments infrastructure including IAM roles, wallet credentials, and the payment stack. All downstream tutorials (01–07) depend on these resources.
