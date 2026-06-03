"""IT Incident Response Agent (AgentCore Runtime entrypoint).

Flow per invocation:
  1. Receive a small payload — at minimum an `issue_key` for a Jira issue.
  2. Use AgentCore Identity to fetch two outbound tokens:
     - Auth0 M2M token  -> Bearer for the AgentCore Gateway (CUSTOM_JWT).
     - Atlassian 3LO    -> Bearer for the Atlassian Remote MCP server.
     AgentCore performs both OAuth grants internally; the agent never
     handles either client_secret.
  3. Connect to the AgentCore Gateway over MCP (streamable HTTP) AND
     the Atlassian Remote MCP server over SSE. Aggregate tools from
     both into one Strands agent.
  4. Resolve the ticket via that agent, then write the resolution back
     as a Jira comment + status transition through the Atlassian MCP.
  5. Record the run as an episode in AgentCore Memory.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone

from bedrock_agentcore.identity.auth import requires_access_token
from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.tools.mcp.mcp_client import MCPClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("it-incident-agent")

GATEWAY_URL = os.environ["GATEWAY_URL"]
MEMORY_ID = os.environ["MEMORY_ID"]
MODEL_ID = os.environ["AGENT_MODEL_ID"]
OAUTH_PROVIDER_NAME = os.environ["OAUTH_PROVIDER_NAME"]
GATEWAY_AUDIENCE = os.environ["GATEWAY_AUDIENCE"]
JIRA_OAUTH_PROVIDER_NAME = os.environ["JIRA_OAUTH_PROVIDER_NAME"]
JIRA_MCP_URL = os.environ["JIRA_MCP_URL"]
JIRA_SITE_URL = os.environ["JIRA_SITE_URL"]
JIRA_PROJECT_KEY = os.environ.get("JIRA_PROJECT_KEY", "INC")
REGION = os.environ.get("AWS_REGION", "us-west-2")

_memory = MemoryClient(region_name=REGION)

app = BedrockAgentCoreApp()

_gateway_token: dict = {}
_jira_token: dict = {}


@requires_access_token(
    provider_name=OAUTH_PROVIDER_NAME,
    auth_flow="M2M",
    scopes=[],
    custom_parameters={"audience": GATEWAY_AUDIENCE},
)
async def _fetch_gateway_token(*, access_token: str) -> None:
    _gateway_token["value"] = access_token


# Atlassian 3LO scopes for the agent. read:me / read:jira-work let us
# fetch the user + the issue; write:jira-work lets us comment & transition.
JIRA_SCOPES = [
    "read:me",
    "read:jira-user",
    "read:jira-work",
    "write:jira-work",
    "offline_access",
]


@requires_access_token(
    provider_name=JIRA_OAUTH_PROVIDER_NAME,
    auth_flow="USER_FEDERATION",
    scopes=JIRA_SCOPES,
    on_auth_url=lambda url: logger.warning(
        "Atlassian consent required (one-time). Visit: %s", url
    ),
)
async def _fetch_jira_token(*, access_token: str) -> None:
    _jira_token["value"] = access_token


SYSTEM_PROMPT = f"""You are an IT Incident Response Agent.

You receive a Jira issue key. Your job is to:
  1. Fetch the issue from Jira (use the Atlassian MCP `getJiraIssue` /
     equivalent tool — pick whichever the server exposes for reading an
     issue by key).
  2. Diagnose the incident using the IT-side tools available via the
     AgentCore Gateway:
       - lookup_user (requester profile + quotas)
       - get_process_info (status of named services / apps / assets)
       - query_kb (relevant runbook guidance)
       - create_change_request (only when the runbook justifies an action)
     Past episodes for the requester are surfaced from AgentCore Memory
     in the conversation context — use them to detect recurring incidents
     (>= 2 in 30 days is a strong escalation signal).
  3. Write a clear, concise resolution comment on the Jira issue (3-6
     sentences) using the Atlassian MCP `addComment` / equivalent tool.
  4. Transition the issue to a resolved/done state using the Atlassian
     MCP transition tool.

Rules:
  - The site to operate on is {JIRA_SITE_URL}, project {JIRA_PROJECT_KEY}.
  - Recurring incidents (>= 2 in 30 days) are a strong escalation signal.
  - Don't open a change request unless a runbook supports the action.
  - Keep the resolution comment user-facing — no chain-of-thought,
    no tool-call narration.

Return the resolution comment as your final message.
"""


def _record_episode(
    issue_key: str,
    requester_id: str,
    summary: str,
    description: str,
    transcript: str,
    resolution: str,
) -> None:
    payload = json.dumps(
        {
            "issue_key": issue_key,
            "summary": summary,
            "description": description,
            "transcript_excerpt": transcript[-4000:],
            "resolution": resolution,
        }
    )
    _memory.create_event(
        memory_id=MEMORY_ID,
        actor_id=requester_id,
        session_id=issue_key,
        event_timestamp=datetime.now(timezone.utc).isoformat() + "Z",
        payload=[{"blob": payload}],
    )


@app.entrypoint
def invoke(payload):
    body = payload if isinstance(payload, dict) else json.loads(payload)
    issue_key = body["issue_key"]
    requester_id = body.get("requester_id", issue_key)
    logger.info("processing Jira issue %s", issue_key)

    asyncio.run(_fetch_gateway_token(access_token=""))
    asyncio.run(_fetch_jira_token(access_token=""))
    gateway_token = _gateway_token["value"]
    jira_token = _jira_token["value"]

    def _gateway_transport():
        return streamablehttp_client(
            GATEWAY_URL,
            headers={"Authorization": f"Bearer {gateway_token}"},
        )

    def _jira_transport():
        return sse_client(
            JIRA_MCP_URL,
            headers={"Authorization": f"Bearer {jira_token}"},
        )

    with MCPClient(_gateway_transport) as gateway, MCPClient(_jira_transport) as jira:
        gateway_tools = gateway.list_tools_sync()
        jira_tools = jira.list_tools_sync()
        logger.info(
            "loaded %d gateway tools, %d jira tools",
            len(gateway_tools),
            len(jira_tools),
        )

        agent = Agent(
            model=MODEL_ID,
            system_prompt=SYSTEM_PROMPT,
            tools=[*gateway_tools, *jira_tools],
            name="ITIncidentResponder",
        )
        prompt = (
            f"Resolve Jira issue {issue_key} in project {JIRA_PROJECT_KEY} "
            f"on site {JIRA_SITE_URL}. Follow the system instructions."
        )
        result = agent(prompt)

    resolution = result.message["content"][0]["text"]
    transcript = json.dumps(result.message, default=str)

    # The agent itself wrote the comment + transitioned the issue via the
    # Atlassian MCP. Record the episode locally for memory rollups.
    _record_episode(
        issue_key=issue_key,
        requester_id=requester_id,
        summary=body.get("summary", ""),
        description=body.get("description", ""),
        transcript=transcript,
        resolution=resolution,
    )

    return {
        "issue_key": issue_key,
        "status": "Resolved",
        "resolution": resolution,
    }


if __name__ == "__main__":
    app.run()
