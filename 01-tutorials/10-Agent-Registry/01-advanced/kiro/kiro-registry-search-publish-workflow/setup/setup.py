"""
Setup: Shared config + Auth0 DCR OAuth (Authorization Code + PKCE).

Loads .env for registry endpoints and Auth0 domain.
get_oauth_token() does:
  1. DCR-registers a public client (if needed)
  2. Opens browser for Auth0 login (authorization_code + PKCE)
  3. Catches callback on localhost, exchanges code for token
  4. Caches token until expiry

Import: from setup import get_cp_client, get_oauth_token, create_registry_with_auth0
"""

import base64
import hashlib
import json
import logging
import os
import secrets
import time
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

import boto3
import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("poc")

# ── Config from .env ─────────────────────────────────────────────────────────

REGION = os.getenv("AWS_REGION", "us-west-2")
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")

# ── Token + client cache ─────────────────────────────────────────────────────

CALLBACK_PORT = 65358
CALLBACK_URL = f"http://localhost:{CALLBACK_PORT}/callback"

_cache = {"token": None, "expires_at": 0, "client_id": None}


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_cp_client():
    return boto3.client("bedrock-agentcore-control", region_name=REGION)


def get_dp_client():
    return boto3.client("bedrock-agentcore", region_name=REGION)


def _auth0_url(path):
    return f"https://{AUTH0_DOMAIN}{path}"


# ── DCR + PKCE OAuth flow ────────────────────────────────────────────────────

def dcr_register(client_name="registry-notebook-client"):
    """Register a public client via Auth0 DCR for authorization_code + PKCE."""
    resp = requests.post(_auth0_url("/oidc/register"), json={
        "client_name": client_name,
        "redirect_uris": [CALLBACK_URL],
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    })
    resp.raise_for_status()
    data = resp.json()
    logger.info("DCR registered client: %s", data["client_id"])
    return data["client_id"]


def _get_or_register_client():
    if _cache["client_id"]:
        return _cache["client_id"]
    cid = dcr_register()
    _cache["client_id"] = cid
    return cid


