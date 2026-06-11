"""Async AWS Lambda: invokes Amazon Bedrock AgentCore to generate GEO content.

Triggered asynchronously by geo_content_handler on cache miss.
Handles key mismatch between the handler's composite key (CloudFront host)
and the agent's key (origin host) by checking both and copying content.
Records timing metrics for observability.
"""

import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import urlparse

import boto3

TABLE_NAME = os.environ.get("GEO_TABLE_NAME", "geo-content")
AGENT_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN", "")
AGENTCORE_REGION = os.environ.get("AGENTCORE_REGION", "us-east-1")
GEO_TTL_SECONDS = int(os.environ.get("GEO_TTL_SECONDS", "86400"))  # 24h default

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)


def _invoke_agentcore(url: str) -> str | None:
    """Invoke the Amazon Bedrock AgentCore agent to generate GEO content for a URL."""
    if not AGENT_RUNTIME_ARN:
        print("AGENT_RUNTIME_ARN not set, skipping")
        return None

    client = boto3.client("bedrock-agentcore", region_name=AGENTCORE_REGION)
    prompt = f"Generate GEO-optimized content and store to DynamoDB: {url}"
    payload = json.dumps({"prompt": prompt}).encode()
    session_id = str(uuid.uuid4())

    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=AGENT_RUNTIME_ARN,
            runtimeSessionId=session_id,
            payload=payload,
        )

        content_type = response.get("contentType", "")
        parts = []

        if "text/event-stream" in content_type:
            for line in response["response"].iter_lines(chunk_size=10):
                if line:
                    decoded = line.decode("utf-8")
                    if decoded.startswith("data: "):
                        parts.append(decoded[6:])
        else:
            for chunk in response.get("response", []):
                if isinstance(chunk, bytes):
                    parts.append(chunk.decode("utf-8"))
                else:
                    parts.append(str(chunk))

        return "".join(parts) if parts else None

    except Exception as e:
        print(f"AgentCore invocation failed: {e}")
        return None


def handler(event, context):
    """Async handler: generate GEO content and store in DDB."""
    generator_start = time.time()
    url_path = event.get("url_path", "/")
    original_url = event.get("original_url", url_path)
    host = event.get("host", "")
    trigger_mode = event.get("mode", "async")

    print(f"Generating GEO content for {original_url} (path: {url_path})")

    start_time = time.time()
    agent_response = _invoke_agentcore(original_url)
    agent_duration_ms = int((time.time() - start_time) * 1000)

    if not agent_response:
        print(f"AgentCore returned no content for {url_path}")
        return {"status": "failed", "url_path": url_path}

    item = None
    agent_ddb_key = None

    try:
        response = table.get_item(Key={"url_path": url_path}, ConsistentRead=True)
        item = response.get("Item")
    except Exception as e:
        print(f"DDB read failed for {url_path}: {e}")

    if not item or not item.get("geo_content"):
        parsed = urlparse(original_url)
        origin_host = parsed.netloc
        if origin_host:
            agent_path = parsed.path or "/"
            if parsed.query:
                agent_path = f"{agent_path}?{parsed.query}"
            agent_ddb_key = f"{origin_host}#{agent_path}"
            if agent_ddb_key != url_path:
                try:
                    response = table.get_item(
                        Key={"url_path": agent_ddb_key}, ConsistentRead=True
                    )
                    item = response.get("Item")
                    if item and item.get("geo_content"):
                        print(
                            f"Found agent content at {agent_ddb_key}, "
                            f"will copy to {url_path}"
                        )
                except Exception as e:
                    print(f"DDB read failed for {agent_ddb_key}: {e}")

    now = datetime.now(timezone.utc).isoformat()
    generator_duration_ms = int((time.time() - generator_start) * 1000)

    if item and item.get("geo_content"):
        gc = item["geo_content"].strip()
        if not (gc.startswith("<") or gc.lower().startswith("<!doctype")):
            print(
                f"Skipping non-HTML content at {agent_ddb_key or url_path}: "
                f"{gc[:80]}..."
            )
            try:
                table.delete_item(Key={"url_path": url_path})
            except Exception:
                pass
            return {"status": "failed", "url_path": url_path, "reason": "non_html_content"}
        try:
            full_item = {
                "url_path": url_path,
                "status": "ready",
                "geo_content": item["geo_content"],
                "content_type": item.get("content_type", "text/html; charset=utf-8"),
                "original_url": original_url,
                "created_at": item.get("created_at", now),
                "updated_at": now,
                "generation_duration_ms": Decimal(str(agent_duration_ms)),
                "generator_duration_ms": Decimal(str(generator_duration_ms)),
                "mode": trigger_mode,
                "ttl": int(time.time()) + GEO_TTL_SECONDS,
            }
            if host:
                full_item["host"] = host

            if "original_score" in item:
                full_item["original_score"] = item["original_score"]
            if "geo_score" in item:
                full_item["geo_score"] = item["geo_score"]
            if "score_improvement" in item:
                full_item["score_improvement"] = item["score_improvement"]
            
            table.put_item(Item=full_item)
        except Exception as e:
            print(f"Failed to store content: {e}")

        print(
            f"GEO content ready for {url_path} "
            f"(agent: {agent_duration_ms}ms, generator: {generator_duration_ms}ms)"
        )
        return {
            "status": "success",
            "url_path": url_path,
            "agent_duration_ms": agent_duration_ms,
            "generator_duration_ms": generator_duration_ms,
        }

    # Try to extract HTML from raw agent response as fallback
    html_match = re.search(
        r"(<(?:!DOCTYPE html|html|article|section|div|main|head)[\s>].*)",
        agent_response,
        re.DOTALL | re.IGNORECASE,
    )
    if html_match:
        geo_content = html_match.group(1).strip()
    else:
        print(
            f"No HTML content found in agent response for {url_path}, "
            f"marking as failed"
        )
        try:
            table.delete_item(Key={"url_path": url_path})
        except Exception:
            pass
        return {"status": "failed", "url_path": url_path, "reason": "no_html_in_response"}

    try:
        fallback_item = {
            "url_path": url_path,
            "status": "ready",
            "geo_content": geo_content,
            "content_type": "text/html; charset=utf-8",
            "original_url": original_url,
            "created_at": now,
            "updated_at": now,
            "generation_duration_ms": Decimal(str(agent_duration_ms)),
            "generator_duration_ms": Decimal(str(generator_duration_ms)),
            "mode": trigger_mode,
            "source": "fallback",
            "ttl": int(time.time()) + GEO_TTL_SECONDS,
        }
        if host:
            fallback_item["host"] = host
        table.put_item(Item=fallback_item)
        print(
            f"Stored extracted HTML for {url_path} "
            f"(agent: {agent_duration_ms}ms, generator: {generator_duration_ms}ms)"
        )
    except Exception as e:
        print(f"Failed to store content: {e}")
        try:
            table.delete_item(Key={"url_path": url_path})
        except Exception:
            pass
        return {"status": "failed", "url_path": url_path}

    return {
        "status": "success",
        "url_path": url_path,
        "agent_duration_ms": agent_duration_ms,
        "generator_duration_ms": generator_duration_ms,
    }
