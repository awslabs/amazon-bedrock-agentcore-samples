"""IT Incident Response Agent — AgentCore Runtime entrypoint (v3, CLI-first).

Flow per invocation:
  1. Receive ticket payload from the trigger Lambda via AgentCore Runtime.
     Supports two modes:
       - Full ticket: {ticket_id, requester_id, title, description, priority}
       - Jira issue key: {issue_key, requester_id} (when Jira integration enabled)
  2. Retrieve past-incident summaries from AgentCore Memory for context.
  3. Connect to MCP servers (Gateway + optionally Atlassian Remote MCP).
  4. Run a Strands agent with aggregated tools from all servers.
  5. Record the run as an episode in AgentCore Memory.
  6. Write resolution (DDB for full-ticket mode, Jira comment for issue-key mode).
  7. On failure: mark ticket as Failed with error context.
"""

import json
import logging
import os
from datetime import datetime, timezone

import boto3
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from model.load import load_model
from mcp_client.client import get_all_mcp_clients, get_all_mcp_clients_safe, get_streamable_http_mcp_client
from mcp_client.jira import JIRA_MCP_URL, JIRA_SITE_URL, JIRA_PROJECT_KEY
from memory.session import get_memory_session_manager
from memory.enrichment import (
    retrieve_past_incidents,
    format_past_incidents_block,
)
from strands import Agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("it-incident-agent")

# Configuration from environment (injected by CDK via agentcore deploy)
# The L3 construct uses AGENTCORE_GATEWAY_{NAME}_URL naming convention.
GATEWAY_URL = os.environ.get("GATEWAY_URL") or os.environ.get("AGENTCORE_GATEWAY_ITINCIDENTGATEWAY_URL", "")
MEMORY_ID = os.environ.get("MEMORY_ID") or os.environ.get("MEMORY_ITINCIDENTAGENTMEMORY_ID", "")
TICKETS_TABLE = os.environ.get("TICKETS_TABLE", "")
REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-west-2"))
EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "default")
GUARDRAIL_ID = os.environ.get("GUARDRAIL_ID", "")
GUARDRAIL_VERSION = os.environ.get("GUARDRAIL_VERSION", "DRAFT")

app = BedrockAgentCoreApp()
log = app.logger

# DynamoDB resource for ticket status updates
_ddb = boto3.resource("dynamodb", region_name=REGION)
_events = boto3.client("events", region_name=REGION)
_bedrock_runtime = boto3.client("bedrock-runtime", region_name=REGION)

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

SYSTEM_PROMPT_JIRA = """You are an IT Incident Response Agent.

You receive a Jira issue key. Your job is to:
  1. Fetch the issue from Jira (use the jira-prefixed tools — e.g.
     `jira___getIssue` or whichever the server exposes for reading an
     issue by key).
  2. Diagnose the incident using the IT-side tools available via the
     AgentCore Gateway:
       - lookup_user (requester profile + quotas)
       - get_process_info (status of named services / apps / assets)
       - query_kb (relevant runbook guidance)
       - create_change_request (only when the runbook justifies an action)
  3. Write a clear, concise resolution comment on the Jira issue (3-6
     sentences) using the jira-prefixed addComment tool.
  4. Transition the issue to a resolved/done state using the jira-prefixed
     transition tool.

Rules:
  - The site to operate on is {jira_site_url}, project {jira_project_key}.
  - Don't open a change request unless a runbook supports the action.
  - Keep the resolution comment user-facing — no chain-of-thought,
    no tool-call narration.
  - Treat the recurring-incident signal below as ground truth: if the
    requester has 2 or more past episodes, escalate (mention recurrence
    in the resolution comment and create a change request when a runbook
    supports it).

{past_incidents_block}
Return the resolution comment as your final message.
"""


def _resolve_ticket(ticket_id: str, comment: str) -> None:
    """Mark ticket as Resolved with the agent's resolution comment."""
    if not TICKETS_TABLE:
        logger.warning("TICKETS_TABLE not set, skipping ticket update")
        return
    now = datetime.now(timezone.utc).isoformat()
    table = _ddb.Table(TICKETS_TABLE)
    table.update_item(
        Key={"ticket_id": ticket_id},
        UpdateExpression=(
            "SET #s = :s, resolution_comment = :c, resolved_at = :t, updated_at = :t"
        ),
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "Resolved",
            ":c": comment,
            ":t": now,
        },
    )


def _fail_ticket(ticket_id: str, error: str) -> None:
    """Mark ticket as Failed with error context."""
    if not TICKETS_TABLE:
        return
    now = datetime.now(timezone.utc).isoformat()
    table = _ddb.Table(TICKETS_TABLE)
    table.update_item(
        Key={"ticket_id": ticket_id},
        UpdateExpression="SET #s = :s, error_message = :e, updated_at = :t",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "Failed",
            ":e": error[:1000],
            ":t": now,
        },
    )


