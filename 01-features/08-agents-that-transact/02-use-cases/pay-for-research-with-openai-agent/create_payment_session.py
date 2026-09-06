"""Create a short-lived AgentCore payment session for one research run."""

from __future__ import annotations

import argparse
import os
import uuid
from decimal import Decimal, InvalidOperation

from bedrock_agentcore.payments import PaymentManager
from dotenv import load_dotenv


def parse_budget(raw: str) -> str:
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError("budget must be a decimal amount") from exc
    if value <= 0:
        raise argparse.ArgumentTypeError("budget must be greater than zero")
    return format(value.quantize(Decimal("0.01")), "f")


def parse_expiry_minutes(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expiry must be a whole number of minutes") from exc
    if not 15 <= value <= 480:
        raise argparse.ArgumentTypeError("expiry must be between 15 and 480 minutes")
    return value


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget", type=parse_budget, default="0.25")
    parser.add_argument("--expiry-minutes", type=parse_expiry_minutes, default=60)
    args = parser.parse_args()

    manager_arn = os.environ["PAYMENT_MANAGER_ARN"]
    user_id = os.environ["PAYMENT_USER_ID"]
    region = os.getenv("AWS_REGION", "us-east-1")
    manager = PaymentManager(payment_manager_arn=manager_arn, region_name=region)
    session = manager.create_payment_session(
        user_id=user_id,
        limits={"maxSpendAmount": {"value": args.budget, "currency": "USD"}},
        expiry_time_in_minutes=args.expiry_minutes,
        client_token=str(uuid.uuid4()),
    )

    session_id = session["paymentSessionId"]
    print(f"Created session with a ${args.budget} cap for {args.expiry_minutes} minutes.")
    print(f"export PAYMENT_SESSION_ID={session_id}")


if __name__ == "__main__":
    main()
