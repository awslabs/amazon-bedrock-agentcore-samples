"""Centralized configuration. ALL env var reads live here — nowhere else.

Environment variables are injected by the CDK stack at deploy time.
The L3 construct auto-generates names like AGENTCORE_GATEWAY_CLAIMSGATEWAY_URL
and MEMORY_CLAIMSAGENTMEMORY_ID. We read both the auto-generated and explicit names.
"""

import os

# ─── Model ──────────────────────────────────────────────────────────────────
AGENT_MODEL_ID = os.getenv("AGENT_MODEL_ID", "global.anthropic.claude-sonnet-4-6")

# ─── AWS Region ─────────────────────────────────────────────────────────────
REGION = os.getenv("AWS_REGION", "us-west-2")

# ─── Gateway ────────────────────────────────────────────────────────────────
# The L3 construct sets AGENTCORE_GATEWAY_CLAIMSGATEWAY_URL automatically.
# We also check the explicit name passed by infra-construct for backward compat.
GATEWAY_URL = os.getenv(
    "AGENTCORE_GATEWAY_URL",
    os.getenv("AGENTCORE_GATEWAY_CLAIMSGATEWAY_URL", ""),
)
GATEWAY_TOKEN_ENDPOINT = os.getenv("AGENTCORE_GATEWAY_TOKEN_ENDPOINT", "")
GATEWAY_OAUTH_SCOPES = os.getenv("AGENTCORE_GATEWAY_OAUTH_SCOPES", "")
GATEWAY_CLIENT_ID = os.getenv("AGENTCORE_GATEWAY_CLIENT_ID", "")
GATEWAY_CLIENT_SECRET = os.getenv("AGENTCORE_GATEWAY_CLIENT_SECRET", "")

# ─── Memory ─────────────────────────────────────────────────────────────────
# L3 construct injects MEMORY_CLAIMSAGENTMEMORY_ID; explicit fallback for manual config.
MEMORY_ID = os.getenv(
    "MEMORY_CLAIMSAGENTMEMORY_ID",
    os.getenv("AGENTCORE_MEMORY_ID", ""),
)

# ─── Logging ────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
