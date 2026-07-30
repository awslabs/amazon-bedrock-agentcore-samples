"""Run live model, merchant-challenge, and optional payment smoke tests."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
from typing import NoReturn

import httpx
from agents import Runner
from dotenv import load_dotenv

from paid_research.agent import build_agent
from paid_research.model_runtime import configure_model_runtime
from paid_research.x402 import X402PaymentClient


class DisabledPaymentClient:
    def fetch(self, _url: str) -> NoReturn:
        raise AssertionError("The model smoke test must not call the paid tool")

    def session_status(self) -> NoReturn:
        raise AssertionError("The model smoke test must not query payment state")


async def model_smoke() -> dict[str, str | bool | None]:
    runtime = configure_model_runtime()
    agent = build_agent(
        DisabledPaymentClient(),
        model=runtime.model,
        include_web_search=runtime.include_web_search,
    )
    result = await Runner.run(
        agent,
        "Do not call tools. Reply with exactly PAID_RESEARCH_MODEL_OK.",
    )
    output = str(result.final_output).strip()
    if output != "PAID_RESEARCH_MODEL_OK":
        raise RuntimeError(f"Unexpected model smoke-test output: {output!r}")
    return {
        "provider": runtime.provider,
        "model": runtime.model,
        "region": runtime.region,
        "web_search_enabled": runtime.include_web_search,
        "status": "passed",
    }


def merchant_challenge(url: str) -> dict[str, str | int | bool | None]:
    response = httpx.get(url, follow_redirects=False, timeout=30.0)
    if response.status_code != 402:
        raise RuntimeError(f"Expected HTTP 402 from test merchant, got {response.status_code}")

    try:
        body = response.json()
    except json.JSONDecodeError:
        body = {}
    version = body.get("x402Version") if isinstance(body, dict) else None
    payment_required = response.headers.get("payment-required")
    if version is None and payment_required:
        try:
            padding = "=" * (-len(payment_required) % 4)
            decoded = base64.b64decode(payment_required + padding)
            header_challenge = json.loads(decoded)
            version = header_challenge.get("x402Version")
        except (ValueError, json.JSONDecodeError):
            pass
    return {
        "status": "passed",
        "status_code": response.status_code,
        "x402_version": version,
        "has_payment_required_header": payment_required is not None,
    }


def payment_smoke(url: str) -> dict[str, str | int | bool | None]:
    result = json.loads(X402PaymentClient.from_env().fetch(url))
    if not result.get("ok") or not result.get("payment_made"):
        raise RuntimeError(f"Live payment smoke test failed: {result}")
    return {
        "status": "passed",
        "status_code": result.get("status_code"),
        "payment_made": result.get("payment_made"),
        "payment_attempts": result.get("payment_attempts"),
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Run paid-research live smoke tests")
    result.add_argument(
        "--url",
        default=os.getenv(
            "PAID_RESEARCH_URL",
            "https://sandbox.node4all.com/v1/x402-test",
        ),
    )
    result.add_argument(
        "--payment",
        action="store_true",
        help="Execute a real testnet payment; requires configured payment resources",
    )
    return result


def main() -> None:
    load_dotenv()
    args = parser().parse_args()
    report = {
        "model": asyncio.run(model_smoke()),
        "merchant_challenge": merchant_challenge(args.url),
    }
    if args.payment:
        report["payment"] = payment_smoke(args.url)
    else:
        report["payment"] = {"status": "skipped", "reason": "--payment was not supplied"}
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
