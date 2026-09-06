from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from payment import PaymentConfig, X402PaymentClient


@dataclass
class FakeResponse:
    status_code: int
    text: str
    headers: dict[str, str] = field(default_factory=dict)


class FakeTransport:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.requests: list[dict[str, Any]] = []

    def get(self, url: str, headers: dict[str, str] | None = None) -> FakeResponse:
        self.requests.append({"url": url, "headers": headers})
        return self.responses.pop(0)


class FakeManager:
    def __init__(self) -> None:
        self.header_calls: list[dict[str, Any]] = []

    def generate_payment_header(self, **kwargs: Any) -> dict[str, str]:
        self.header_calls.append(kwargs)
        return {"PAYMENT-SIGNATURE": "proof"}

    def get_payment_session(self, payment_session_id: str, user_id: str) -> dict[str, Any]:
        return {
            "limits": {"maxSpendAmount": {"value": "0.25", "currency": "USD"}},
            "availableLimits": {"availableSpendAmount": {"value": "0.20", "currency": "USD"}},
            "expiryTimeInMinutes": 60,
            "paymentSessionId": payment_session_id,
            "userId": user_id,
        }


def config(**overrides: Any) -> PaymentConfig:
    values = {
        "manager_arn": "arn:manager",
        "instrument_id": "instrument",
        "session_id": "session",
        "user_id": "user",
        "region": "us-east-1",
        "allowed_hosts": frozenset({"merchant.example"}),
        "max_payment_attempts": 3,
    }
    values.update(overrides)
    return PaymentConfig(**values)


def public_resolver(_host: str, _port: int) -> list[str]:
    return ["8.8.8.8"]


def test_returns_free_content_without_payment() -> None:
    transport = FakeTransport([FakeResponse(200, '{"source":"public"}')])
    manager = FakeManager()
    client = X402PaymentClient(
        config(),
        manager,
        get=transport.get,
        resolver=public_resolver,
    )

    result = json.loads(client.fetch("https://merchant.example/data"))

    assert result["ok"] is True
    assert result["source_url"] == "https://merchant.example/data"
    assert result["payment_made"] is False
    assert manager.header_calls == []


def test_settles_402_and_uses_version_aware_sdk_header() -> None:
    challenge = json.dumps(
        {
            "x402Version": 2,
            "accepts": [{"network": "eip155:84532", "amount": "1000", "asset": "USDC"}],
        }
    )
    transport = FakeTransport(
        [
            FakeResponse(402, challenge, {"payment-required": "challenge"}),
            FakeResponse(200, '{"premium":"evidence"}'),
        ]
    )
    manager = FakeManager()
    client = X402PaymentClient(
        config(),
        manager,
        get=transport.get,
        resolver=public_resolver,
        token_factory=lambda: "stable-token",
    )

    result = json.loads(client.fetch("https://merchant.example/data"))

    assert result["payment_made"] is True
    assert result["payment_attempts"] == 1
    assert transport.requests[1]["headers"] == {"PAYMENT-SIGNATURE": "proof"}
    assert manager.header_calls[0]["client_token"] == "stable-token"


def test_reuses_idempotency_token_across_transient_402_retries() -> None:
    transport = FakeTransport(
        [
            FakeResponse(402, '{"x402Version":2,"accepts":[]}'),
            FakeResponse(402, '{"x402Version":2,"accepts":[]}'),
            FakeResponse(200, "paid"),
        ]
    )
    manager = FakeManager()
    client = X402PaymentClient(
        config(),
        manager,
        get=transport.get,
        resolver=public_resolver,
        token_factory=lambda: "one-token",
    )

    result = json.loads(client.fetch("https://merchant.example/data"))

    assert result["payment_attempts"] == 2
    assert [call["client_token"] for call in manager.header_calls] == [
        "one-token",
        "one-token",
    ]


def test_blocks_unapproved_hosts_before_network_access() -> None:
    transport = FakeTransport([])
    client = X402PaymentClient(
        config(),
        FakeManager(),
        get=transport.get,
        resolver=public_resolver,
    )

    result = json.loads(client.fetch("https://unapproved.example/data"))

    assert result["ok"] is False
    assert "not approved" in result["error"]
    assert transport.requests == []


def test_blocks_private_dns_results() -> None:
    transport = FakeTransport([])
    client = X402PaymentClient(
        config(),
        FakeManager(),
        get=transport.get,
        resolver=lambda _host, _port: ["127.0.0.1"],
    )

    result = json.loads(client.fetch("https://merchant.example/data"))

    assert result["ok"] is False
    assert "private or non-routable" in result["error"]
    assert transport.requests == []


def test_session_status_exposes_budget_not_resource_ids() -> None:
    client = X402PaymentClient(config(), FakeManager(), resolver=public_resolver)

    result = json.loads(client.session_status())

    assert result["maximum_spend"] == "0.25"
    assert result["available_spend"] == "0.20"
    assert "session" not in result
    assert "instrument" not in result
