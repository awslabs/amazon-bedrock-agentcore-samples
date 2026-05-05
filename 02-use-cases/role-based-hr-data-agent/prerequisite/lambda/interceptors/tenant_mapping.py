"""
Shared tenant mapping loader for request/response interceptors.

Maps Cognito client_id → tenant context (tenantId, role, department, username).
Loaded once per Lambda container lifetime via lru_cache.

Why this exists: Cognito V2_0 client_credentials tokens do not carry custom
claims, so tenant context must be derived from the client_id (JWT sub claim)
using this external mapping rather than from the token itself.

Load order:
  1. Local file (CLIENT_TENANT_MAPPING_PATH env var, default config/client_tenant_mapping.json)
  2. SSM Parameter Store (/app/hrdlp/client-tenant-mapping) — populated by
     scripts/cognito_credentials_provider.py create
  3. Empty fallback (all client_ids return "unknown" — safe deny-by-default)
"""

import json
import os
from functools import lru_cache
from typing import Dict

_SSM_PARAM = "/app/hrdlp/client-tenant-mapping"
_FALLBACK: Dict[str, Dict[str, str]] = {}


@lru_cache(maxsize=1)
def _load_mapping() -> Dict[str, Dict[str, str]]:
    # 1. Try local file
    path = os.getenv("CLIENT_TENANT_MAPPING_PATH", "config/client_tenant_mapping.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            mapping = json.load(f)
        print(f"[tenant-mapping] Loaded {len(mapping)} clients from {path}")
        return mapping
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[tenant-mapping] WARNING: Failed to load {path}: {e}")

    # 2. Fall back to SSM (populated by cognito_credentials_provider.py create)
    try:
        import boto3
        resp = boto3.client("ssm").get_parameter(Name=_SSM_PARAM, WithDecryption=False)
        mapping = json.loads(resp["Parameter"]["Value"])
        print(f"[tenant-mapping] Loaded {len(mapping)} clients from SSM ({_SSM_PARAM})")
        return mapping
    except Exception as e:
        print(f"[tenant-mapping] WARNING: SSM fallback failed: {e}, using empty mapping")
        return _FALLBACK


def resolve_client_context(client_id: str) -> Dict[str, str]:
    """Return tenant context for client_id; returns 'unknown' values if not found."""
    ctx = _load_mapping().get(client_id)
    if not ctx:
        print(f"[tenant-mapping] WARNING: Unknown client_id: {client_id}")
        return {"tenantId": "unknown", "role": "unknown", "department": "unknown", "username": "unknown"}
    return ctx


def reload_mapping() -> None:
    """Force re-read of the mapping file (clears lru_cache)."""
    _load_mapping.cache_clear()
