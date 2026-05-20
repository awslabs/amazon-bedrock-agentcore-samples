# Wallet Provider Setup

Before running Tutorial 00, choose a wallet provider and run its setup script to save credentials to `.env`.

## Providers

| Provider | Script | Credentials Written to .env |
|----------|--------|------------------------------|
| Coinbase CDP | `coinbase_cdp_account_setup.py` | `COINBASE_API_KEY_ID`, `COINBASE_API_KEY_SECRET`, `COINBASE_WALLET_SECRET` |
| Stripe (Privy) | `stripe_privy_account_setup.py` | `PRIVY_APP_ID`, `PRIVY_APP_SECRET`, `PRIVY_AUTHORIZATION_ID`, `PRIVY_AUTHORIZATION_PRIVATE_KEY` |

Run only one provider setup. If you want both providers (for Tutorial 06 multi-agent), run both.

## Running

```bash
pip install -r providers/requirements.txt

# Option A: Coinbase CDP
python providers/coinbase_cdp_account_setup.py

# Option B: Stripe (Privy)
python providers/stripe_privy_account_setup.py
```

Each script prints step-by-step instructions for the manual browser steps, then prompts for the credentials to save to `.env`.

## Coinbase CDP Setup Summary

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
