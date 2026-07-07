# AgentCore Payments Setup

This directory contains optional helpers for creating the IAM roles and AgentCore Payments resources used by the sample.

The local unit tests do not require AWS access. Run these helpers only when you are ready to create resources in an AWS account enrolled in the AgentCore Payments private beta, with the current beta service model installed (see below).

## Safety Gate

Every script reads the sample-root `.env` file:

```bash
cd ..
cp .env.example .env
```

Before a script mutates AWS resources, it verifies the current AWS caller against this value and exits without printing account IDs or ARNs unless it matches:

```bash
CONFIRM_AWS_ACCOUNT_ID=<your-account-id>
```

This prevents accidental role or payment-resource creation in the wrong account.

## Service Model (Private Beta)

AgentCore Payments is a private beta. Its APIs are **not** in the public AWS SDK/CLI — no released `botocore` bundles them. AWS distributes the control- and data-plane service models with the beta materials; install the **current** ones into `~/.aws/models` (the beta package ships a `setup_model.sh` that does this):

```bash
# From the AgentCore Payments beta package:
bash setup_model.sh   # installs the bedrock-agentcore + bedrock-agentcore-control models into ~/.aws/models
```

Use the **current** model, not an older snapshot. The live API has migrated payment instruments to `EMBEDDED_CRYPTO_WALLET`; an outdated model still exposes the operations but fails later — `CreatePaymentInstrument` rejects the legacy `CRYPTO_WALLET` type, and `GetPaymentInstrument` returns `InternalServerException` ("Failed to retrieve payment instrument") for instruments created under the old schema.

Quick capability checks (should list `create-payment-manager` / `create-payment-instrument`):

```bash
aws bedrock-agentcore help >/dev/null
aws bedrock-agentcore-control help >/dev/null
```

## IAM Roles

Create or update the sample-scoped roles:

```bash
bash setup/setup_roles.sh
```

By default the scripts use this prefix:

```text
AgentCoreX402SecureData
```

Override `ROLE_NAME_PREFIX` in `.env` if you need a different role namespace.

`setup_roles.sh` derives a narrow trusted setup principal from the current caller. If the caller is not an IAM role or user you want in role trust policies, set:

```bash
TRUSTED_SETUP_PRINCIPAL_ARN=<specific-iam-role-or-user-arn>
```

The script writes `CONTROL_PLANE_ROLE_ARN`, `MANAGEMENT_ROLE_ARN`, `PROCESS_PAYMENT_ROLE_ARN`, and `RESOURCE_RETRIEVAL_ROLE_ARN` into the sample-root `.env`. It prints role names only, not ARN values.

Secrets Manager read access is not wildcarded by default. If your credential provider requires a known secret ARN, set this and rerun `setup_roles.sh`:

```bash
CREDENTIAL_PROVIDER_SECRET_ARN=<credential-provider-secret-arn>
```

## Payment Manager Resources

Create a Coinbase CDP credential provider, payment manager, and connector:

```bash
python -m pip install -r setup/requirements.txt
bash setup/setup_manager.sh
```

The setup manager stores wallet-provider credentials through AgentCore. Normal output is redacted and does not print raw request bodies, raw AWS responses, wallet addresses, account IDs, session IDs, instrument IDs, transactions, or payment proofs.

Set `SHOW_RESPONSE_KEYS=1` only for local troubleshooting when you need to see top-level AWS response keys. Values are still not printed.

## Payment Instrument and Session

Create the end user's embedded wallet instrument and a budgeted payment session:

```bash
bash setup/setup_instrument.sh
```

This provisions an `EMBEDDED_CRYPTO_WALLET` for `USER_ID` through the connector's Coinbase CDP credentials, opens a payment session capped by `PAYMENT_SESSION_MAX_SPEND_USD` / `PAYMENT_SESSION_EXPIRY_MINUTES`, and writes `PAYMENT_INSTRUMENT_ID`, `PAYMENT_SESSION_ID`, and `WALLET_ADDRESS` into the sample-root `.env`. Set `PAYMENT_INSTRUMENT_NETWORK` and `INSTRUMENT_EMAIL` first.

> **`INSTRUMENT_EMAIL` must be a real, deliverable address you control.** The embedded wallet links to this identity, and the per-wallet delegated-signing grant (below) is completed by signing in to the Coinbase WalletHub with a one-time code sent to it. A placeholder like `<user>@example.com` (a reserved, non-deliverable domain) makes the grant impossible, and `ProcessPayment` then fails with *"Delegated signing grant is not active for the end user wallet."* The setup script rejects `@example.com` addresses.

### Delegated signing — two one-time layers (both required)

Before the agent can settle a payment, delegated signing must be granted at **both** levels:

1. **Project policy** (once per Coinbase project): CDP Portal → **Wallets → Non-custodial Wallet → Security** → enable **Delegated signing**. This requires your account's 2-step verification.
2. **Per-wallet grant** (once per wallet): open the **Coinbase WalletHub** link the setup script prints, sign in with `INSTRUMENT_EMAIL` (one-time code), and **Grant signing delegation**.

Then fund the wallet (address saved to `.env` as `WALLET_ADDRESS`) with USDC on the configured network. After both grants, the agent signs every x402 payment autonomously within the session budget — no per-payment approval. If either layer is missing, `ProcessPayment` returns an `AccessDeniedException` naming which one.
