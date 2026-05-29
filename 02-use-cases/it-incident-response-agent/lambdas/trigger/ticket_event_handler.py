"""SNS-triggered handler: fan a ticket-created event into the AgentCore Runtime.

Wire-up:
  Mock-Jira ticket published -> SNS topic -> this Lambda -> InvokeAgentRuntime.

Each SNS message body is a JSON ticket dict (see seed-data/sample_ticket.json
for the schema). The handler:

  1. Persists the ticket to DynamoDB (status=Open).
  2. Calls InvokeAgentRuntime with the ticket payload.

Note on auth: the runtime fetches its own Auth0 access token via AgentCore
Identity (`@requires_access_token`, `auth_flow="M2M"`). The trigger Lambda
does NOT mint or pass tokens — that responsibility lives entirely with
AgentCore Identity inside the runtime.
"""

import base64
import json
import logging
import os
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TICKETS_TABLE = os.environ["TICKETS_TABLE"]
AGENT_RUNTIME_ARN = os.environ["AGENT_RUNTIME_ARN"]

_ddb = boto3.resource("dynamodb").Table(TICKETS_TABLE)
_runtime = boto3.client("bedrock-agentcore")


def _persist_ticket(ticket: dict) -> None:
    now = datetime.now(timezone.utc).isoformat()
    _ddb.put_item(
        Item={
            "ticket_id": ticket["ticket_id"],
            "requester_id": ticket["requester_id"],
            "title": ticket.get("title", ""),
            "description": ticket.get("description", ""),
            "priority": ticket.get("priority", "MEDIUM"),
            "status": "Open",
            "created_at": now,
            "updated_at": now,
        }
    )


def lambda_handler(event, context):
    logger.info("ticket_event_handler invoked, records=%d", len(event.get("Records", [])))

    for record in event.get("Records", []):
        message = record["Sns"]["Message"]
        ticket = json.loads(message)
        logger.info("processing ticket %s", ticket.get("ticket_id"))

        _persist_ticket(ticket)

        payload = json.dumps(
            {
                "ticket_id": ticket["ticket_id"],
                "requester_id": ticket["requester_id"],
                "title": ticket.get("title", ""),
                "description": ticket.get("description", ""),
                "priority": ticket.get("priority", "MEDIUM"),
            }
        ).encode()

        resp = _runtime.invoke_agent_runtime(
            agentRuntimeArn=AGENT_RUNTIME_ARN,
            qualifier="DEFAULT",
            payload=base64.b64encode(payload),
        )
        logger.info(
            "AgentCore invoked for ticket %s, status=%s",
            ticket["ticket_id"],
            resp.get("ResponseMetadata", {}).get("HTTPStatusCode"),
        )

    return {"status": "dispatched", "count": len(event.get("Records", []))}
