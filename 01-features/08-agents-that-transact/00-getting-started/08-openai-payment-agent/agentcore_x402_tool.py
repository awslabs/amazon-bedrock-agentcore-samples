"""AgentCore Payments adapter for x402 function tools."""

import ipaddress
import json
import os
import socket
import uuid
from urllib.parse import urlparse

import httpx
from bedrock_agentcore.payments import PaymentManager

PAYMENT_MANAGER_ARN = os.getenv("PAYMENT_MANAGER_ARN")
PAYMENT_INSTRUMENT_ID = os.getenv("PAYMENT_INSTRUMENT_ID")
PAYMENT_SESSION_ID = os.getenv("PAYMENT_SESSION_ID")
PAYMENT_USER_ID = os.getenv("PAYMENT_USER_ID")
REGION = os.getenv("AWS_REGION", "us-east-1")
MAX_PAYMENT_ATTEMPTS = int(os.getenv("X402_MAX_PAYMENT_ATTEMPTS", "5"))

_manager = (
    PaymentManager(
        payment_manager_arn=PAYMENT_MANAGER_ARN,
        region_name=REGION,
    )
    if PAYMENT_MANAGER_ARN
    else None
)


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


def _settle_and_retry(url, method, response, client_token):
    """Generate a payment proof and replay the request with a fresh client."""
    payment_header = _manager.generate_payment_header(
        payment_instrument_id=PAYMENT_INSTRUMENT_ID,
        payment_session_id=PAYMENT_SESSION_ID,
        user_id=PAYMENT_USER_ID,
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


def x402_fetch(url, method="GET"):
    """Fetch a URL and automatically settle an x402 payment when required."""
    url_error = _validate_url(url)
    if url_error:
        return json.dumps({"error": url_error})
    if not PAYMENT_USER_ID:
        return json.dumps({"error": "PAYMENT_USER_ID environment variable is required"})

    response = httpx.request(method, url, timeout=30)
    if response.status_code != 402:
        return json.dumps(
            {
                "status_code": response.status_code,
                "body": response.text,
            }
        )

    if not _manager:
        return json.dumps(
            {
                "status_code": 402,
                "error": "Set PAYMENT_MANAGER_ARN before using this tool.",
                "body": response.text,
            }
        )

    client_token = str(uuid.uuid4())
    for attempt in range(1, MAX_PAYMENT_ATTEMPTS + 1):
        try:
            retry_response = _settle_and_retry(
                url,
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
            "error": (f"Merchant still returned 402 after {MAX_PAYMENT_ATTEMPTS} payment attempts."),
            "body": response.text,
            "payment_made": False,
            "payment_attempts": MAX_PAYMENT_ATTEMPTS,
        }
    )
