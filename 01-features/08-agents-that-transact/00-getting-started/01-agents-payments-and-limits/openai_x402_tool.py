"""AgentCore Payments adapter for OpenAI Agents SDK x402 tools."""

import ipaddress
import json
import os
import socket
import uuid
from urllib.parse import urlparse

import httpx
from bedrock_agentcore.payments import PaymentManager

MAX_PAYMENT_ATTEMPTS = int(os.getenv("X402_MAX_PAYMENT_ATTEMPTS", "5"))


def _validate_url(url):
    """Reject non-HTTPS and private or internal network addresses."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return "Only HTTPS URLs are supported for payment requests"
    try:
        addresses = socket.getaddrinfo(
            parsed.hostname,
            parsed.port or 443,
        )
        for _family, _, _, _, socket_address in addresses:
            ip = ipaddress.ip_address(socket_address[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return "Cannot fetch private/internal network addresses"
    except socket.gaierror:
        return "Cannot resolve hostname"
    return None


def _settle_and_retry(
    url,
    manager,
    payment_instrument_id,
    payment_session_id,
    user_id,
    method,
    response,
    client_token,
):
    """Generate a payment proof and replay the request with a fresh client."""
    payment_header = manager.generate_payment_header(
        payment_instrument_id=payment_instrument_id,
        payment_session_id=payment_session_id,
        user_id=user_id,
        client_token=client_token,
        payment_required_request={
            "statusCode": response.status_code,
            "headers": dict(response.headers),
            "body": response.text,
        },
    )
    with httpx.Client(verify=True) as client:
        return client.request(
            method,
            url,
            headers=payment_header,
            timeout=30,
        )


def build_x402_fetch(
    payment_manager_arn: str,
    payment_instrument_id: str,
    payment_session_id: str,
    user_id: str,
    region: str,
):
    """Build an x402 fetch tool bound to one user and payment session."""
    manager = PaymentManager(
        payment_manager_arn=payment_manager_arn,
        region_name=region,
    )

    def x402_fetch(url, method="GET"):
        """Fetch a URL and automatically settle an x402 payment when required."""
        url_error = _validate_url(url)
        if url_error:
            return json.dumps({"error": url_error})
        if not user_id:
            return json.dumps({"error": "PAYMENT_USER_ID environment variable is required"})

        response = httpx.request(method, url, timeout=30)
        if response.status_code != 402:
            return json.dumps(
                {
                    "status_code": response.status_code,
                    "body": response.text,
                }
            )

        client_token = str(uuid.uuid4())
        for attempt in range(1, MAX_PAYMENT_ATTEMPTS + 1):
            try:
                retry_response = _settle_and_retry(
                    url,
                    manager,
                    payment_instrument_id,
                    payment_session_id,
                    user_id,
                    method,
                    response,
                    client_token,
                )
            except Exception as error:  # noqa: BLE001
                return json.dumps(
                    {
                        "status_code": 402,
                        "error": f"Payment header generation failed: {error}",
                    }
                )

            if retry_response.status_code != 402:
                return json.dumps(
                    {
                        "status_code": retry_response.status_code,
                        "body": retry_response.text,
                        "payment_made": (200 <= retry_response.status_code < 300),
                        "payment_attempts": attempt,
                    }
                )

            response = retry_response

        return json.dumps(
            {
                "status_code": 402,
                "error": (
                    "Merchant still returned 402 after "
                    f"{MAX_PAYMENT_ATTEMPTS} payment attempts."
                ),
                "body": response.text,
                "payment_made": False,
                "payment_attempts": MAX_PAYMENT_ATTEMPTS,
            }
        )

    return x402_fetch
