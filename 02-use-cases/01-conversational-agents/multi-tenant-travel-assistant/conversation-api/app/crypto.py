"""Seal the OAuth tokens before they touch DynamoDB.

DynamoDB's encryption at rest protects the disk, not a caller holding `dynamodb:GetItem`. Sealing
means a reader needs `kms:Decrypt` on a specific key as well, and every decrypt is a CloudTrail
event.

The **encryption context** is what makes this more than encryption: KMS treats it as authenticated
data, so a ciphertext sealed under one session id will not decrypt under another. Write access to
the table therefore cannot relocate a sealed token to hijack a session.

Direct KMS rather than a `GenerateDataKey` envelope: tokens are ~1-2 KB against the 4096-byte
limit, and an envelope would need `cryptography` in a bundle that carries no compiled wheels.
"""

from __future__ import annotations

import base64
import os
from collections import OrderedDict

import boto3

KEY_VAR = "SESSION_KMS_KEY_ID"

# Distinguishes a sealed value from a plaintext one. Without it the only test is "try to decrypt",
# whose natural failure path — use the value as-is — is a silent-plaintext path.
PREFIX = "kms1:"

_MAX_PLAINTEXT = 4096

# The session row is read on every authenticated request, so an uncached decrypt puts a KMS round
# trip on every turn. **Keyed on `(session_id, ciphertext)`**: keying on the ciphertext alone serves
# a blob decrypted for session A to session B, defeating the encryption context.
_CACHE_MAX = 256
_cache: OrderedDict[tuple[str, str], str] = OrderedDict()

_client = None


class TokenDecryptionError(RuntimeError):
    """A stored secret could not be recovered. Treated as an expired session, never as plaintext."""


def _kms():
    global _client
    if _client is None:
        _client = boto3.client("kms")
    return _client


def enabled() -> bool:
    return bool(os.environ.get(KEY_VAR))


def allow_plaintext() -> bool:
    """Opt-in escape hatch for a local run with no AWS. Never set in `infra/`."""
    return os.environ.get("TRAVEL_ALLOW_PLAINTEXT_SESSIONS") == "1"


def _context(session_id: str) -> dict[str, str]:
    return {"session_id": session_id, "purpose": "multi-tenant-travel-oauth-token"}


def write(value: str | None, *, session_id: str) -> str | None:
    """Seal a secret. Raises rather than falling back to plaintext if no key is configured."""
    if value is None:
        return None
    if not enabled():
        raise TokenDecryptionError(
            f"{KEY_VAR} is not set, so a token would be stored in plaintext. Deploy with the "
            "KMS key, or set TRAVEL_ALLOW_PLAINTEXT_SESSIONS=1 for a local throwaway table."
        )
    if len(value.encode()) > _MAX_PLAINTEXT:
        raise TokenDecryptionError(
            f"secret is {len(value.encode())} bytes, over KMS's {_MAX_PLAINTEXT}-byte Encrypt "
            "limit. Switch to a GenerateDataKey envelope if tokens have grown."
        )
    blob = _kms().encrypt(
        KeyId=os.environ[KEY_VAR],
        Plaintext=value.encode(),
        EncryptionContext=_context(session_id),
    )["CiphertextBlob"]
    return PREFIX + base64.b64encode(blob).decode()


def read(stored: str | None, *, session_id: str) -> str | None:
    """Recover a sealed secret. An unprefixed value is refused, not returned.

    That costs one re-login for sessions predating this module, and buys the guarantee that a
    deployment missing its KMS grant fails instead of quietly storing bearer tokens in the clear.
    """
    if stored is None:
        return None
    if not stored.startswith(PREFIX):
        raise TokenDecryptionError("stored secret is not sealed; sign in again")

    cache_key = (session_id, stored)
    cached = _cache.get(cache_key)
    if cached is not None:
        _cache.move_to_end(cache_key)
        return cached

    try:
        plaintext = _kms().decrypt(
            CiphertextBlob=base64.b64decode(stored[len(PREFIX) :]),
            EncryptionContext=_context(session_id),
        )["Plaintext"]
    except Exception as error:
        # The commonest cause is a context mismatch — the relocation this design refuses — so it is
        # an authentication failure rather than a retryable server error.
        raise TokenDecryptionError(
            f"could not decrypt stored secret: {type(error).__name__}"
        ) from None

    value = plaintext.decode()
    _cache[cache_key] = value
    if len(_cache) > _CACHE_MAX:
        _cache.popitem(last=False)
    return value


def seal(value: str | None, *, session_id: str) -> str | None:
    if not enabled() and allow_plaintext():
        return value
    return write(value, session_id=session_id)


def open_(stored: str | None, *, session_id: str) -> str | None:
    if not enabled() and allow_plaintext():
        return stored
    return read(stored, session_id=session_id)
