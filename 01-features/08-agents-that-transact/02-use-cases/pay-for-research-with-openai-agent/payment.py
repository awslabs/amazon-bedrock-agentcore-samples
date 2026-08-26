"""Thin OpenAI Agents SDK adapter for AgentCore Payments."""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

MAX_BODY_CHARS = 100_000
GetRequest = Callable[[str, dict[str, str] | None], Any]
Resolver = Callable[[str, int], Sequence[str]]


def _http_get(url: str, headers: dict[str, str] | None = None) -> httpx.Response:
    """Issue a cookie-free GET without following redirects."""
    with httpx.Client(cookies=None, follow_redirects=False, timeout=30.0) as client:
        return client.get(url, headers=headers)


def _resolve(hostname: str, port: int) -> Sequence[str]:
    return [entry[4][0] for entry in socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)]


@dataclass(frozen=True)
class PaymentConfig:
    manager_arn: str
    instrument_id: str
    session_id: str
    user_id: str
    allowed_hosts: frozenset[str]
    region: str = "us-east-1"
    max_payment_attempts: int = 5

    @classmethod
    def from_env(cls) -> PaymentConfig:
        env_names = {
            "manager_arn": "PAYMENT_MANAGER_ARN",
            "instrument_id": "PAYMENT_INSTRUMENT_ID",
            "session_id": "PAYMENT_SESSION_ID",
            "user_id": "PAYMENT_USER_ID",
        }
        values = {field: os.getenv(name, "").strip() for field, name in env_names.items()}
        missing = [env_names[field] for field, value in values.items() if not value]
        if missing:
            raise ValueError("Missing payment configuration: " + ", ".join(missing))

        allowed_hosts = frozenset(
            host.strip().lower().rstrip(".")
            for host in os.getenv("PAID_RESEARCH_ALLOWED_HOSTS", "").split(",")
            if host.strip()
        )
        if not allowed_hosts:
            raise ValueError("PAID_RESEARCH_ALLOWED_HOSTS must contain an exact host")

        attempts = int(os.getenv("X402_MAX_PAYMENT_ATTEMPTS", "5"))
        if not 1 <= attempts <= 10:
            raise ValueError("X402_MAX_PAYMENT_ATTEMPTS must be between 1 and 10")

        return cls(
            **values,
            allowed_hosts=allowed_hosts,
            region=os.getenv("AWS_REGION", "us-east-1"),
            max_payment_attempts=attempts,
        )


class X402PaymentClient:
    """Fetch one approved source through a budget-bounded payment session."""

    def __init__(
        self,
        config: PaymentConfig,
        payment_manager: Any,
        *,
        get: GetRequest = _http_get,
        resolver: Resolver = _resolve,
        token_factory: Callable[[], str] | None = None,
    ) -> None:
        self.config = config
        self.payment_manager = payment_manager
        self.get = get
        self.resolver = resolver
        self.token_factory = token_factory or (lambda: str(uuid.uuid4()))

    @classmethod
    def from_env(cls) -> X402PaymentClient:
        from bedrock_agentcore.payments import PaymentManager

        config = PaymentConfig.from_env()
        return cls(
            config,
            PaymentManager(
                payment_manager_arn=config.manager_arn,
                region_name=config.region,
            ),
        )

    @staticmethod
    def _json(**values: Any) -> str:
        return json.dumps(values, default=str, sort_keys=True)

    def _validate_url(self, url: str) -> str | None:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname:
            return "Paid research requires an HTTPS URL with a hostname"
        if parsed.username or parsed.password:
            return "URLs containing credentials are not allowed"

        hostname = parsed.hostname.lower().rstrip(".")
        if hostname not in self.config.allowed_hosts:
            return f"Host is not approved for paid research: {hostname}"

        try:
            addresses = self.resolver(hostname, parsed.port or 443)
        except OSError:
            return "Could not resolve the merchant hostname"
        if not addresses:
            return "Merchant hostname resolved to no addresses"
        if any(not ipaddress.ip_address(address).is_global for address in addresses):
            return "Merchant hostname resolves to a private or non-routable address"
        return None

    def fetch(self, url: str) -> str:
        """GET an approved URL, settle a 402, and return structured JSON."""
        if error := self._validate_url(url):
            return self._json(ok=False, source_url=url, error=error)

        response = self.get(url, None)
        if response.status_code != 402:
            return self._json(
                ok=200 <= response.status_code < 300,
                source_url=url,
                status_code=response.status_code,
                body=response.text[:MAX_BODY_CHARS],
                payment_made=False,
            )

        client_token = self.token_factory()
        for attempt in range(1, self.config.max_payment_attempts + 1):
            try:
                payment_header = self.payment_manager.generate_payment_header(
                    payment_instrument_id=self.config.instrument_id,
                    payment_session_id=self.config.session_id,
                    user_id=self.config.user_id,
                    client_token=client_token,
                    payment_required_request={
                        "statusCode": response.status_code,
                        "headers": dict(response.headers),
                        "body": response.text,
                    },
                )
                if not payment_header:
                    raise ValueError("AgentCore returned an empty payment header")
                response = self.get(url, payment_header)
            except Exception as exc:  # noqa: BLE001 - SDK exposes provider-specific exceptions.
                return self._json(
                    ok=False,
                    source_url=url,
                    status_code=402,
                    error=f"Payment failed: {type(exc).__name__}: {exc}",
                    payment_attempts=attempt,
                )

            if response.status_code != 402:
                paid = 200 <= response.status_code < 300
                return self._json(
                    ok=paid,
                    source_url=url,
                    status_code=response.status_code,
                    body=response.text[:MAX_BODY_CHARS],
                    payment_made=paid,
                    payment_attempts=attempt,
                )

        return self._json(
            ok=False,
            source_url=url,
            status_code=402,
            error="Merchant still returned 402 after the bounded settlement retries",
            payment_made=False,
            payment_attempts=self.config.max_payment_attempts,
        )

    def session_status(self) -> str:
        """Return budget status without exposing wallet or session identifiers."""
        session = self.payment_manager.get_payment_session(
            payment_session_id=self.config.session_id,
            user_id=self.config.user_id,
        )
        maximum = session.get("limits", {}).get("maxSpendAmount", {})
        available = session.get("availableLimits", {}).get("availableSpendAmount", {})
        return self._json(
            maximum_spend=maximum.get("value"),
            available_spend=available.get("value"),
            currency=available.get("currency") or maximum.get("currency"),
            expiry_time_in_minutes=session.get("expiryTimeInMinutes"),
        )
