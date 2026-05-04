"""
Cognito OAuth2 PKCE authentication for the Streamlit UI.

Manages the authorization code flow, token exchange, and cookie-based
token storage so the user stays logged in across Streamlit reruns.
"""

import base64
import hashlib
import json
import logging
import os
import secrets
from typing import Optional
from urllib.parse import urlencode

import requests
import streamlit as st

from agent_config.utils import get_ssm_parameter

logger = logging.getLogger(__name__)


class AuthManager:
    """Handles Cognito PKCE OAuth2 flow for the Streamlit UI."""

    def __init__(self):
        self.region = os.getenv("AWS_REGION", "us-east-1")
        self.client_id = get_ssm_parameter("/app/hrdlp/cognito-client-id") or os.getenv("COGNITO_CLIENT_ID", "")
        self.token_url = get_ssm_parameter("/app/hrdlp/cognito-token-url") or os.getenv("COGNITO_TOKEN_URL", "")
        self.user_pool_id = get_ssm_parameter("/app/hrdlp/cognito-user-pool-id") or ""
        # Derive auth URL from token URL
        self.auth_url = self.token_url.replace("/oauth2/token", "/oauth2/authorize") if self.token_url else ""
        self.redirect_uri = os.getenv("STREAMLIT_REDIRECT_URI", "http://localhost:8501")
        self.scopes = "openid email profile hr-dlp-gateway/read hr-dlp-gateway/pii hr-dlp-gateway/address hr-dlp-gateway/comp"

    def get_auth_url(self) -> str:
        """Generate the Cognito authorization URL with PKCE code challenge."""
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).rstrip(b"=").decode()
        st.session_state["pkce_verifier"] = verifier

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": self.scopes,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return f"{self.auth_url}?{urlencode(params)}"

    def exchange_code(self, code: str) -> Optional[dict]:
        """Exchange an authorization code for tokens."""
        verifier = st.session_state.get("pkce_verifier", "")
        try:
            resp = requests.post(
                self.token_url,
                data={
                    "grant_type": "authorization_code",
                    "client_id": self.client_id,
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                    "code_verifier": verifier,
                },
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Token exchange failed: {e}")
            return None

    def decode_token(self, access_token: str) -> dict:
        """Decode JWT payload (without verification — display only)."""
        try:
            payload_b64 = access_token.split(".")[1]
            padding = 4 - len(payload_b64) % 4
            payload_bytes = base64.urlsafe_b64decode(payload_b64 + "=" * padding)
            return json.loads(payload_bytes.decode())
        except Exception:
            return {}

    def store_tokens(self, tokens: dict) -> None:
        """Persist tokens in Streamlit session state."""
        st.session_state["access_token"] = tokens.get("access_token")
        st.session_state["id_token"] = tokens.get("id_token")
        st.session_state["refresh_token"] = tokens.get("refresh_token")

    def get_access_token(self) -> Optional[str]:
        return st.session_state.get("access_token")

    def is_authenticated(self) -> bool:
        return bool(self.get_access_token())

    def logout(self) -> None:
        for key in ["access_token", "id_token", "refresh_token", "pkce_verifier"]:
            st.session_state.pop(key, None)
