"""IT Incident Response Agent (AgentCore Runtime entrypoint).

Flow per invocation:
  1. Receive a small payload — at minimum an `issue_key` for a Jira issue.
  2. Use AgentCore Identity to fetch two outbound tokens:
     - Auth0 M2M token  -> Bearer for the AgentCore Gateway (CUSTOM_JWT).
     - Atlassian 3LO    -> Bearer for the Atlassian Remote MCP server.
     AgentCore performs both OAuth grants internally; the agent never
     handles either client_secret.
  3. Pull past-incident summaries for this requester from AgentCore
     Memory (`retrieve_memories` against the actor's namespace) and
     inject them into the system prompt.
  4. Connect to the AgentCore Gateway over MCP (streamable HTTP) AND
     the Atlassian Remote MCP server over SSE. Aggregate tools from
     both into one Strands agent.
  5. Resolve the ticket via that agent, then write the resolution back
     as a Jira comment + status transition through the Atlassian MCP.
  6. Record the run in AgentCore Memory as a USER/ASSISTANT turn so
     the configured `summary_memory_strategy` can roll it up into the
     next episode for this actor.
"""

import asyncio
import json
import logging
import os

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


SYSTEM_PROMPT_TEMPLATE = """You are an IT Incident Response Agent.

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
  3. Write a clear, concise resolution comment on the Jira issue (3-6
     sentences) using the Atlassian MCP `addComment` / equivalent tool.
  4. Transition the issue to a resolved/done state using the Atlassian
     MCP transition tool.

Rules:
  - The site to operate on is {jira_site_url}, project {jira_project_key}.
  - Don't open a change request unless a runbook supports the action.
  - Keep the resolution comment user-facing — no chain-of-thought,
    no tool-call narration.
  - Treat the recurring-incident signal below as ground truth: if the
    requester has 2 or more past episodes summarized below, escalate
    (mention recurrence in the resolution comment and create a change
    request when a runbook supports it).

{past_incidents_block}
Return the resolution comment as your final message.
"""


def _memory_namespace(requester_id: str) -> str:
    return f"incidents/{requester_id}"


def _load_past_incidents(requester_id: str, query: str) -> list[str]:
    """Pull summarized past-incident episodes for this requester.

    The CfnMemory resource is configured with a `summary_memory_strategy`
    namespaced as `incidents/{actorId}`. AgentCore extracts a summary per
    session asynchronously after each event; `retrieve_memories` does a
    semantic search across those summaries.
    """
    try:
        hits = _memory.retrieve_memories(
            memory_id=MEMORY_ID,
            namespace=_memory_namespace(requester_id),
            query=query,
            top_k=5,
        )
    except Exception as exc:
        logger.warning("memory retrieve failed for actor=%s: %s", requester_id, exc)
        return []
    summaries = []
    for hit in hits or []:
        text = (hit.get("content") or {}).get("text") or ""
        if text:
            summaries.append(text)
    return summaries


def _build_system_prompt(past_incidents: list[str]) -> str:
    if past_incidents:
        body = "\n".join(f"- {s}" for s in past_incidents)
        block = (
            f"Past incidents for this requester (most-relevant first, "
            f"count={len(past_incidents)}):\n{body}\n\n"
        )
    else:
        block = "Past incidents for this requester: none on file.\n\n"
    return SYSTEM_PROMPT_TEMPLATE.format(
        jira_site_url=JIRA_SITE_URL,
        jira_project_key=JIRA_PROJECT_KEY,
        past_incidents_block=block,
    )


def _record_episode(
    issue_key: str,
    requester_id: str,
    user_prompt: str,
    resolution: str,
) -> None:
    """Append this run as a USER/ASSISTANT turn for the configured
    summary_memory_strategy to roll up into the next episode.

    The SDK's create_event takes `messages=[(text, role)]`; the strategy
    extracts from those — blob payloads would not be summarized.
    """
    try:
        _memory.create_event(
            memory_id=MEMORY_ID,
            actor_id=requester_id,
            session_id=issue_key,
            messages=[
                (user_prompt, "USER"),
                (resolution, "ASSISTANT"),
            ],
        )
    except Exception as exc:
        logger.warning("memory create_event failed for issue=%s: %s", issue_key, exc)


@app.entrypoint
def invoke(payload):
    body = payload if isinstance(payload, dict) else json.loads(payload)
    issue_key = body["issue_key"]
    requester_id = body.get("requester_id", issue_key)
    logger.info("processing Jira issue %s for actor %s", issue_key, requester_id)

    asyncio.run(_fetch_gateway_token(access_token=""))
    asyncio.run(_fetch_jira_token(access_token=""))
    gateway_token = _gateway_token["value"]
    jira_token = _jira_token["value"]

    past_incidents = _load_past_incidents(
        requester_id=requester_id,
        query=f"prior incidents for {requester_id}",
    )
    logger.info("loaded %d past-incident summaries", len(past_incidents))
    system_prompt = _build_system_prompt(past_incidents)

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

    user_prompt = (
        f"Resolve Jira issue {issue_key} in project {JIRA_PROJECT_KEY} "
        f"on site {JIRA_SITE_URL}. Follow the system instructions."
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
            system_prompt=system_prompt,
            tools=[*gateway_tools, *jira_tools],
            name="ITIncidentResponder",
        )
        result = agent(user_prompt)

    resolution = result.message["content"][0]["text"]

    _record_episode(
        issue_key=issue_key,
        requester_id=requester_id,
        user_prompt=user_prompt,
        resolution=resolution,
    )

    return {
        "issue_key": issue_key,
        "status": "Resolved",
        "resolution": resolution,
        "recurring_incident_count": len(past_incidents),
    }


if __name__ == "__main__":
    app.run()
