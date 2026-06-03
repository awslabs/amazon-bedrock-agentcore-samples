#!/usr/bin/env python3
"""Authorization Code + PKCE helper for the demo's Okta authz server.

Opens a browser to Okta, waits for the redirect on a local one-shot HTTP
listener, exchanges the code for an access token, and prints the access
token to stdout. All log messages go to stderr so the output can be
captured directly:

    export OKTA_ACCESS_TOKEN=$(scripts/get_token.py)
    scripts/test_jwt.sh

Required env vars:
  OKTA_ISSUER         e.g. https://<tenant>.okta.com/oauth2/<authzServerId>
  OKTA_CLIENT_ID      OIDC client id

Optional env vars:
  OKTA_CLIENT_SECRET  required only for "Web application" client type
  OKTA_REDIRECT_URI   default http://localhost:8080/callback (must match
                      a Sign-in redirect URI registered on the OIDC client)
  OKTA_SCOPES         space-separated, default "openid"

Stdlib only.
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
import secrets
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def main() -> int:
    issuer = os.environ.get("OKTA_ISSUER")
    client_id = os.environ.get("OKTA_CLIENT_ID")
    if not issuer or not client_id:
        log("ERROR: OKTA_ISSUER and OKTA_CLIENT_ID must be set.")
        return 2

    client_secret = os.environ.get("OKTA_CLIENT_SECRET")
    redirect_uri = os.environ.get("OKTA_REDIRECT_URI", "http://localhost:8080/callback")
    scopes = os.environ.get("OKTA_SCOPES", "gateway.invoke openid")

    parsed = urllib.parse.urlparse(redirect_uri)
    if parsed.hostname not in ("localhost", "127.0.0.1") or not parsed.port:
        log(f"ERROR: OKTA_REDIRECT_URI must be http://localhost:<port>/<path>, got {redirect_uri!r}.")
        return 2

    verifier = b64url(secrets.token_bytes(32))
    challenge = b64url(hashlib.sha256(verifier.encode()).digest())
    state = b64url(secrets.token_bytes(16))

    auth_url = f"{issuer}/v1/authorize?" + urllib.parse.urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "scope": scopes,
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )

    received: dict[str, str] = {}
    done = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            qs = urllib.parse.urlparse(self.path).query
            params = dict(urllib.parse.parse_qsl(qs))
            received.update(params)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            if "code" in params:
                self.wfile.write(b"<h1>OK</h1><p>You can close this tab.</p>")
            else:
                err = params.get("error", "missing code")
                self.wfile.write(f"<h1>Auth failed</h1><pre>{err}</pre>".encode())
            done.set()

        def log_message(self, *_args) -> None:  # silence access log
            pass

    server = http.server.HTTPServer((parsed.hostname, parsed.port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    log(f"→ Listening on {redirect_uri}")
    log("→ Opening browser for Okta sign-in...")
    if not webbrowser.open(auth_url):
        log("Could not open a browser. Visit this URL manually:")
        log(auth_url)

    if not done.wait(timeout=300):
        server.shutdown()
        log("ERROR: timed out waiting for Okta redirect (5 min).")
        return 1
    server.shutdown()

    if received.get("state") != state:
        log("ERROR: state mismatch (possible CSRF). Aborting.")
        return 1
    if "code" not in received:
        log(f"ERROR: Okta did not return a code. Response: {received}")
        return 1

    body = {
        "grant_type": "authorization_code",
        "code": received["code"],
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": verifier,
    }
    if client_secret:
        body["client_secret"] = client_secret

    req = urllib.request.Request(
        f"{issuer}/v1/token",
        data=urllib.parse.urlencode(body).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        # URL is built from the operator-supplied OKTA_ISSUER (https://...).
        with urllib.request.urlopen(req, timeout=15) as resp:  # nosec B310
            payload = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        log(f"ERROR: token exchange failed ({e.code}): {e.read().decode(errors='replace')}")
        return 1

    token = payload.get("access_token")
    if not token:
        log(f"ERROR: token response missing access_token: {payload}")
        return 1

    log("→ Got access token.")
    print(token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
