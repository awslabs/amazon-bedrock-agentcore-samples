"""MCP Client for connecting to the AgentCore Gateway (and optionally Jira).

Supports two auth modes for the Gateway (controlled by GATEWAY_AUTH_MODE env var):
  - AWS_IAM (default): SigV4-signed requests using botocore credentials
  - CUSTOM_JWT: Uses AgentCore Identity @requires_access_token decorator
    to fetch an M2M OAuth token — the decorator handles async/sync context
    detection automatically.

Optionally connects to the Atlassian Remote MCP server for Jira integration
when JIRA_MCP_URL is configured. See mcp_client/jira.py for details.

The Gateway URL is injected via environment variable at runtime.
"""

import logging
import os
from typing import Optional

from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

logger = logging.getLogger(__name__)

# The L3 construct injects the URL as AGENTCORE_GATEWAY_{NAME}_URL.
# We also accept GATEWAY_URL for backward compat and explicit override.
GATEWAY_URL = os.getenv("GATEWAY_URL") or os.getenv("AGENTCORE_GATEWAY_ITINCIDENTGATEWAY_URL", "")
GATEWAY_AUTH_MODE = os.getenv("GATEWAY_AUTH_MODE", "AWS_IAM")
# New naming: GATEWAY_OAUTH_* (boundary-scoped). Falls back to legacy names for compat.
GATEWAY_OAUTH_PROVIDER_NAME = os.getenv("GATEWAY_OAUTH_PROVIDER_NAME") or os.getenv("OAUTH_PROVIDER_NAME", "")
GATEWAY_OAUTH_AUDIENCE = os.getenv("GATEWAY_OAUTH_AUDIENCE") or os.getenv("GATEWAY_AUDIENCE", "")


def _create_sigv4_auth():
    """Create an httpx.Auth instance that signs requests with SigV4.

    The AgentCore Gateway with AWS_IAM auth expects requests signed for
    service='bedrock-agentcore'. We use botocore's SigV4Auth to produce
    the Authorization, X-Amz-Date, and X-Amz-Security-Token headers.

    This is an httpx Auth *flow* — it signs every request dynamically
    (not a one-shot pre-sign) so it works correctly for multi-request
    MCP sessions (tool listing, multiple tool calls, etc.).
    """
    import httpx
    import botocore.session
    from botocore.auth import SigV4Auth
    from botocore.awsrequest import AWSRequest

    region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-west-2"))
    service = "bedrock-agentcore"
    botocore_session = botocore.session.get_session()

    class _SigV4Auth(httpx.Auth):
        """httpx Auth flow that adds SigV4 signature headers to each request."""

        def auth_flow(self, request: httpx.Request):
            # Read body bytes for signing
            body = request.content if request.content else b""

            # Build a botocore AWSRequest for signing
            # Exclude headers that SigV4Auth will compute
            headers = {
                k: v for k, v in request.headers.items()
                if k.lower() not in ("host", "authorization", "x-amz-date", "x-amz-security-token")
            }
            aws_request = AWSRequest(
                method=str(request.method),
                url=str(request.url),
                data=body,
                headers=headers,
            )

            # Get fresh credentials (they rotate in the runtime)
            credentials = botocore_session.get_credentials().get_frozen_credentials()
            SigV4Auth(credentials, service, region).add_auth(aws_request)

            # Copy the signed headers back into the httpx request
            for key, val in aws_request.headers.items():
                request.headers[key] = val

            yield request

    return _SigV4Auth()


# ─── CUSTOM_JWT: @requires_access_token on the function that consumes the token ─
# The decorator handles async/sync context detection automatically:
#   - If called from a running event loop (async def invoke): uses ThreadPoolExecutor
#   - If called from sync context (local dev): uses asyncio.run()
# The token flows directly into the closure — no module-level cache needed.

def _create_custom_jwt_client() -> Optional[MCPClient]:
    """Create Gateway MCP client with CUSTOM_JWT auth.

    STEP: IDENTITY — Uses @requires_access_token to fetch an M2M token
    from AgentCore Identity. The decorator handles the client_credentials
    grant internally; the agent never sees the client_secret.

    The token is injected directly into the MCPClient transport lambda,
    avoiding module-level state and asyncio.run() fragility.
    """
    from bedrock_agentcore.identity.auth import requires_access_token

    @requires_access_token(
        provider_name=GATEWAY_OAUTH_PROVIDER_NAME,
        auth_flow="M2M",
        scopes=[],
        custom_parameters={"audience": GATEWAY_OAUTH_AUDIENCE} if GATEWAY_OAUTH_AUDIENCE else {},
    )
    def _build_client(*, access_token: str) -> MCPClient:
        """Decorated function — token is injected by @requires_access_token."""
        return MCPClient(
            lambda: streamablehttp_client(
                GATEWAY_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
        )

    return _build_client()


def get_streamable_http_mcp_client() -> Optional[MCPClient]:
    """Returns an MCP Client connected to the AgentCore Gateway.

    Auth mode is determined by GATEWAY_AUTH_MODE:
      - AWS_IAM: Signs each request with SigV4 for bedrock-agentcore service
      - CUSTOM_JWT: Fetches OAuth token via AgentCore Identity, passes as Bearer

    Returns None if GATEWAY_URL is not configured (local dev without gateway).
    """
    if not GATEWAY_URL:
        logger.warning("GATEWAY_URL not set — MCP client unavailable. Tools will not load.")
        return None

    if GATEWAY_AUTH_MODE == "CUSTOM_JWT":
        if not GATEWAY_OAUTH_PROVIDER_NAME:
            logger.error("CUSTOM_JWT mode requires GATEWAY_OAUTH_PROVIDER_NAME env var")
            return None
        logger.info("Using CUSTOM_JWT auth (provider: %s)", GATEWAY_OAUTH_PROVIDER_NAME)
        return _create_custom_jwt_client()
    else:
        # AWS_IAM mode — SigV4 signing via botocore (signs every request)
        logger.info("Using AWS_IAM auth (SigV4 for bedrock-agentcore)")
        sigv4_auth = _create_sigv4_auth()
        return MCPClient(
            lambda: streamablehttp_client(GATEWAY_URL, auth=sigv4_auth)
        )


def get_all_mcp_clients() -> list[MCPClient]:
    """Returns all configured MCP clients (Gateway + optionally Jira).

    STEP: MULTI-MCP AGGREGATION — Compose tools from multiple MCP servers
    into a single Agent. The Gateway provides internal tools (lookup_user,
    get_process_info, etc.) and the Jira MCP provides external tools
    (getIssue, addComment, transitionIssue).

    Usage:
        agent = Agent(tools=get_all_mcp_clients(), ...)

    The Strands Agent manages the lifecycle of all MCPClient instances
    when they're passed directly to the tools parameter.

    Returns an empty list if no MCP clients could be created (local dev
    without gateway or Jira).
    """
    from mcp_client.jira import get_jira_mcp_client_sync

    clients: list[MCPClient] = []

    # Primary: AgentCore Gateway (internal tools)
    gateway_client = get_streamable_http_mcp_client()
    if gateway_client:
        clients.append(gateway_client)

    # Optional: Atlassian Remote MCP (Jira tools)
    jira_client = get_jira_mcp_client_sync()
    if jira_client:
        clients.append(jira_client)

    logger.info("Assembled %d MCP client(s) for agent", len(clients))
    return clients
