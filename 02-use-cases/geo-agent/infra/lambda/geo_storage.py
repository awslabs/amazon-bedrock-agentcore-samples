"""AWS Lambda: stores GEO-optimized content in Amazon DynamoDB.

Called by the agent's store_geo_content tool via lambda:InvokeFunction.
This decouples the agent from Amazon DynamoDB — the agent only needs
lambda:InvokeFunction permission.

Supports two actions:
  - store (default): Write a full GEO content record.
  - update_scores: Update only score fields on an existing record.

Includes HTML validation as a last line of defense — rejects content
that doesn't start with '<'.
"""

import json
import os
import time
from datetime import datetime, timezone

import boto3

TABLE_NAME = os.environ.get("GEO_TABLE_NAME", "geo-content")
GEO_TTL_SECONDS = int(os.environ.get("GEO_TTL_SECONDS", "86400"))

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)


def handler(event, context):
    """Route to store or update_scores based on the action field."""
    # Support both direct dict and JSON string payload
    if isinstance(event, str):
        event = json.loads(event)

    action = event.get("action", "store")

    if action == "update_scores":
        return _update_scores(event)

    return _store_content(event)


def _update_scores(event):
    """Update only score fields on an existing Amazon DynamoDB record."""
    url_path = event.get("url_path")
    if not url_path:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "url_path is required"}),
        }

    host = event.get("host", "")
    ddb_key = f"{host}#{url_path}" if host else url_path

    original_score = event.get("original_score")
    geo_score = event.get("geo_score")
    if not original_score and not geo_score:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "at least one score field is required"}),
        }

    now = datetime.now(timezone.utc).isoformat()
    update_parts = ["#u = :now"]
    attr_names = {"#u": "updated_at"}
    attr_values = {":now": now}

    if original_score:
        update_parts.append("original_score = :os")
        attr_values[":os"] = original_score

    if geo_score:
        update_parts.append("geo_score = :gs")
        attr_values[":gs"] = geo_score

    if original_score and geo_score:
        if "overall_score" in original_score and "overall_score" in geo_score:
            from decimal import Decimal
            improvement = Decimal(str(geo_score["overall_score"])) - Decimal(str(original_score["overall_score"]))
            update_parts.append("score_improvement = :si")
            attr_values[":si"] = improvement

    try:
        table.update_item(
            Key={"url_path": ddb_key},
            UpdateExpression="SET " + ", ".join(update_parts),
            ExpressionAttributeNames=attr_names,
            ExpressionAttributeValues=attr_values,
        )
        return {
            "statusCode": 200,
            "body": json.dumps({"status": "scores_updated", "ddb_key": ddb_key}),
        }
    except Exception as e:
        print(f"Score update failed: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }


def _store_content(event):
    """Validate and store a full GEO content record in Amazon DynamoDB."""

    url_path = event.get("url_path")
    geo_content = event.get("geo_content")

    if not url_path or not geo_content:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "url_path and geo_content are required"}),
        }

    # Reject non-HTML content
    stripped = geo_content.strip()
    if not (stripped.startswith("<") or stripped.lower().startswith("<!doctype")):
        print(f"Rejected non-HTML content for {url_path}: {stripped[:80]}...")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "geo_content must be HTML (must start with '<')"}),
        }

    host = event.get("host", "")
    ddb_key = f"{host}#{url_path}" if host else url_path

    now = datetime.now(timezone.utc).isoformat()

    item = {
        "url_path": ddb_key,
        "status": "ready",
        "geo_content": geo_content,
        "content_type": event.get("content_type", "text/html; charset=utf-8"),
        "original_url": event.get("original_url", url_path),
        "created_at": now,
        "updated_at": now,
        "ttl": int(time.time()) + GEO_TTL_SECONDS,
    }

    if host:
        item["host"] = host

    gen_ms = event.get("generation_duration_ms")
    if gen_ms is not None:
        from decimal import Decimal
        item["generation_duration_ms"] = Decimal(str(gen_ms))

    original_score = event.get("original_score")
    if original_score:
        item["original_score"] = original_score

    geo_score = event.get("geo_score")
    if geo_score:
        item["geo_score"] = geo_score
        if original_score and "overall_score" in original_score and "overall_score" in geo_score:
            from decimal import Decimal
            improvement = Decimal(str(geo_score["overall_score"])) - Decimal(str(original_score["overall_score"]))
            item["score_improvement"] = improvement

    try:
        table.put_item(Item=item)
        return {
            "statusCode": 200,
            "body": json.dumps({
                "status": "stored",
                "url_path": url_path,
                "ddb_key": ddb_key,
                "content_length": len(geo_content),
            }),
        }
    except Exception as e:
        print(f"DDB write failed: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }
