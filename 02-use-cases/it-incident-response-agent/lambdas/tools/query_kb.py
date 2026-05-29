"""Gateway tool: query_kb.

Wraps Bedrock Knowledge Base Retrieve so the KB is exposed as a gateway tool
alongside the other Lambda tools. The agent calls this to look up runbooks.
"""

import json
import logging
import os

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

KB_ID = os.environ["KB_ID"]
_kb = boto3.client("bedrock-agent-runtime")


def _ok(body):
    return {"statusCode": 200, "body": json.dumps(body, default=str)}


def _err(message, status=400):
    return {"statusCode": status, "body": json.dumps({"error": message})}


def lambda_handler(event, context):
    logger.info("query_kb invoked, event=%s", event)

    query = event.get("query")
    top_k = int(event.get("top_k", 4))
    if not query:
        return _err("query is required")

    resp = _kb.retrieve(
        knowledgeBaseId=KB_ID,
        retrievalQuery={"text": query},
        retrievalConfiguration={
            "vectorSearchConfiguration": {"numberOfResults": top_k}
        },
    )

    results = [
        {
            "score": r.get("score"),
            "content": r.get("content", {}).get("text", ""),
            "source": (r.get("location", {}).get("s3Location") or {}).get("uri"),
        }
        for r in resp.get("retrievalResults", [])
    ]
    return _ok({"query": query, "results": results})