def _emit_resolution_event(ticket_id: str, resolution: str, requester_id: str) -> None:
    """Emit a TicketResolved event to EventBridge for downstream consumers.

    Completes the Trigger → Enrich → Reason → Act → **Emit** pattern.
    Downstream consumers (dashboards, notification systems, audit trails)
    can subscribe to this event via EventBridge rules.
    """
    try:
        _events.put_events(
            Entries=[
                {
                    "Source": "it-incident-agent",
                    "DetailType": "TicketResolved",
                    "Detail": json.dumps({
                        "ticket_id": ticket_id,
                        "requester_id": requester_id,
                        "resolution": resolution[:500],
                        "resolved_at": datetime.now(timezone.utc).isoformat(),
                    }),
                    "EventBusName": EVENT_BUS_NAME,
                }
            ]
        )
        logger.info("Emitted TicketResolved event for %s", ticket_id)
    except Exception:
        logger.exception("Failed to emit EventBridge event (non-fatal)")


def _apply_guardrail(text: str) -> str:
    """Apply Bedrock Guardrails to filter PII and inappropriate content.

    Event payloads can contain messy data — PII, profanity, or injection
    attempts. The guardrail sanitizes the input before it reaches the model.
    Returns the sanitized text, or original if no guardrail is configured.
    """
    if not GUARDRAIL_ID:
        return text  # No guardrail configured — pass through

    try:
        response = _bedrock_runtime.apply_guardrail(
            guardrailIdentifier=GUARDRAIL_ID,
            guardrailVersion=GUARDRAIL_VERSION,
            source="INPUT",
            content=[{"text": {"text": text}}],
        )
        action = response.get("action", "NONE")
        if action == "GUARDRAIL_INTERVENED":
            # Guardrail blocked or modified the content
            outputs = response.get("outputs", [])
            if outputs:
                sanitized = outputs[0].get("text", text)
                logger.info("Guardrail intervened: replaced content (action=%s)", action)
                return sanitized
            logger.warning("Guardrail intervened but no output — using original")
        return text
    except Exception:
        logger.exception("Guardrail application failed (non-fatal, using original)")
        return text


def _build_query(ticket: dict) -> str:
    """Construct the agent query from the ticket payload."""
    return (
        f"Ticket {ticket['ticket_id']} from user {ticket['requester_id']} "
        f"(priority {ticket.get('priority', 'MEDIUM')}).\n"
        f"Title: {ticket.get('title', '')}\n"
        f"Description: {ticket.get('description', '')}\n\n"
        "Diagnose and resolve following the system instructions."
    )


