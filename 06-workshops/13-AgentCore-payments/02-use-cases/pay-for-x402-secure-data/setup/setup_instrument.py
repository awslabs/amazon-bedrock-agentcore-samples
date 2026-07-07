#!/usr/bin/env python3
"""Create the EMBEDDED_CRYPTO_WALLET payment instrument and a budgeted payment session.

Run this after ``setup/setup_manager.py`` has created the credential provider, payment
manager, and connector. It provisions an embedded Coinbase CDP wallet for ``USER_ID``,
opens a time- and amount-bounded payment session, prints the one-time Coinbase WalletHub
funding + delegated-signing link, and writes ``PAYMENT_INSTRUMENT_ID`` /
``PAYMENT_SESSION_ID`` / ``WALLET_ADDRESS`` back to the sample-root ``.env``.

Delegated signing is a ONE-TIME grant: once enabled, the agent signs every x402 payment
autonomously within the session budget, with no per-payment approval.

Requires the CURRENT AgentCore Payments beta data-plane service model in ``~/.aws/models``
(the one that supports ``EMBEDDED_CRYPTO_WALLET``). See ``setup/README.md``.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any

from botocore.exceptions import ClientError

from setup_manager import (
    assume_role,
    boto3_session,
    get_role_arn,
    maybe_print_response_keys,
    optional_endpoint,
    require_confirmed_account,
    require_env,
    role_name,
    update_env_file,
)


def client_token() -> str:
    return f"{uuid.uuid4()}-{uuid.uuid4().hex[:8]}"


def embedded_wallet_supported(dp_client: Any) -> bool:
    """Return True when the loaded service model exposes EMBEDDED_CRYPTO_WALLET."""
    shape = dp_client.meta.service_model.operation_model("CreatePaymentInstrument").input_shape.members[
        "paymentInstrumentType"
    ]
    enum = getattr(shape, "enum", None) or shape.metadata.get("enum", [])
    return "EMBEDDED_CRYPTO_WALLET" in (enum or [])


def wait_for_instrument_active(dp_client: Any, **kwargs: str) -> dict[str, Any]:
    """Poll GetPaymentInstrument until the instrument leaves the CREATING state."""
    detail: dict[str, Any] = {}
    for _ in range(12):
        detail = dp_client.get_payment_instrument(**kwargs)["paymentInstrument"]
        if detail.get("status") not in (None, "CREATING"):
            break
        time.sleep(5)
    return detail


def main() -> None:
    manager_arn = require_env("MANAGER_ARN")
    connector_id = require_env("PAYMENT_CONNECTOR_ID")
    user_id = os.environ.get("USER_ID", "test-user-x402-secure-data")
    email = os.environ.get("INSTRUMENT_EMAIL", "").strip()
    if not email or email.lower().endswith("@example.com"):
        raise SystemExit(
            "INSTRUMENT_EMAIL must be a REAL address you can receive email at. The embedded "
            "wallet links to this identity, and the per-wallet delegated-signing grant is "
            "completed by signing in to the Coinbase WalletHub with a one-time code sent to "
            "this address. A placeholder like <user>@example.com (a reserved, non-deliverable "
            "domain) makes the grant impossible, and ProcessPayment then fails with "
            "'Delegated signing grant is not active for the end user wallet'."
        )
    network = os.environ.get("PAYMENT_INSTRUMENT_NETWORK", "ETHEREUM")
    max_spend = os.environ.get("PAYMENT_SESSION_MAX_SPEND_USD", "1.0")
    expiry_minutes = int(os.environ.get("PAYMENT_SESSION_EXPIRY_MINUTES", "60"))

    base_session = boto3_session()
    require_confirmed_account(base_session)

    management_role_arn = get_role_arn(base_session, role_name("MANAGEMENT_ROLE_NAME", "ManagementRole"))
    management_session = assume_role(
        base_session,
        management_role_arn,
        f"x402-secure-data-instrument-{uuid.uuid4().hex[:8]}",
    )
    dp_client = management_session.client(
        "bedrock-agentcore",
        **optional_endpoint("PAYMENTS_DP_ENDPOINT", "DP_ENDPOINT"),
    )

    if not embedded_wallet_supported(dp_client):
        raise SystemExit(
            "The local AgentCore Payments data-plane service model does not support "
            "EMBEDDED_CRYPTO_WALLET. Install the CURRENT beta model into ~/.aws/models "
            "(see setup/README.md), then re-run this script."
        )

    print("Creating AgentCore Payments instrument and session with redacted output.")
    instrument_response = dp_client.create_payment_instrument(
        paymentManagerArn=manager_arn,
        paymentConnectorId=connector_id,
        userId=user_id,
        paymentInstrumentType="EMBEDDED_CRYPTO_WALLET",
        paymentInstrumentDetails={
            "embeddedCryptoWallet": {
                "network": network,
                "linkedAccounts": [{"email": {"emailAddress": email}}],
            }
        },
        clientToken=client_token(),
    )
    maybe_print_response_keys("CreatePaymentInstrument", instrument_response)
    instrument_id = instrument_response["paymentInstrument"]["paymentInstrumentId"]
    print("Created payment instrument (embedded crypto wallet).")

    detail = wait_for_instrument_active(
        dp_client,
        paymentManagerArn=manager_arn,
        paymentConnectorId=connector_id,
        paymentInstrumentId=instrument_id,
        userId=user_id,
    )
    wallet = detail.get("paymentInstrumentDetails", {}).get("embeddedCryptoWallet", {})
    wallet_address = wallet.get("walletAddress", "")
    redirect_url = wallet.get("redirectUrl")

    session_response = dp_client.create_payment_session(
        paymentManagerArn=manager_arn,
        userId=user_id,
        expiryTimeInMinutes=expiry_minutes,
        limits={"maxSpendAmount": {"value": str(max_spend), "currency": "USD"}},
        clientToken=client_token(),
    )
    maybe_print_response_keys("CreatePaymentSession", session_response)
    session_id = session_response["paymentSession"]["paymentSessionId"]
    print(f"Created payment session (budget ${max_spend} USD, expiry {expiry_minutes} min).")

    update_env_file(
        {
            "PAYMENT_INSTRUMENT_ID": instrument_id,
            "PAYMENT_SESSION_ID": session_id,
            "WALLET_ADDRESS": wallet_address,
        }
    )
    print("Updated .env with PAYMENT_INSTRUMENT_ID, PAYMENT_SESSION_ID, WALLET_ADDRESS.")

    print("\nOne-time onboarding (required before the agent can pay). Delegated signing has")
    print("TWO layers and BOTH must be satisfied:")
    print(
        "  1. PROJECT policy (once per Coinbase project): CDP Portal -> Wallets -> "
        "Non-custodial Wallet -> Security -> enable 'Delegated signing' (requires your "
        "account 2FA)."
    )
    if redirect_url:
        print(
            f"  2. PER-WALLET grant (once per wallet): open the WalletHub URL, sign in with\n"
            f"     INSTRUMENT_EMAIL ({email}) using the one-time code, and Grant signing delegation:\n"
            f"     {redirect_url}"
        )
    else:
        print(
            "  2. PER-WALLET grant: WalletHub URL not ready yet; re-run to fetch it. Sign in "
            "with INSTRUMENT_EMAIL and Grant signing delegation."
        )
    if network == "ETHEREUM":
        fund_chain = (
            "Base mainnet (CDP's ETHEREUM network settles USDC on Base for x402) — "
            "Base Sepolia fallback via https://faucet.circle.com/"
        )
    elif network == "SOLANA":
        fund_chain = "Solana (Devnet fallback via https://faucet.circle.com/)"
    else:
        fund_chain = network
    print(f"  3. Fund the wallet (address saved to .env as WALLET_ADDRESS) with USDC on {fund_chain}.")
    print(
        "After both layers are granted, the agent signs every x402 payment autonomously "
        "within the session budget — no per-payment approval."
    )


if __name__ == "__main__":
    try:
        main()
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "Unknown")
        raise SystemExit(f"AWS API error during instrument/session setup: {code}. See local AWS logs.") from exc
