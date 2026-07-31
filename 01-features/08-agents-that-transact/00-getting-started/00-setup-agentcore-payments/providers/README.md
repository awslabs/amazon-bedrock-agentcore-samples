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

The Coinbase helper opens the exact CDP Portal pages, consumes the two downloaded
credential files without printing their contents, verifies them with Coinbase's
official CDP CLI, and writes the values needed by AgentCore to `.env`.

## Coinbase CDP Setup Summary

Coinbase does not currently expose a supported OAuth or CLI bootstrap that can
mint a project's root API key and Wallet Secret. The project owner creates those
credentials in the portal; the helper automates the safe handoff from there.

1. Install the official CDP CLI: `npm install -g @coinbase/cdp-cli`
2. Run `python providers/coinbase_cdp_account_setup.py --open-portal`
3. Sign in to the CDP Portal in the browser tab that opens
4. Create and download a **Secret API Key** JSON file
5. Generate and download the **Wallet Secret** file
6. Return to the terminal and provide the two downloaded file paths

Delegated signing is a later, per-wallet consent step. After AgentCore creates
the embedded wallet, open the returned WalletHub `redirectUrl`, sign in as the
linked user, and grant signing permission.

The Wallet Secret is shown **only once**. Store both downloads in a secure
location and delete unnecessary copies after AgentCore has ingested them.

For a non-interactive import after downloading the files:

```bash
python providers/coinbase_cdp_account_setup.py \
  --api-key-file ~/Downloads/cdp_api_key.json \
  --wallet-secret-file ~/Downloads/cdp_wallet_secret.txt
```

The embedded wallet created by AgentCore must hold enough testnet USDC to pay
the x402 endpoint. For Base Sepolia, request free testnet USDC from
[Circle's faucet](https://faucet.circle.com/). Testnet USDC has no monetary
value, so no real Coinbase balance or purchase is required.

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