def _generate_pkce():
    """Generate PKCE code_verifier and code_challenge."""
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _authorize_via_browser(client_id, audience, code_verifier, code_challenge, timeout=120):
    """Open browser for Auth0 login, catch the callback code on localhost."""
    import subprocess
    state = secrets.token_urlsafe(32)
    auth_code = [None]
    error = [None]

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            qs = parse_qs(urlparse(self.path).query)
            if qs.get("state", [None])[0] != state:
                error[0] = "State mismatch"
            elif "error" in qs:
                error[0] = qs["error"][0] + ": " + qs.get("error_description", [""])[0]
            else:
                auth_code[0] = qs.get("code", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            msg = "Authentication successful! You can close this tab." if auth_code[0] else f"Error: {error[0]}"
            self.wfile.write(f"<html><body><h2>{msg}</h2></body></html>".encode())

        def log_message(self, *args):
            pass

    server = HTTPServer(("localhost", CALLBACK_PORT), CallbackHandler)
    server.timeout = timeout

    authorize_url = _auth0_url("/authorize") + "?" + urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": CALLBACK_URL,
        "audience": audience,
        "scope": "openid",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    })

    # Print clickable link as fallback, then try to open browser
    print(f"\n Auth0 login required. If browser doesn't open, click:\n{authorize_url}\n")
    try:
        subprocess.Popen(["open", authorize_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        try:
            webbrowser.open(authorize_url)
        except Exception:
            pass  # user can click the printed URL

    server.handle_request()
    server.server_close()

    if error[0]:
        raise RuntimeError(f"Auth0 authorization failed: {error[0]}")
    if not auth_code[0]:
        raise RuntimeError("No authorization code received (timeout?)")

    return auth_code[0]


def _exchange_code(client_id, code, code_verifier):
    """Exchange authorization code for access token."""
    resp = requests.post(_auth0_url("/oauth/token"), json={
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "redirect_uri": CALLBACK_URL,
        "code_verifier": code_verifier,
    })
    resp.raise_for_status()
    return resp.json()


def get_oauth_token(force_refresh=False, audience=None):
    """Get a valid Auth0 bearer token via DCR + authorization_code PKCE.

    First call opens a browser for login. Token is cached until expiry.
    """
    if not audience:
        raise ValueError("audience is required — pass the registry MCP URL.")

    if not force_refresh and _cache["token"] and time.time() < _cache["expires_at"] - 60:
        return _cache["token"]

    client_id = _get_or_register_client()
    code_verifier, code_challenge = _generate_pkce()

    # Browser popup — user authenticates once
    code = _authorize_via_browser(client_id, audience, code_verifier, code_challenge)
    data = _exchange_code(client_id, code, code_verifier)

    _cache["token"] = data["access_token"]

    # Parse expiry from JWT or response
    try:
        payload = data["access_token"].split(".")[1]
        payload += "=" * (4 - len(payload) % 4)
        decoded = json.loads(base64.b64decode(payload))
        _cache["expires_at"] = decoded.get("exp", time.time() + 3600)
    except Exception:
        _cache["expires_at"] = time.time() + data.get("expires_in", 3600)

    logger.info("OAuth token acquired (expires in %ds)", _cache["expires_at"] - time.time())
    return _cache["token"]


# ── Registry management ─────────────────────────────────────────────────────

def create_registry_with_auth0(name="auth0-oauth-registry",
                                description="Registry with Auth0 OAuth authentication",
                                initial_audience="AWS-REGISTRY-SAMPLE-DCR-V0",
                                poll_interval=5, max_wait=150):
    """Create a registry with Auth0 CUSTOM_JWT authorizer.

    initial_audience is the Auth0 API identifier used at creation time.
    After READY, the MCP URL is added to allowedAudience automatically.
    Sets module-level REGISTRY_ID and AUTH0_AUDIENCE.
    """
    cp = get_cp_client()
    discovery_url = f"https://{AUTH0_DOMAIN}/.well-known/openid-configuration"

    logger.info("Creating registry '%s' with CUSTOM_JWT authorizer...", name)
    resp = cp.create_registry(
        name=name,
        description=description,
        authorizerType="CUSTOM_JWT",
        authorizerConfiguration={
            "customJWTAuthorizer": {
                "discoveryUrl": discovery_url,
                "allowedAudience": [initial_audience],
            }
        },
    )
    registry_arn = resp["registryArn"]
    registry_id = registry_arn.split("/")[-1]
    logger.info("Created registry %s (%s)", registry_id, registry_arn)

    # Wait for READY
    status = "UNKNOWN"
    elapsed = 0
    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval
        info = cp.get_registry(registryId=registry_id)
        status = info.get("status", "UNKNOWN")
        logger.info("[%ds] status=%s", elapsed, status)
        if status == "READY":
            break

    if status != "READY":
        logger.warning("Registry not READY after %ds (status=%s) — skipping audience update", max_wait, status)
    else:
        # Add MCP URL to allowedAudience
        update_registry_audience_with_mcp_url(registry_id)
        logger.info("Added MCP URL to allowedAudience")

    return {"registryId": registry_id, "registryArn": registry_arn, "status": status}


def update_registry_audience_with_mcp_url(registry_id=None):
    """Add the MCP endpoint URL to the registry's allowedAudience."""

    cp = get_cp_client()
    registry = cp.get_registry(registryId=registry_id)
    jwt_config = registry["authorizerConfiguration"]["customJWTAuthorizer"]
    dp = get_dp_client()
    mcp_url = f"{dp.meta.endpoint_url}/registry/{registry_id}/mcp"
    audience = list(set(jwt_config.get("allowedAudience", []) + [mcp_url]))
    cp.update_registry(
        registryId=registry_id,
        authorizerConfiguration={
            "optionalValue": {
                "customJWTAuthorizer": {
                    "discoveryUrl": jwt_config["discoveryUrl"],
                    "allowedAudience": audience,
                }
            }
        },
    )
    while True:
        status = cp.get_registry(registryId=registry_id)["status"]
        if status != "UPDATING":
            break
        time.sleep(2)
    return cp.get_registry(registryId=registry_id)


