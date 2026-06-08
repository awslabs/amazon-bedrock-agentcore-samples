"""Gateway tool: create_change_request.

Records a corrective action against a ticket and stamps the user's record.
This is the agent's "make a change" action — demonstrating tool-driven mutation.
"""

import logging
import os
import uuid
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

CHANGES_TABLE = os.environ["CHANGES_TABLE"]
USERS_TABLE = os.environ["USERS_TABLE"]

_ddb = boto3.resource("dynamodb")
_changes = _ddb.Table(CHANGES_TABLE)
_users = _ddb.Table(USERS_TABLE)


# Gateway Lambda targets return the tool result DIRECTLY to the model — no
# API-Gateway-style {statusCode, body} envelope. Errors are returned as a
# plain {"error": ...} object so the model can read them.
def _ok(body: dict) -> dict:
    return body


def _err(message: str) -> dict:
    return {"error": message}


def lambda_handler(event, context):
    """Create a change request and stamp user record."""
    # STEP: ACT — Execute the corrective action decided by the agent
    logger.info("create_change_request invoked")

    ticket_id = event.get("ticket_id")
    user_id = event.get("user_id")
    summary = event.get("summary")
    action = event.get("action", "manual_intervention")

    if not all([ticket_id, user_id, summary]):
        return _err("ticket_id, user_id, and summary are required")

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
        UpdateExpression="SET last_incident_at = :ts ADD incident_count :one",
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
