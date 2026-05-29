"""IT Incident Response Agent (AgentCore Runtime entrypoint).

Flow per invocation:
  1. Receive ticket payload (no token in payload — see Auth note below).
  2. Use AgentCore Identity (`@requires_access_token`, auth_flow=M2M) to
     get an Auth0 access token. AgentCore performs the client_credentials
     grant against Auth0 internally; the agent never handles the secret.
  3. Connect to the AgentCore Gateway over MCP using that token. The
     Gateway's CUSTOM_JWT authorizer (also Auth0) validates it.
  4. Run a Strands agent with the gateway-hosted tools (lookup_user,
     get_process_info, create_change_request, query_kb).
  5. Record the run as an episode in AgentCore Memory.
  6. Write the resolution comment back to the Tickets DynamoDB row and
     mark it Resolved (mock Jira).
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone

import boto3
from bedrock_agentcore.identity.auth import requires_access_token
from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.tools.mcp.mcp_client import MCPClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("it-incident-agent")

GATEWAY_URL = os.environ["GATEWAY_URL"]
MEMORY_ID = os.environ["MEMORY_ID"]
MODEL_ID = os.environ["AGENT_MODEL_ID"]
TICKETS_TABLE = os.environ["TICKETS_TABLE"]
OAUTH_PROVIDER_NAME = os.environ["OAUTH_PROVIDER_NAME"]
GATEWAY_AUDIENCE = os.environ["GATEWAY_AUDIENCE"]
REGION = os.environ.get("AWS_REGION", "us-west-2")

_tickets = boto3.resource("dynamodb", region_name=REGION).Table(TICKETS_TABLE)
_memory = MemoryClient(region_name=REGION)

app = BedrockAgentCoreApp()

_gateway_token: dict = {}


@requires_access_token(
    provider_name=OAUTH_PROVIDER_NAME,
    auth_flow="M2M",
    scopes=[],
    # Auth0 requires `audience` (not a scope) in the client_credentials
    # grant; without it Auth0 issues an opaque token and the Gateway's
    # CUSTOM_JWT authorizer rejects it. AgentCore Identity forwards
    # custom_parameters to the IdP's token endpoint.
    custom_parameters={"audience": GATEWAY_AUDIENCE},
)
async def _fetch_gateway_token(*, access_token: str) -> None:
    _gateway_token["value"] = access_token


SYSTEM_PROMPT = """You are an IT Incident Response Agent.

You receive a ticket describing a user-reported IT problem. Your job is to
diagnose, take any necessary corrective action, and produce a clear
resolution comment.

Always work in this order:
  1. Call `lookup_user` with the requester to understand their context,
     quotas, and recent incident history. Recurring incidents (>= 2 in 30
     days) are a strong signal to escalate.
  2. If the ticket mentions a specific process / service / app, call
     `get_process_info` to understand its status and known issues.
  3. Call `query_kb` with a focused query to retrieve relevant runbook
     guidance from the IT knowledge base.
  4. If a corrective action is justified by the runbook, call
     `create_change_request` to record the action and stamp the user.
  5. Produce a short final resolution comment (3-6 sentences) that
     summarises what you found, what you did, and any follow-up the user
     should take.

Return only the resolution comment as your final message. Do not include
chain-of-thought, planning markers, or tool-call narration in the final
comment."""


def _resolve_ticket(ticket_id: str, comment: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    _tickets.update_item(
        Key={"ticket_id": ticket_id},
        UpdateExpression="SET #s = :s, resolution_comment = :c, resolved_at = :t, updated_at = :t",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "Resolved",
            ":c": comment,
            ":t": now,
        },
    )


def _record_episode(ticket: dict, transcript: str, resolution: str) -> None:
    """Write one event to AgentCore Memory, scoped per-user, per-ticket session.

    With an EPISODIC strategy on the memory resource, AgentCore will roll up
    these events into episodes that future incidents can recall.
    """
    payload = json.dumps(
        {
            "ticket_id": ticket["ticket_id"],
            "title": ticket.get("title"),
            "description": ticket.get("description"),
            "transcript_excerpt": transcript[-4000:],
            "resolution": resolution,
        }
    )
    _memory.create_event(
        memory_id=MEMORY_ID,
        actor_id=ticket["requester_id"],
        session_id=ticket["ticket_id"],
        event_timestamp=datetime.now(timezone.utc).isoformat() + "Z",
        payload=[{"blob": payload}],
    )


def _build_query(ticket: dict) -> str:
    return (
        f"Ticket {ticket['ticket_id']} from user {ticket['requester_id']} "
        f"(priority {ticket.get('priority', 'MEDIUM')}).\n"
        f"Title: {ticket.get('title', '')}\n"
        f"Description: {ticket.get('description', '')}\n\n"
        "Diagnose and resolve following the system instructions."
    )


@app.entrypoint
def invoke(payload):
    ticket = payload if isinstance(payload, dict) else json.loads(payload)
    logger.info("processing ticket %s", ticket["ticket_id"])

    asyncio.run(_fetch_gateway_token(access_token=""))
    user_token = _gateway_token["value"]

    def _transport():
        return streamablehttp_client(
            GATEWAY_URL,
            headers={"Authorization": f"Bearer {user_token}"},
        )

    with MCPClient(_transport) as gateway:
        tools = gateway.list_tools_sync()
        logger.info("loaded %d tools from gateway", len(tools))

        agent = Agent(
            model=MODEL_ID,
            system_prompt=SYSTEM_PROMPT,
            tools=tools,
            name="ITIncidentResponder",
        )
        result = agent(_build_query(ticket))

    resolution = result.message["content"][0]["text"]
    transcript = json.dumps(result.message, default=str)

    _resolve_ticket(ticket["ticket_id"], resolution)
    _record_episode(ticket, transcript, resolution)

    return {
        "ticket_id": ticket["ticket_id"],
        "status": "Resolved",
        "resolution": resolution,
    }


if __name__ == "__main__":
    app.run()
