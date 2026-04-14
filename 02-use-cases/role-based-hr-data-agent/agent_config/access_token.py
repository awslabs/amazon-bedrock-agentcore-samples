"""
M2M (machine-to-machine) access token acquisition for Amazon Bedrock AgentCore Gateway.

Fetches an Amazon Cognito client_credentials token and caches it for reuse.
"""

import logging
import time
from typing import Optional

import requests

from agent_config.utils import get_ssm_parameter

logger = logging.getLogger(__name__)

_cached_token: Optional[str] = None
_token_expiry: float = 0.0


def get_gateway_access_token(client_id: Optional[str] = None, client_secret: Optional[str] = None) -> Optional[str]:
    """
    Return a valid Cognito client_credentials access token.

    Credentials are read from SSM if not provided directly:
      /app/hrdlp/cognito-client-id
      /app/hrdlp/cognito-client-secret
      /app/hrdlp/cognito-token-url
    """
    global _cached_token, _token_expiry

    if _cached_token and time.time() < _token_expiry - 60:
        return _cached_token

    client_id = client_id or get_ssm_parameter("/app/hrdlp/cognito-client-id")
    client_secret = client_secret or get_ssm_parameter("/app/hrdlp/cognito-client-secret")
    token_url = get_ssm_parameter("/app/hrdlp/cognito-token-url")

    if not all([client_id, client_secret, token_url]):
        logger.error("Missing Cognito credentials in SSM")
        return None

    try:
        response = requests.post(
            token_url,
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        _cached_token = data["access_token"]
        _token_expiry = time.time() + data.get("expires_in", 3600)
        return _cached_token
    except Exception as e:
        logger.error(f"Failed to acquire access token: {e}")
        return None
