"""MCP Client for the Atlassian Remote MCP server (Jira integration).

Opt-in: Only activates when JIRA_MCP_URL is set. When absent, returns None
and the agent operates without Jira tools (DDB mock path).

Authentication uses AgentCore Identity with auth_flow="USER_FEDERATION"
(OAuth 2.0 3LO). The @requires_access_token decorator handles the token
fetch — it auto-detects async/sync context and manages the event loop
correctly. The agent never sees the client_secret.

First-time setup: Atlassian 3LO requires a real user to grant consent once.
On the first invocation, the on_auth_url callback logs the consent URL.
After consent, AgentCore caches the refresh token for all future invocations.
"""

import logging
import os
from typing import Optional

from strands.tools.mcp.mcp_client import MCPClient

logger = logging.getLogger(__name__)

# Opt-in env vars: set these to enable Jira integration
JIRA_MCP_URL = os.getenv("JIRA_MCP_URL")  # e.g. https://mcp.atlassian.com/v1/sse
JIRA_OAUTH_PROVIDER_NAME = os.getenv("JIRA_OAUTH_PROVIDER_NAME")
JIRA_SITE_URL = os.getenv("JIRA_SITE_URL", "")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "INC")

# Atlassian 3LO scopes: read:me + read:jira-work for fetching issues;
# write:jira-work for commenting + transitioning; offline_access for refresh.
JIRA_SCOPES = [
    "read:me",
    "read:jira-user",
    "read:jira-work",
    "write:jira-work",
    "offline_access",
]


def _is_jira_configured() -> bool:
    """Check whether Jira integration env vars are present."""
    return bool(JIRA_MCP_URL and JIRA_OAUTH_PROVIDER_NAME)


def get_jira_mcp_client_sync() -> Optional[MCPClient]:
    """Returns an MCP Client connected to the Atlassian Remote MCP server.

    STEP: IDENTITY — Uses @requires_access_token(auth_flow="USER_FEDERATION")
    to fetch a 3LO token from AgentCore Identity. The decorator handles
    async/sync context detection automatically — no manual asyncio.run() needed.

    Returns None if:
      - JIRA_MCP_URL is not configured (opt-out)
      - Token fetch fails (consent not granted, provider misconfigured)

    Uses `prefix="jira"` to namespace Jira tools and avoid collisions
    with Gateway tools (e.g., both could expose a "search" tool).
    """
    if not _is_jira_configured():
        logger.info("Jira integration not configured (JIRA_MCP_URL unset) — skipping")
        return None

    from bedrock_agentcore.identity.auth import requires_access_token
    from mcp.client.sse import sse_client

    @requires_access_token(
        provider_name=JIRA_OAUTH_PROVIDER_NAME,
        auth_flow="USER_FEDERATION",
        scopes=JIRA_SCOPES,
        on_auth_url=lambda url: logger.warning(
            "Atlassian consent required (one-time). Visit: %s", url
        ),
    )
    def _build_client(*, access_token: str) -> MCPClient:
        """Decorated — token injected by @requires_access_token."""
        logger.info("Using Atlassian MCP at %s (provider: %s)", JIRA_MCP_URL, JIRA_OAUTH_PROVIDER_NAME)
        return MCPClient(
            lambda: sse_client(
                JIRA_MCP_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            ),
            prefix="jira",
        )

    try:
        return _build_client()
    except Exception as exc:
        logger.warning("Jira MCP client creation failed: %s (Jira tools unavailable)", exc)
        return None
