"""A framework-agnostic, read-only x402 client backed by AgentCore Payments."""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx


class ResponseLike(Protocol):
    status_code: int
    headers: Mapping[str, str]
    text: str


class PaymentManagerLike(Protocol):
    def generate_payment_header(
        self,
        *,
        payment_instrument_id: str,
        payment_session_id: str,
        payment_required_request: dict[str, Any],
        user_id: str | None = None,
        client_token: str | None = None,
    ) -> dict[str, str]: ...

    def get_payment_session(
        self,
        payment_session_id: str,
        user_id: str | None = None,
    ) -> dict[str, Any]: ...


class Transport(Protocol):
    def get(self, url: str, *, headers: Mapping[str, str] | None = None) -> ResponseLike: ...


Resolver = Callable[[str, int], Sequence[str]]


def _system_resolver(hostname: str, port: int) -> Sequence[str]:
    return [entry[4][0] for entry in socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)]


@dataclass(frozen=True)
class PaymentConfig:
    manager_arn: str
    instrument_id: str
    session_id: str
    user_id: str
    region: str
    allowed_hosts: frozenset[str]
    max_payment_attempts: int = 5
    max_body_chars: int = 100_000

    @classmethod
    def from_env(cls) -> PaymentConfig:
        values = {
            "manager_arn": os.getenv("PAYMENT_MANAGER_ARN", "").strip(),
            "instrument_id": os.getenv("PAYMENT_INSTRUMENT_ID", "").strip(),
            "session_id": os.getenv("PAYMENT_SESSION_ID", "").strip(),
            "user_id": os.getenv("PAYMENT_USER_ID", "").strip(),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            env_names = {
                "manager_arn": "PAYMENT_MANAGER_ARN",
                "instrument_id": "PAYMENT_INSTRUMENT_ID",
                "session_id": "PAYMENT_SESSION_ID",
                "user_id": "PAYMENT_USER_ID",
            }
            raise ValueError(
                "Missing payment configuration: " + ", ".join(env_names[name] for name in missing)
            )

        allowed_hosts = frozenset(
            host.strip().lower().rstrip(".")
            for host in os.getenv("PAID_RESEARCH_ALLOWED_HOSTS", "").split(",")
            if host.strip()
        )
        if not allowed_hosts:
            raise ValueError("PAID_RESEARCH_ALLOWED_HOSTS must contain at least one exact host")

        attempts = int(os.getenv("X402_MAX_PAYMENT_ATTEMPTS", "5"))
        if attempts < 1 or attempts > 10:
            raise ValueError("X402_MAX_PAYMENT_ATTEMPTS must be between 1 and 10")

        return cls(
            **values,
            region=os.getenv("AWS_REGION", "us-east-1"),
            allowed_hosts=allowed_hosts,
            max_payment_attempts=attempts,
        )


class HttpxTransport:
    """Issue each request with a fresh cookie-free client and no redirects."""

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self.timeout_seconds = timeout_seconds

    def get(self, url: str, *, headers: Mapping[str, str] | None = None) -> httpx.Response:
        with httpx.Client(
            cookies=None,
            follow_redirects=False,
            timeout=self.timeout_seconds,
            verify=True,
        ) as client:
            return client.get(url, headers=headers)


class X402PaymentClient:
    """Fetch approved paid research while keeping signing outside model context."""

    def __init__(
        self,
        config: PaymentConfig,
        payment_manager: PaymentManagerLike,
        *,
        transport: Transport | None = None,
        resolver: Resolver = _system_resolver,
        token_factory: Callable[[], str] | None = None,
    ) -> None:
        self.config = config
        self.payment_manager = payment_manager
        self.transport = transport or HttpxTransport()
        self.resolver = resolver
        self.token_factory = token_factory or (lambda: str(uuid.uuid4()))

    @classmethod
    def from_env(cls) -> X402PaymentClient:
        from bedrock_agentcore.payments import PaymentManager

        config = PaymentConfig.from_env()
        manager = PaymentManager(
            payment_manager_arn=config.manager_arn,
            region_name=config.region,
        )
        return cls(config, manager)

    def _validate_url(self, url: str) -> str | None:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            return "Only HTTPS URLs are allowed"
        if parsed.username or parsed.password:
            return "URLs containing credentials are not allowed"
        if not parsed.hostname:
            return "URL must include a hostname"

        hostname = parsed.hostname.lower().rstrip(".")
        if hostname not in self.config.allowed_hosts:
            return f"Host is not approved for paid research: {hostname}"

        try:
            addresses = self.resolver(hostname, parsed.port or 443)
        except OSError:
            return "Could not resolve the merchant hostname"
        if not addresses:
            return "Merchant hostname resolved to no addresses"

        for address in addresses:
            ip = ipaddress.ip_address(address)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_unspecified
            ):
                return "Merchant hostname resolves to a private or non-routable address"
        return None

    def _body(self, response: ResponseLike) -> str:
        return response.text[: self.config.max_body_chars]

    @staticmethod
    def _challenge_summary(response: ResponseLike) -> dict[str, Any]:
        try:
            body = json.loads(response.text)
        except (json.JSONDecodeError, TypeError):
            return {"x402_version": None, "accepts_count": None}
        if not isinstance(body, dict):
            return {"x402_version": None, "accepts_count": None}

        accepts = body.get("accepts")
        first = accepts[0] if isinstance(accepts, list) and accepts else {}
        if not isinstance(first, dict):
            first = {}
        return {
            "x402_version": body.get("x402Version"),
            "accepts_count": len(accepts) if isinstance(accepts, list) else None,
            "network": first.get("network"),
            "asset": first.get("asset"),
            "quoted_amount": first.get("amount") or first.get("maxAmountRequired"),
        }

    @staticmethod
    def _json(payload: dict[str, Any]) -> str:
        return json.dumps(payload, default=str, sort_keys=True)

    def fetch(self, url: str) -> str:
        """GET an approved URL, settle an x402 challenge, and return structured JSON."""
        validation_error = self._validate_url(url)
        if validation_error:
            return self._json({"ok": False, "source_url": url, "error": validation_error})

        response = self.transport.get(url)
        if 300 <= response.status_code < 400:
            return self._json(
                {
                    "ok": False,
                    "source_url": url,
                    "status_code": response.status_code,
                    "error": "Redirects are not followed by the paid research tool",
                }
            )
        if response.status_code != 402:
            return self._json(
                {
                    "ok": 200 <= response.status_code < 300,
                    "source_url": url,
                    "status_code": response.status_code,
                    "body": self._body(response),
                    "payment_made": False,
                }
            )

        challenge = self._challenge_summary(response)
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
                response = self.transport.get(url, headers=payment_header)
            except Exception as exc:  # Payment SDK exposes provider-specific exception types.
                return self._json(
                    {
                        "ok": False,
                        "source_url": url,
                        "status_code": 402,
                        "error": f"Payment failed: {type(exc).__name__}: {exc}",
                        "challenge": challenge,
                        "payment_attempts": attempt,
                    }
                )

            if response.status_code != 402:
                return self._json(
                    {
                        "ok": 200 <= response.status_code < 300,
                        "source_url": url,
                        "status_code": response.status_code,
                        "body": self._body(response),
                        "payment_made": 200 <= response.status_code < 300,
                        "payment_attempts": attempt,
                        "challenge": challenge,
                    }
                )

        return self._json(
            {
                "ok": False,
                "source_url": url,
                "status_code": 402,
                "error": "Merchant still returned 402 after the bounded settlement retries",
                "payment_made": False,
                "payment_attempts": self.config.max_payment_attempts,
                "challenge": challenge,
            }
        )

    def session_status(self) -> str:
        """Return a minimal budget view without exposing wallet or session identifiers."""
        session = self.payment_manager.get_payment_session(
            payment_session_id=self.config.session_id,
            user_id=self.config.user_id,
        )
        maximum = session.get("limits", {}).get("maxSpendAmount", {})
        available = session.get("availableLimits", {}).get("availableSpendAmount", {})
        return self._json(
            {
                "maximum_spend": maximum.get("value"),
                "available_spend": available.get("value"),
                "currency": available.get("currency") or maximum.get("currency"),
                "expiry_time_in_minutes": session.get("expiryTimeInMinutes"),
                "updated_at": session.get("updatedAt"),
            }
        )
