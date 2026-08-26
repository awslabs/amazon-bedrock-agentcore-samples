"""Browser sessions: the cookie the SPA holds, and the tokens it never sees.

**This module is the entire reason the frontend cannot leak a token.** The browser gets an opaque
session id in an httpOnly cookie; the Cognito access and refresh tokens live here, server-side,
keyed by that id. An XSS bug in the SPA can read no token because there is none to read.

**And they are sealed with KMS before they are written** (`crypto.py`): at-rest encryption protects
the disk, not a caller holding `dynamodb:GetItem`.

**Why a table rather than a signed cookie carrying the tokens.** A JWT-in-cookie needs no store, but
it puts the access token back on the wire to the browser on every response — httpOnly stops
JavaScript reading it, not a compromised extension or a proxy that logs headers. And it cannot be
*revoked*: a stolen cookie is valid until expiry. A server-side session can be deleted.

**TTL is the expiry mechanism**, not a cleanup job. DynamoDB removes the row itself, so an abandoned
session disappears without anything scheduled — and a row that has passed its TTL but not yet been
swept is still treated as expired here, because DynamoDB's deletion is eventual and a security check
must not be.
"""

from __future__ import annotations

import logging
import os
import secrets
import time
from typing import Any

import boto3

# Flat import: the deploy bundle copies `app/*.py` into one directory with no package.
import crypto

log = logging.getLogger("travel.conversation")

TABLE_VAR = "SESSION_TABLE"

# Long enough for a working session, short enough that a stolen cookie has a bounded life. The
# refresh token inside outlives it, which is the point: the session is renewed server-side without
# the browser ever holding anything long-lived.
SESSION_SECONDS = 12 * 60 * 60

# Renew the access token this long before it expires, so a turn never starts with a credential that
# dies mid-stream — a streamed response cannot go back and re-authenticate.
REFRESH_MARGIN_SECONDS = 120

_table = None


def _sessions():
    """Lazily built so import works without AWS, and reused across invocations."""
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(os.environ[TABLE_VAR])
    return _table


def new_id() -> str:
    """An opaque session id.

    `token_urlsafe(32)` — 256 bits. This is a bearer credential in cookie form, so it has to be
    unguessable; a sequential or timestamp-derived id would be enumerable.
    """
    return secrets.token_urlsafe(32)


def create(
    *,
    access_token: str,
    refresh_token: str | None,
    expires_in: int,
    tenant_id: str | None,
    traveler_id: str | None,
) -> str:
    """Store a new session and return its id.

    `tenant_id` and `traveler_id` are stored **for logging and for the citation route's ownership
    check** — never as an authorization input to the agent. The agent's tenant comes from the token
    the interceptor verifies, so a tampered session row could mislabel a log line but could not
    reach another tenant's data.
    """
    session_id = new_id()
    now = int(time.time())
    _sessions().put_item(
        Item={
            "session_id": session_id,
            # Sealed under this session's id, so a ciphertext moved to another row will not
            # decrypt there. See `crypto.py`.
            "access_token": crypto.seal(access_token, session_id=session_id),
            "refresh_token": crypto.seal(refresh_token, session_id=session_id),
            # When the *access token* dies, which is not when the session does.
            "access_expires_at": now + int(expires_in),
            # When the session row dies. DynamoDB's TTL attribute.
            "expires_at": now + SESSION_SECONDS,
            "tenant_id": tenant_id,
            "traveler_id": traveler_id,
            "created_at": now,
        }
    )
    return session_id


def get(session_id: str) -> dict[str, Any] | None:
    """A live session, or `None`.

    Treats a past-TTL row as absent even if DynamoDB has not swept it yet: TTL deletion is
    eventually consistent, and "probably deleted by now" is not a basis for honouring a credential.
    """
    if not session_id:
        return None
    item = (_sessions().get_item(Key={"session_id": session_id}) or {}).get("Item")
    if not item:
        return None
    if int(item.get("expires_at", 0)) <= int(time.time()):
        return None

    # Decrypted on the way out, so no caller needs to know the tokens are sealed. A failed decrypt
    # is an expired session rather than a 500: the likeliest cause is the tampering the encryption
    # context exists to catch.
    try:
        item["access_token"] = crypto.open_(item.get("access_token"), session_id=session_id)
        item["refresh_token"] = crypto.open_(item.get("refresh_token"), session_id=session_id)
    except crypto.TokenDecryptionError as error:
        # Truncated: enough to correlate with the request log, not a usable bearer credential.
        log.warning("session rejected: %s (session %s…)", error, session_id[:8])
        return None
    return item


def destroy(session_id: str) -> None:
    """Log out. The row goes immediately rather than waiting for TTL."""
    if session_id:
        _sessions().delete_item(Key={"session_id": session_id})


def needs_refresh(session: dict[str, Any]) -> bool:
    """Whether the access token is close enough to expiry to renew before using."""
    return int(session.get("access_expires_at", 0)) - REFRESH_MARGIN_SECONDS <= int(time.time())


def update_access_token(session_id: str, access_token: str, expires_in: int) -> None:
    """Store a renewed access token against the same session.

    The session id does not rotate on refresh: the browser's cookie stays valid, which is what makes
    refresh invisible to the SPA. Rotating here would mean setting a cookie mid-stream, and headers
    cannot be written once a streamed response has started.
    """
    _sessions().update_item(
        Key={"session_id": session_id},
        UpdateExpression="SET access_token = :t, access_expires_at = :e",
        ExpressionAttributeValues={
            # A refresh must not be the one write that leaves plaintext behind.
            ":t": crypto.seal(access_token, session_id=session_id),
            ":e": int(time.time()) + int(expires_in),
        },
    )
