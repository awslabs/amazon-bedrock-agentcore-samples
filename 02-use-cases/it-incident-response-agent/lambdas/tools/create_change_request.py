"""Gateway tool: create_change_request.

Writes/updates an incident-linked change record in the ChangeRequests table
and stamps the customer's record (last_incident_at, incident_count). This is
the agent's "make a change" action, demonstrating tool-driven mutation.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CHANGES_TABLE = os.environ["CHANGES_TABLE"]
USERS_TABLE = os.environ["USERS_TABLE"]

_ddb = boto3.resource("dynamodb")
_changes = _ddb.Table(CHANGES_TABLE)
_users = _ddb.Table(USERS_TABLE)


def _ok(body):
    return {"statusCode": 200, "body": json.dumps(body, default=str)}


def _err(message, status=400):
    return {"statusCode": status, "body": json.dumps({"error": message})}


def lambda_handler(event, context):
    logger.info("create_change_request invoked, event=%s", event)

    ticket_id = event.get("ticket_id")
    user_id = event.get("user_id")
    summary = event.get("summary")
    action = event.get("action", "manual_intervention")

    if not all([ticket_id, user_id, summary]):
        return _err("ticket_id, user_id, summary are required")

    now = datetime.now(timezone.utc).isoformat()
    change_id = f"CHG-{uuid.uuid4().hex[:8].upper()}"

    _changes.put_item(
        Item={
            "change_id": change_id,
            "ticket_id": ticket_id,
            "user_id": user_id,
            "summary": summary,
            "action": action,
            "created_at": now,
            "status": "applied",
        }
    )

    _users.update_item(
        Key={"user_id": user_id},
        UpdateExpression=(
            "SET last_incident_at = :ts "
            "ADD incident_count :one "
        ),
        ExpressionAttributeValues={":ts": now, ":one": 1},
    )

    return _ok(
        {
            "change_id": change_id,
            "ticket_id": ticket_id,
            "user_id": user_id,
            "applied_at": now,
            "status": "applied",
        }
    )
