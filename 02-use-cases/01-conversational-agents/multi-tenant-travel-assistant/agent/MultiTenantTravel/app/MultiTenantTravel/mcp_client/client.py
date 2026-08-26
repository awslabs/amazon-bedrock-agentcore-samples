"""Gateway MCP client.

The agent reaches its tools through the AgentCore Gateway, forwarding **the traveller's
own bearer token**. That is what lets the Gateway's request interceptor verify the caller
and inject tenant context — the agent itself asserts nothing about who is asking, which is
why a prompt-injected model cannot change tenant.

The token reaches us because the runtime is configured with
`requestHeaderAllowlist: ["Authorization"]`; without it the header never arrives and every
tool call is refused.
"""

from __future__ import annotations

import logging
import os

from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

logger = logging.getLogger(__name__)

# Set on the runtime by `scripts/configure_gateway.py`.
GATEWAY_URL_VAR = "GATEWAY_MCP_URL"

# This gateway advertises only `2025-03-26`; a newer version returns JSON-RPC -32022 with
# the supported list. Pinned rather than defaulted so an upgrade is a deliberate change
# with an eval run behind it.
MCP_PROTOCOL_VERSION = "2025-03-26"

# Carries the conversation id to the tools for **audit correlation only**. Must match
# `SESSION_HEADER` in `tools/common/context.py` and the interceptor — they cross language
# boundaries, so the name is stated in each place and a mismatch shows up as a missing
# `session_id` in CloudTrail rather than as an error.
SESSION_HEADER = "X-Session-Id"


def gateway_url() -> str | None:
    return os.environ.get(GATEWAY_URL_VAR)


def get_gateway_client(access_token: str | None, session_id: str | None = None) -> MCPClient | None:
    """An MCP client bound to one traveller's token, labelled with this conversation.

    Returns `None` when the gateway is unconfigured or the token is absent, so the caller
    degrades to a clear refusal rather than crashing. A tool-less agent that says "I can't
    reach your travel information" is far better than a stack trace.

    **Per-request, never cached.** The client carries the caller's credential, so reusing
    one across sessions would mean acting for the wrong traveller — the worst bug this
    layer could have.

    `session_id` travels as `X-Session-Id` purely for **audit correlation**: the backend puts it
    on an STS session tag, so a CloudTrail data event can be traced back to one conversation and
    joined to the ledger line for the same turn. Nothing authorises on it — identity comes from
    the token, verified again at the gateway.
    """
    url = gateway_url()
    if not url:
        logger.error("%s is not set — the agent has no tools", GATEWAY_URL_VAR)
        return None
    if not access_token:
        logger.error("no bearer token on this invocation — the agent has no tools")
        return None

    headers = {
        "Authorization": f"Bearer {access_token}",
        "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
    }
    if session_id:
        headers[SESSION_HEADER] = session_id
    else:
        # The runtime supplies a session id even when the caller omits one, so absence here means
        # our own plumbing dropped it — worth a warning, because the symptom is silent: tools
        # keep working and the audit trail quietly loses conversation attribution.
        logger.warning("no session id on this invocation — tool calls will not be attributable")

    def transport():
        return streamablehttp_client(url, headers=headers)

    return MCPClient(transport)


def list_tools(client: MCPClient) -> list:
    """All tools, following pagination.

    `list_tools_sync` paginates, and ignoring `pagination_token` silently truncates the
    catalog — the model then cannot call a tool it was never told about, which presents as
    a reasoning failure rather than a plumbing one.

    Called **once per session**, not per turn: the Gateway serves this from its capability
    catalog so it is cheap, but a per-turn round trip is still latency for nothing.
    """
    tools: list = []
    token = None
    while True:
        page = client.list_tools_sync(pagination_token=token)
        tools.extend(page)
        token = getattr(page, "pagination_token", None)
        if not token:
            return tools
