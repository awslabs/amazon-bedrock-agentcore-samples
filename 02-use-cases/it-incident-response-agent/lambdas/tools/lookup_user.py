"""Gateway tool: lookup_user.

Returns the requester's profile and quotas. Recurring-incident history
lives in AgentCore Memory (keyed per actor) — the agent surfaces it from
there rather than from a parallel DynamoDB store.
"""

import json
import logging
import os

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

USERS_TABLE = os.environ["USERS_TABLE"]

_ddb = boto3.resource("dynamodb")
_users = _ddb.Table(USERS_TABLE)


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

    return _ok(
        {
            "user_id": user_id,
            "profile": user,
            "quotas": user.get("quotas", {}),
        }
    )
