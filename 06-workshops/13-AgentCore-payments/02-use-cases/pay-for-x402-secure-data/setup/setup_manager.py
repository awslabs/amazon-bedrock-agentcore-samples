#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

SAMPLE_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = Path(os.environ.get("ENV_FILE", SAMPLE_ROOT / ".env"))

if ENV_FILE.exists():
    load_dotenv(ENV_FILE)


def require_env(key: str) -> str:
    value = os.environ.get(key, "").strip()
    if not value or value.startswith("<"):
        raise SystemExit(f"Missing or placeholder value for {key} in {ENV_FILE}")
    return value


def optional_endpoint(name: str, fallback: str | None = None) -> dict[str, str]:
    endpoint = os.environ.get(name) or (os.environ.get(fallback) if fallback else None)
    return {"endpoint_url": endpoint} if endpoint else {}


def boto3_session() -> boto3.Session:
    kwargs: dict[str, str] = {"region_name": AWS_REGION}
    profile = os.environ.get("AWS_PROFILE", "").strip()
    if profile:
        kwargs["profile_name"] = profile
    return boto3.Session(**kwargs)


def require_confirmed_account(session: boto3.Session) -> str:
    identity = session.client("sts").get_caller_identity()
    account_id = identity["Account"]
    if os.environ.get("CONFIRM_AWS_ACCOUNT_ID") != account_id:
        raise SystemExit(
            "CONFIRM_AWS_ACCOUNT_ID does not match the current AWS caller. "
            f"Update {ENV_FILE} before mutating AWS resources."
        )
    return account_id


def role_name(key: str, suffix: str) -> str:
    prefix = os.environ.get("ROLE_NAME_PREFIX", "AgentCoreX402SecureData")
    return os.environ.get(key, f"{prefix}{suffix}")


def get_role_arn(session: boto3.Session, name: str) -> str:
    try:
        return session.client("iam").get_role(RoleName=name)["Role"]["Arn"]
    except ClientError as exc:
        raise SystemExit(f"Missing IAM role {name}. Run setup/setup_roles.sh first.") from exc


def assume_role(session: boto3.Session, role_arn: str, session_name: str) -> boto3.Session:
    creds = session.client("sts").assume_role(
        RoleArn=role_arn,
        RoleSessionName=session_name,
    )["Credentials"]
    session_kwargs = {
        "aws_access_key_id": creds["AccessKeyId"],
        "aws_secret_access_key": creds["SecretAccessKey"],
        "aws_session_token": creds["SessionToken"],
        "region_name": AWS_REGION,
    }
    return boto3.Session(**session_kwargs)


def check_payments_model_available(session: boto3.Session) -> None:
    """Verify the AgentCore Payments service model is installed and loadable.

    AgentCore Payments (private beta) ships as a botocore service model distributed
    with the beta materials, not through the public AWS SDK — no released botocore
    bundles it. Install the CURRENT beta control- and data-plane models into
    ~/.aws/models before running setup (see setup/README.md). An outdated model still
    exposes these operations but fails later on EMBEDDED_CRYPTO_WALLET.
    """
    client = session.client(
        "bedrock-agentcore-control",
        **optional_endpoint("PAYMENTS_CP_ENDPOINT", "CP_ENDPOINT"),
    )
    if not hasattr(client, "create_payment_manager"):
        raise SystemExit(
            "AgentCore Payments control-plane operations are unavailable. Install the "
            "current beta service models into ~/.aws/models (see setup/README.md), then re-run."
        )


def safe_name(prefix: str) -> str:
    suffix = uuid.uuid4().hex[:8]
    candidate = f"{prefix}{suffix}"
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]{0,47}$", candidate):
        raise SystemExit(f"Generated invalid AgentCore name: {candidate}")
    return candidate


def update_env_file(values: dict[str, str]) -> None:
    existing = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
    lines = existing.splitlines()
    seen: set[str] = set()
    updated: list[str] = []

    for line in lines:
        if "=" not in line or line.lstrip().startswith("#"):
            updated.append(line)
            continue
        key = line.split("=", 1)[0]
        if key in values:
            updated.append(f"{key}={values[key]}")
            seen.add(key)
        else:
            updated.append(line)

    for key, value in values.items():
        if key not in seen:
            updated.append(f"{key}={value}")

    ENV_FILE.write_text("\n".join(updated) + "\n", encoding="utf-8")