@app.entrypoint
async def invoke(payload, context):
    """Main entrypoint called by AgentCore Runtime."""
    log.info("Invoking IT Incident Response Agent...")

    # Determine if this is a ticket processing request or a simple prompt
    if isinstance(payload, str):
        payload = json.loads(payload) if payload.startswith("{") else {"prompt": payload}

    # Simple prompt mode (for testing / dev server)
    if "prompt" in payload and "ticket_id" not in payload and "issue_key" not in payload:
        session_id = getattr(context, "session_id", "default-session")
        user_id = getattr(context, "user_id", "default-user")

        mcp_clients, tool_warnings = get_all_mcp_clients_safe()
        tools = mcp_clients if mcp_clients else []

        try:
            if tool_warnings:
                logger.warning(
                    "Running in degraded mode (some tools unavailable): %s",
                    "; ".join(tool_warnings)
                )
            
            agent = Agent(
                model=load_model(),
                session_manager=get_memory_session_manager(session_id, user_id),
                system_prompt=SYSTEM_PROMPT,
                tools=tools,
            )
        except Exception as agent_init_exc:
            logger.warning(
                "Agent initialization with tools failed (%s: %s). "
                "Falling back to LLM-only mode.",
                type(agent_init_exc).__name__,
                agent_init_exc,
                exc_info=True
            )
            
            # Create agent without tools
            agent = Agent(
                model=load_model(),
                session_manager=get_memory_session_manager(session_id, user_id),
                system_prompt=SYSTEM_PROMPT,
                tools=[],
            )

        stream = agent.stream_async(payload.get("prompt"))
        async for event in stream:
            if "data" in event and isinstance(event["data"], str):
                yield event["data"]
        return

    # ─── Detect mode: issue_key (Jira) vs ticket_id (DDB mock) ─────
    is_jira_mode = "issue_key" in payload and JIRA_MCP_URL
    ticket_id = payload.get("issue_key") if is_jira_mode else payload["ticket_id"]
    requester_id = payload.get("requester_id", ticket_id)
    priority = payload.get("priority", "MEDIUM")

    logger.info(
        "Processing %s %s (priority=%s, mode=%s)",
        "issue" if is_jira_mode else "ticket",
        ticket_id,
        priority,
        "jira" if is_jira_mode else "ddb",
    )

    try:
        # STEP: GUARDRAIL — Sanitize event payload before model invocation
        if not is_jira_mode:
            sanitized_description = _apply_guardrail(payload.get("description", ""))
            payload_for_agent = {**payload, "description": sanitized_description}
        else:
            payload_for_agent = payload

        # STEP: MEMORY ENRICHMENT — Retrieve past incidents for this requester
        past_incidents = retrieve_past_incidents(
            requester_id=requester_id,
            query=f"prior incidents for {requester_id}",
        )

        # STEP: BUILD SYSTEM PROMPT — Inject memory context
        if is_jira_mode:
            past_block = format_past_incidents_block(past_incidents)
            system_prompt = SYSTEM_PROMPT_JIRA.format(
                jira_site_url=JIRA_SITE_URL,
                jira_project_key=JIRA_PROJECT_KEY,
                past_incidents_block=past_block,
            )
        else:
            # DDB mode — append past incidents context to the standard prompt
            if past_incidents:
                past_block = format_past_incidents_block(past_incidents)
                system_prompt = SYSTEM_PROMPT + f"\n\n{past_block}"
            else:
                system_prompt = SYSTEM_PROMPT

        # STEP: MULTI-MCP — Connect to Gateway + optionally Jira with safe fallback
        mcp_clients, tool_warnings = get_all_mcp_clients_safe()
        tools = mcp_clients if mcp_clients else []
        
        # Try to create the agent with available tools, gracefully degrade if tool loading fails
        try:
            if tool_warnings:
                logger.warning(
                    "Running in degraded mode (some tools unavailable). "
                    "Failures: %s. Attempting with available tools.",
                    "; ".join(tool_warnings)
                )
            
            agent = Agent(
                model=load_model(priority),
                session_manager=get_memory_session_manager(ticket_id, requester_id),
                system_prompt=system_prompt,
                tools=tools,
            )
        except Exception as agent_init_exc:
            # Tool loading failed even with available clients — fall back to LLM-only
            logger.warning(
                "Agent initialization with tools failed (%s: %s). "
                "Falling back to LLM-only mode.",
                type(agent_init_exc).__name__,
                agent_init_exc,
                exc_info=True
            )
            tool_warnings.append(f"Agent tool initialization failed: {type(agent_init_exc).__name__}: {agent_init_exc}")
            
            # Create agent without tools
            agent = Agent(
                model=load_model(priority),
                session_manager=get_memory_session_manager(ticket_id, requester_id),
                system_prompt=system_prompt,
                tools=[],
            )

        # STEP: ENRICH + REASON + ACT — Run the agent
        if is_jira_mode:
            user_query = (
                f"Resolve Jira issue {ticket_id} in project {JIRA_PROJECT_KEY} "
                f"on site {JIRA_SITE_URL}. Follow the system instructions."
            )
        else:
            user_query = _build_query(payload_for_agent)

        result = agent(user_query)

        # Extract resolution text
        resolution = result.message["content"][0]["text"]

        # STEP: MEMORY — Persistence is handled by the AgentCoreMemorySessionManager
        # attached to the Agent above; it writes the conversation turn (and the
        # SUMMARIZATION strategy rolls it into the per-requester namespace).
        # No separate create_event call is needed here (avoids a double-write).

        # STEP: ACT — Write resolution to ticket store (DDB mode only)
        # In Jira mode, the agent already commented + transitioned via MCP tools.
        if not is_jira_mode:
            _resolve_ticket(ticket_id, resolution)

        # STEP: EMIT — Publish downstream event for consumers
        _emit_resolution_event(ticket_id, resolution, requester_id)

        logger.info("%s %s resolved successfully", "Issue" if is_jira_mode else "Ticket", ticket_id)
        yield json.dumps({
            "ticket_id": ticket_id,
            "status": "Resolved",
            "resolution": resolution,
            "mode": "jira" if is_jira_mode else "ddb",
            "recurring_incident_count": len(past_incidents),
        })

    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {exc}"
        logger.exception("Failed to process %s", ticket_id)

        try:
            if not is_jira_mode:
                _fail_ticket(ticket_id, error_msg)
        except Exception:
            logger.exception("Failed to mark ticket %s as Failed", ticket_id)

        yield json.dumps({
            "ticket_id": ticket_id,
            "status": "Failed",
            "error": error_msg,
        })


if __name__ == "__main__":
    app.run()
