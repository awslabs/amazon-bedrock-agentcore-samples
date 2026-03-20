"""
AgentCore Runtime agent demonstrating two outbound OAuth2 flows:

  1. M2M (machine-to-machine / client credentials):
     The agent calls an internal API as itself, using a service account.
     @requires_access_token with auth_flow="M2M" — no user interaction needed.

  2. Auth Code / 3LO (authorization code / user federation):
     The agent accesses Google Calendar on behalf of the authenticated user.
     @requires_access_token with auth_flow="USER_FEDERATION" — triggers a
     consent URL on first access; subsequent calls use stored tokens.

Inbound Auth: Cognito JWT (configured in agentcore/agentcore.json).
"""

import json
import os
from datetime import datetime, timezone

import httpx
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.identity.auth import requires_access_token

app = BedrockAgentCoreApp()
_model = BedrockModel(model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0")

# ---------------------------------------------------------------------------
# M2M: client credentials grant
# The agent authenticates as a service account (no user involved).
# ---------------------------------------------------------------------------

_m2m_token_cache: dict = {}


@requires_access_token(
    provider_name="M2MProvider",
    auth_flow="M2M",
    scopes=["api:read"],
)
async def _fetch_m2m_token(*, access_token: str) -> None:
    """Fetch M2M access token from AgentCore Identity."""
    _m2m_token_cache["token"] = access_token


@tool
async def call_internal_api(endpoint: str) -> str:
    """Call an internal/downstream API using the M2M service account token.

    Args:
        endpoint: The API path to call (e.g. "/api/v1/status")
    """
    if "token" not in _m2m_token_cache:
        await _fetch_m2m_token(access_token="")

    token = _m2m_token_cache.get("token", "")
    base_url = os.environ.get("INTERNAL_API_BASE_URL", "https://api.example.internal")

    # In production: use the token to authenticate to the internal service
    print(f"[M2M] Calling {base_url}{endpoint} with token: {token[:20]}...")

    # Simulated response for demo purposes
    return json.dumps({"status": "ok", "endpoint": endpoint, "timestamp": datetime.now(timezone.utc).isoformat()})


# ---------------------------------------------------------------------------
# Auth Code / 3LO: authorization code grant (Google Calendar)
# The agent accesses the user's Google Calendar.
# On first call: returns a consent URL for the user to visit.
# On subsequent calls: uses stored tokens automatically.
# ---------------------------------------------------------------------------

_google_token_cache: dict = {}
_auth_url_cache: dict = {}


def _on_auth_url(url: str) -> None:
    """Called by AgentCore Identity when user consent is required."""
    _auth_url_cache["url"] = url
    print(f"\n[3LO] User consent required. Visit this URL to authorize Google Calendar access:\n{url}\n")


@requires_access_token(
    provider_name="Google3LOProvider",
    auth_flow="USER_FEDERATION",
    scopes=["https://www.googleapis.com/auth/calendar.readonly"],
    on_auth_url=_on_auth_url,
)
async def _fetch_google_token(*, access_token: str) -> None:
    """Fetch Google OAuth2 token from AgentCore Identity."""
    _google_token_cache["token"] = access_token


@tool
async def get_calendar_events() -> str:
    """Get today's Google Calendar events for the authenticated user.

    On first call, this will return an authorization URL.
    After the user grants consent, call this tool again to get events.
    """
    if "token" not in _google_token_cache:
        await _fetch_google_token(access_token="")

    if "url" in _auth_url_cache and "token" not in _google_token_cache:
        return (
            f"User authorization required. Please visit this URL and grant access:\n"
            f"{_auth_url_cache['url']}\n\n"
            "After authorizing, invoke the agent again to retrieve your calendar events."
        )

    token = _google_token_cache.get("token", "")
    today = datetime.now(timezone.utc).date().isoformat()

    async with httpx.AsyncClient() as http_client:
        resp = await http_client.get(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "timeMin": f"{today}T00:00:00Z",
                "timeMax": f"{today}T23:59:59Z",
                "singleEvents": "true",
                "orderBy": "startTime",
            },
        )
        resp.raise_for_status()
        events = resp.json().get("items", [])

    if not events:
        return f"No calendar events found for today ({today})."

    lines = [f"Calendar events for {today}:"]
    for event in events:
        start = event.get("start", {}).get("dateTime", event.get("start", {}).get("date", ""))
        lines.append(f"  - {start}: {event.get('summary', '(no title)')}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Agent entrypoint
# ---------------------------------------------------------------------------

_agent: Agent | None = None


@app.entrypoint
async def handler(payload: dict) -> str:
    global _agent

    if _agent is None:
        _agent = Agent(
            model=_model,
            tools=[call_internal_api, get_calendar_events],
            system_prompt=(
                "You are a helpful assistant. "
                "You can call internal APIs (using secure M2M credentials) "
                "and check the user's Google Calendar (using their delegated OAuth2 access)."
            ),
        )

    user_input = payload.get("prompt", "")
    response = _agent(user_input)
    return response.message["content"][0]["text"]


if __name__ == "__main__":
    app.run()