def maybe_print_response_keys(label: str, response: dict[str, Any]) -> None:
    if os.environ.get("SHOW_RESPONSE_KEYS") == "1":
        print(f"{label} response keys: {', '.join(sorted(response.keys()))}")


AWS_REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-west-2"


def main() -> None:
    provider_key_id = require_env("COINBASE_API_KEY_ID")
    provider_key_secret = require_env("COINBASE_API_KEY_SECRET")
    provider_wallet_secret = require_env("COINBASE_WALLET_SECRET")

    base_session = boto3_session()
    require_confirmed_account(base_session)
    check_payments_model_available(base_session)

    control_role_name = role_name("CONTROL_PLANE_ROLE_NAME", "ControlPlaneRole")
    retrieval_role_name = role_name("RESOURCE_RETRIEVAL_ROLE_NAME", "ResourceRetrievalRole")
    control_role_arn = get_role_arn(base_session, control_role_name)
    retrieval_role_arn = get_role_arn(base_session, retrieval_role_name)

    control_session = assume_role(
        base_session,
        control_role_arn,
        f"x402-secure-data-setup-{uuid.uuid4().hex[:8]}",
    )
    identity_client = control_session.client(
        "bedrock-agentcore-control",
        **optional_endpoint("CREDENTIAL_PROVIDER_ENDPOINT", "CP_ENDPOINT"),
    )
    payments_client = control_session.client(
        "bedrock-agentcore-control",
        **optional_endpoint("PAYMENTS_CP_ENDPOINT", "CP_ENDPOINT"),
    )

    credential_provider_name = safe_name("CoinbaseCdp")
    manager_name = os.environ.get("DEFAULT_PAYMENT_MANAGER_NAME") or safe_name("PaymentManager")
    connector_name = os.environ.get("DEFAULT_PAYMENT_CONNECTOR_NAME") or safe_name("CoinbaseConnector")

    provider_configuration = {
        "coinbaseCdpConfiguration": {
            "apiKeyId": provider_key_id,
            "apiKeySecret": provider_key_secret,
            "walletSecret": provider_wallet_secret,
        }
    }

    print("Creating AgentCore Payments resources with redacted output.")
    credential_response = identity_client.create_payment_credential_provider(
        name=credential_provider_name,
        credentialProviderVendor="CoinbaseCDP",
        providerConfigurationInput=provider_configuration,
    )
    maybe_print_response_keys("CreatePaymentCredentialProvider", credential_response)
    credential_provider_arn = credential_response["credentialProviderArn"]
    print("Created credential provider.")

    manager_response = payments_client.create_payment_manager(
        name=manager_name,
        authorizerType="AWS_IAM",
        roleArn=retrieval_role_arn,
    )
    maybe_print_response_keys("CreatePaymentManager", manager_response)
    manager_id = manager_response["paymentManagerId"]
    manager_arn = manager_response["paymentManagerArn"]
    print("Created payment manager.")

    connector_response = payments_client.create_payment_connector(
        paymentManagerId=manager_id,
        name=connector_name,
        type="CoinbaseCDP",
        credentialProviderConfigurations=[{"coinbaseCDP": {"credentialProviderArn": credential_provider_arn}}],
    )
    maybe_print_response_keys("CreatePaymentConnector", connector_response)
    connector_id = connector_response["paymentConnectorId"]
    print("Created payment connector.")

    update_env_file(
        {
            "MANAGER_ARN": manager_arn,
            "PAYMENT_CONNECTOR_ID": connector_id,
        }
    )
    print(f"Updated {ENV_FILE} with MANAGER_ARN and PAYMENT_CONNECTOR_ID.")


if __name__ == "__main__":
    try:
        main()
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "Unknown")
        raise SystemExit(f"AWS API error during setup: {code}. See local AWS logs for details.") from exc
