"""
Async agent workflow orchestration for the Amazon Bedrock AgentCore Runtime.

Wires together: context setup → token extraction → agent invocation → response.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from agent_config.agent import HRDataAgent

logger = logging.getLogger(__name__)


def _get_auth_header(context: Any) -> Optional[str]:
    if hasattr(context, "request_headers") and isinstance(context.request_headers, dict):
        headers = context.request_headers
        return headers.get("Authorization") or headers.get("authorization")
    return None


def _strip_bearer(header: str) -> str:
    return header.replace("Bearer ", "").replace("bearer ", "").strip()


async def run_agent_task(
    payload: Dict[str, Any],
    context: Any,
    gateway_url: str,
    session_id: str,
) -> Dict[str, Any]:
    """
    Main async workflow:
      1. Extract OAuth token from request headers
      2. Create/retrieve AgentContext for this session
      3. Instantiate HRDataAgent and invoke with user prompt
      4. Return structured response
    """
    user_prompt = payload.get("prompt") or "How can I help you today?"
    logger.info(f"[agent_task] session={session_id} prompt={user_prompt[:80]!r}")

    # Extract access token from incoming request (pass-through from caller)
    auth_header = _get_auth_header(context)
    if not auth_header:
        return {"error": "Missing Authorization header"}
    access_token = _strip_bearer(auth_header)

    try:
        agent = HRDataAgent(gateway_url=gateway_url, access_token=access_token)
        result = await agent.process(user_prompt)
        return result
    except Exception as e:
        logger.exception(f"[agent_task] failure: {e}")
        return {"error": str(e)}
