"""The Cognito authorization-code flow, run entirely server-side.

**PKCE even though this is a confidential-ish server.** The code verifier never leaves this Lambda,
so
an intercepted authorization code is useless without it. Cognito's public clients require PKCE
anyway, and our web client has no secret — a browser could not keep one, and pretending otherwise is
a common way samples teach an insecure pattern.

**`urllib`, not `requests`.** Same reason as the tool layer: this runs zip-packaged, and every
dependency is cold-start latency plus a native-wheel risk at package time. The token exchange is one
form POST.

**The verifier is stashed in the session table**, keyed by the `state` value, rather than in a
cookie.
A cookie would work, but it means the browser holds part of the auth exchange — and the whole point
of
this design is that it holds nothing but an opaque id.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

import boto3

# Flat import: the deploy bundle has no package structure.
import crypto

COGNITO_DOMAIN_VAR = "COGNITO_DOMAIN"
CLIENT_ID_VAR = "COGNITO_CLIENT_ID"
REDIRECT_URI_VAR = "OAUTH_REDIRECT_URI"
TABLE_VAR = "SESSION_TABLE"

# This only has to survive one round trip through Cognito's hosted UI — but a *first* sign-in on
# that
# UI can include a forced password change and MFA enrolment, which a real person can take several
# minutes to complete. Ten minutes was long enough for the happy path and too short for that first
# run, so a legitimate slow login expired and read as a forged one. Thirty minutes covers the slow
# first sign-in; the row stays single-use (deleted on exchange), so widening the window does not
# widen
# the replay surface — a replay still finds nothing.
PENDING_SECONDS = 1800

_table = None


def _pending():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(os.environ[TABLE_VAR])
    return _table


def _domain() -> str:
    return os.environ[COGNITO_DOMAIN_VAR].rstrip("/")


def _default_redirect_uri() -> str:
    """The deployed callback — the one this function is configured with."""
    return os.environ[REDIRECT_URI_VAR]


def _origin(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _redirect_uri_for(return_to: str | None) -> str:
    """The OAuth callback to use for a login that began at `return_to`.

    One deployment serves both the CloudFront site and a developer's `npm run dev`, but Cognito must
    be sent back to the origin the login *started* on, or the browser lands on the wrong host and
    the
    session cookie is set where nobody is looking. So the callback is chosen per login rather than
    fixed.

    Only the deployed origin and loopback are honoured — the caller has already checked `return_to`
    against the allowlist, and this refuses to synthesise a callback for anything other than
    `localhost`/`127.0.0.1`, so an unexpected origin falls back to the default rather than minting a
    URL Cognito would reject. The dev server proxies `/api` onto the API's `/v1` stage, which is why
    its browser-facing callback path is `/api/auth/callback` rather than the deployed `/v1/...`.
    """
    default = _default_redirect_uri()
    if not return_to:
        return default
    return_to = return_to.rstrip("/")
    if _origin(default) == return_to:
        return default
    host = urllib.parse.urlparse(return_to).hostname or ""
    if host in ("localhost", "127.0.0.1"):
        return f"{return_to}/api/auth/callback"
    return default


def _post_form(url: str, fields: dict[str, str]) -> dict:
    """POST a form and parse the JSON response."""
    request = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(fields).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read() or b"{}")


def start(return_to: str | None = None) -> str:
    """Begin a login. Returns the Cognito URL to redirect the browser to.

    Generates a PKCE pair and a `state`, stores the verifier against the state, and hands back only
    the challenge — so nothing the browser carries is sufficient to complete the exchange.

    `return_to` is the (already allowlisted) SPA origin the login began on. Both the callback used
    for
    this login and the origin the browser is bounced back to afterwards are derived from it and
    stored against the `state`, so the token exchange can present the *same* `redirect_uri` OAuth
    requires and the final redirect lands back where the traveller started — CloudFront or the dev
    server.
    """
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    )
    state = secrets.token_urlsafe(24)
    redirect_uri = _redirect_uri_for(return_to)

    _pending().put_item(
        Item={
            # Namespaced so a pending authorization can never be mistaken for a live session by the
            # session lookup, which reads the same table.
            "session_id": f"pending#{state}",
            # Sealed like the tokens. Alone it cannot complete a login — an attacker also needs the
            # authorization code — but it is half of a pair, and the other half is encrypted.
            "code_verifier": crypto.seal(verifier, session_id=f"pending#{state}"),
            # Stored so the token exchange presents the identical redirect_uri, and the final bounce
            # returns to the origin the login began on.
            "redirect_uri": redirect_uri,
            "return_to": return_to or _origin(redirect_uri),
            "expires_at": int(time.time()) + PENDING_SECONDS,
        }
    )

    query = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": os.environ[CLIENT_ID_VAR],
            "redirect_uri": redirect_uri,
            # `openid` for identity, plus the resource-server scopes the gateway's authorizer
            # requires — a token without `travel/read` is refused at the gateway, not here.
            "scope": "openid email travel/read travel/book",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{_domain()}/oauth2/authorize?{query}"


def exchange(code: str, state: str) -> tuple[dict, str]:
    """Trade an authorization code for tokens. Raises on anything suspect.

    The `state` lookup is what makes this safe: an attacker who induces a callback with their own
    code
    has no matching pending row, so the exchange never happens. Consumed on use — a replayed
    callback
    finds nothing.

    Returns the tokens together with the `return_to` origin recorded at `start`, so the callback can
    bounce the browser back to the site the login began on. The `redirect_uri` presented here is the
    one stored against the `state`, because OAuth requires it to match the value used at authorize.
    """
    key = {"session_id": f"pending#{state}"}
    item = (_pending().get_item(Key=key) or {}).get("Item")
    if not item:
        raise PermissionError("unknown or expired login attempt")
    if int(item.get("expires_at", 0)) <= int(time.time()):
        raise PermissionError("login attempt expired")
    # Single use. Deleted before the exchange so a concurrent replay cannot also succeed.
    _pending().delete_item(Key=key)

    tokens = _post_form(
        f"{_domain()}/oauth2/token",
        {
            "grant_type": "authorization_code",
            "client_id": os.environ[CLIENT_ID_VAR],
            "code": code,
            "redirect_uri": item.get("redirect_uri") or _default_redirect_uri(),
            "code_verifier": crypto.open_(item["code_verifier"], session_id=key["session_id"]),
        },
    )
    return tokens, item.get("return_to") or _origin(_default_redirect_uri())


def logout_url(return_to: str | None = None) -> str:
    """Cognito's hosted-UI logout — the half of sign-out this module was missing.

    **Destroying the local session row is not signing out.** `/auth/logout` only ever deleted that
    row, so the browser still held Cognito's own hosted-UI session cookie — set on Cognito's domain,
    invisible to this app entirely. Clicking sign in again did not show a login form; it silently
    re-authenticated as whoever last typed a password there, which defeats the one demo this sample
    leads with: sign in as the other tenant and ask the same question. Found in a browser, because
    every API-level check drives the OAuth exchange itself and never observes what a *second* login
    click does with a session Cognito is still holding open.

    So sign-out has the same shape as sign-in: this module owns the redirect, the browser is sent to
    Cognito, and the app never talks to Cognito's domain except through a URL this function builds.
    `logout_uri` must be on the app client's allowed logout URLs — the same allowlist `redirect_uri`
    already satisfies, since both are configured with this deployment's origin.
    """
    query = urllib.parse.urlencode(
        {
            "client_id": os.environ[CLIENT_ID_VAR],
            "logout_uri": return_to or _origin(_default_redirect_uri()),
        }
    )
    return f"{_domain()}/logout?{query}"


def refresh(refresh_token: str) -> dict:
    """Renew an access token. Cognito returns no new refresh token for this grant."""
    return _post_form(
        f"{_domain()}/oauth2/token",
        {
            "grant_type": "refresh_token",
            "client_id": os.environ[CLIENT_ID_VAR],
            "refresh_token": refresh_token,
        },
    )


def user_info(access_token: str) -> dict:
    """Verify an access token against Cognito and return its user info. Raises if invalid.

    **The server-side validation the BFF fails closed on**, and deliberately not
    `cognito-idp:GetUser`: that call requires the `aws.cognito.signin.user.admin` scope, which a
    token from the authorization-code flow does not carry — so it answers *"Access Token does not
    have required scopes"* for a perfectly valid credential. `/oauth2/userInfo` needs only `openid`,
    checks signature, expiry and revocation the same way, and 401s on a token that has been revoked
    since it was issued.

    Cheap enough to run before every turn: one HTTPS call against a rejected token beats a runtime
    cold start.
    """
    request = urllib.request.Request(
        f"{_domain()}/oauth2/userInfo",
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read() or b"{}")


def claims(access_token: str) -> dict:
    """Read the token's claims **without verifying** — for labelling only.

    Deliberately unverified, and safe because nothing authorizes on the result: the tenant that
    matters is the one the gateway's interceptor extracts from the same token after verifying its
    signature. This is used to put `tenant_id` on a log line and on the session row.

    Verifying here would mean fetching JWKS and doing RS256 in this Lambda — which the interceptor
    already does, properly, at the boundary that counts.
    """
    try:
        payload = access_token.split(".")[1]
        padded = payload + "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(padded))
    except (IndexError, ValueError):
        return {}
