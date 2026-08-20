# Wallet Provider Setup

Before running Tutorial 00, choose a wallet provider and run its setup script to save credentials to `.env`.

## Providers

| Provider | Script | Credentials Written to .env |
|----------|--------|------------------------------|
| Coinbase CDP | `coinbase_cdp_account_setup.py` | `COINBASE_API_KEY_ID`, `COINBASE_API_KEY_SECRET`, `COINBASE_WALLET_SECRET` |
| Stripe (Privy) | `stripe_privy_account_setup.py` | `PRIVY_APP_ID`, `PRIVY_APP_SECRET`, `PRIVY_AUTHORIZATION_ID`, `PRIVY_AUTHORIZATION_PRIVATE_KEY` |

Run only one provider setup. If you want both providers (for Tutorial 07 multi-agent), run both.

## Running

```bash
pip install -r providers/requirements.txt

# Option A: Coinbase CDP
python providers/coinbase_cdp_account_setup.py

# Option B: Stripe (Privy)
python providers/stripe_privy_account_setup.py
```

Each script prints step-by-step instructions for the manual browser steps, then prompts for the credentials to save to `.env`.

See the detailed instructions to be followed [here](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-create-manager.html)


## Important Note  

To create a Coinbase payment connector, your account must have an active AWS Marketplace subscription to the Coinbase Wallets for AgentCore Payments listing. With this subscription, your Coinbase wallet usage charges are consolidated into your monthly AWS bill based on Coinbase’s pricing on the Coinbase website. There are no additional charges or obligations for the subscription. If the subscription is missing, CreatePaymentConnector fails with a SubscriptionRequiredException (HTTP 403). This requirement applies only to Coinbase; other providers, such as Stripe (Privy), are not affected. For more information, see Subscribe to Coinbase Wallets for AgentCore Payments in AWS Marketplace.

## Coinbase CDP Setup Summary


If you choose Coinbase, choose how to provide the credentials for the payment auth:

Quick create configurations - recommended — Quick create allows you to link to your Coinbase CDP account and let AgentCore payments create the credentials for you without leaving the AgentCore console. It opens a window to sign up or sign in to your Coinbase CDP account. The service then provisions the Coinbase CDP API key and Wallet secret and stores them as a payment auth on your behalf. You do not generate or paste any keys.
Quick create does not support linking to an existing project with a Wallet Secret.

Watch the detailed video for the steps here in this blog[https://aws.amazon.com/blogs/machine-learning/amazon-bedrock-agentcore-payments-is-now-generally-available-enabling-agents-to-transact-safely-and-autonomously-at-scale/] 

Use existing configurations — Provide Coinbase CDP credentials that you generated yourself in the Coinbase Developer Platform.

1. Create a Coinbase account at [coinbase.com](https://coinbase.com/)
2. Enable CDP at [portal.cdp.coinbase.com](https://portal.cdp.coinbase.com/)
3. Create an API Key → copy `API Key ID` + `API Key Secret`
4. Under Wallets → ServerWallet → copy `Wallet Secret`
5. Enable **Delegated Signing** under Wallets → Embedded Wallet → Policies
6. Run `coinbase_cdp_account_setup.py` and paste the three values when prompted

The Wallet Secret is shown **only once** — save it before closing the dialog.

## Stripe (Privy) Setup Summary

1. Create a Privy app at [dashboard.privy.io](https://dashboard.privy.io)
2. Enable Email + EVM wallets + SVM (Solana) wallets in app settings
3. Generate an authorization key under Wallet Infrastructure → Authorization
4. Clone and run the Privy reference frontend (`git clone https://github.com/privy-io/aws-agentcore-sdk`)
5. Run `stripe_privy_account_setup.py` and follow the prompts

The Privy reference frontend must be running at `http://localhost:3000` for the
end-user consent step in Tutorial 00 Step 7b (after the wallet is created).

## After Provider Setup

Return to `setup_agentcore_payments.py` — it reads `CREDENTIAL_PROVIDER_TYPE` from `.env`
automatically and uses the correct provider.
