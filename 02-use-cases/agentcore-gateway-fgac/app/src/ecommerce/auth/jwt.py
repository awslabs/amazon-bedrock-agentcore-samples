"""JWT claim extraction for the ALB-validated request path.

The ALB performs full JWT validation (signature, issuer, audience, role
membership) before any request reaches the app — see the Terraform
`jwt_validation` action on the HTTPS listener. By the time a request
arrives here, the token has been verified.

This module *parses* claims from the bearer token to derive the
``Principal`` (sub, role) used for per-route authorization. It does not
re-validate the signature.
"""

import base64
import json
from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import Depends, Header, HTTPException, status

Role = Literal["customer", "admin"]


@dataclass(frozen=True)
class Principal:
    sub: str
    role: Role


def _decode_claims(token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed token")
    payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload_b64))
    except (ValueError, json.JSONDecodeError) as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed token") from e


def get_principal(
    authorization: Annotated[str | None, Header(include_in_schema=False)] = None,
) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")

    token = authorization.split(None, 1)[1]
    claims = _decode_claims(token)

    sub = claims.get("sub")
    role = claims.get("role")
    if not isinstance(sub, str) or role not in ("customer", "admin"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token missing required sub/role claims")

    return Principal(sub=sub, role=role)


def require_admin(
    principal: Annotated[Principal, Depends(get_principal)],
) -> Principal:
    if principal.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return principal
