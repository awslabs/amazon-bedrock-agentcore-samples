"""Gateway tool: create_change_request.

Records a corrective action against a ticket and stamps the user's record.
This is the agent's "make a change" action — demonstrating tool-driven mutation.
"""

import logging
import os
import re
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

# Input validation constants
MAX_ID_LENGTH = 128
MAX_SUMMARY_LENGTH = 2000
MAX_ACTION_LENGTH = 256
ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-\.@]+$")
ACTION_PATTERN = re.compile(r"^[A-Za-z0-9_\-\.]+$")


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

    # Input validation: enforce type, length, and format constraints
    for field_name, value, max_len, pattern in [
        ("ticket_id", ticket_id, MAX_ID_LENGTH, ID_PATTERN),
        ("user_id", user_id, MAX_ID_LENGTH, ID_PATTERN),
    ]:
        if not isinstance(value, str):
            return _err(f"{field_name} must be a string")
        if len(value) > max_len:
            return _err(f"{field_name} exceeds maximum length of {max_len} characters")
        if not pattern.match(value):
            return _err(f"{field_name} contains invalid characters")

    if not isinstance(summary, str):
        return _err("summary must be a string")
    if len(summary) > MAX_SUMMARY_LENGTH:
        return _err(f"summary exceeds maximum length of {MAX_SUMMARY_LENGTH} characters")

    if not isinstance(action, str):
        return _err("action must be a string")
    if len(action) > MAX_ACTION_LENGTH:
        return _err(f"action exceeds maximum length of {MAX_ACTION_LENGTH} characters")
    if not ACTION_PATTERN.match(action):
        return _err("action contains invalid characters (allowed: alphanumeric, _, -, .)")

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
