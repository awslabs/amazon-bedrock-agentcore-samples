"""Gateway tool: lookup_user.

Returns user profile, quotas, and recent incident history for a given user_id.
The agent uses this to understand requester context and detect recurring incidents.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

USERS_TABLE = os.environ["USERS_TABLE"]
TICKETS_TABLE = os.environ["TICKETS_TABLE"]

_ddb = boto3.resource("dynamodb")
_users = _ddb.Table(USERS_TABLE)
_tickets = _ddb.Table(TICKETS_TABLE)


def _resolve_tool_name(context) -> str:
    raw = (context.client_context.custom or {}).get("bedrockAgentCoreToolName", "")
    delim = "___"
    return raw.split(delim, 1)[1] if delim in raw else raw


def _ok(body):
    return {"statusCode": 200, "body": json.dumps(body, default=str)}


def _err(message, status=400):
    return {"statusCode": status, "body": json.dumps({"error": message})}


def lambda_handler(event, context):
    tool_name = _resolve_tool_name(context)
    logger.info("lookup_user invoked, tool_name=%s, event=%s", tool_name, event)

    user_id = event.get("user_id")
    if not user_id:
        return _err("user_id is required")

    user = _users.get_item(Key={"user_id": user_id}).get("Item")
    if not user:
        return _err(f"user_id {user_id} not found", status=404)

    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    recent = _tickets.query(
        IndexName="byRequester",
        KeyConditionExpression=Key("requester_id").eq(user_id)
        & Key("created_at").gte(cutoff),
        Limit=10,
        ScanIndexForward=False,
    ).get("Items", [])

    return _ok(
        {
            "user_id": user_id,
            "profile": user,
            "quotas": user.get("quotas", {}),
            "recent_tickets": [
                {
                    "ticket_id": t["ticket_id"],
                    "title": t.get("title"),
                    "status": t.get("status"),
                    "created_at": t.get("created_at"),
                }
                for t in recent
            ],
            "recent_incident_count_30d": len(recent),
        }
    )
