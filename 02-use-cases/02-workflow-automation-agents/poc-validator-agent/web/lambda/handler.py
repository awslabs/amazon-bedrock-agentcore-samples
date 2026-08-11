"""poc-validator-web-invoke — Lambda proxy in front of the AgentCore Runtime.

Handles two routes, both reached via CloudFront on the same domain as the
page itself:
  POST /api/invoke      — runs the agent, gated by a shared secret header
                           (X-Demo-Key) since the caller is a browser that
                           can't SigV4-sign.
  GET  /share/<id>.json — serves a previously-completed result, publicly, no
                           key required — but capped at 3 views and 30 days
                           via a DynamoDB counter, enforced here rather than
                           trusted to the client.
"""

import json
import os
import re
import time
import uuid

import boto3
from botocore.exceptions import ClientError

RUNTIME_ARN = os.environ["AGENT_RUNTIME_ARN"]
EXPECTED_KEY = os.environ["DEMO_KEY"]
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")
RESULTS_BUCKET = os.environ["RESULTS_BUCKET"]
PUBLIC_BASE_URL = os.environ["PUBLIC_BASE_URL"]
VIEWS_TABLE = os.environ["VIEWS_TABLE"]

MAX_VIEWS = 3
SHARE_TTL_SECONDS = 30 * 24 * 3600

_region = os.environ.get("AWS_REGION", "us-east-1")
_client = boto3.client("bedrock-agentcore", region_name=_region)
_s3 = boto3.client("s3", region_name=_region)
_views_table = boto3.resource("dynamodb", region_name=_region).Table(VIEWS_TABLE)

_CORS_HEADERS = {
    "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "content-type, x-demo-key",
}


def _response(status, body_obj):
    return {
        "statusCode": status,
        "headers": {**_CORS_HEADERS, "Content-Type": "application/json"},
        "body": json.dumps(body_obj),
    }


def _reassemble_sse(raw_text):
    """invoke_agent_runtime's response is Server-Sent Events: one `data: "<chunk>"`
    line per yielded chunk, each chunk a JSON-encoded string. Decode each line
    and concatenate to get back the plain text the entrypoint actually yielded.
    """
    parts = []
    for line in raw_text.split("\n"):
        line = line.strip()
        if not line.startswith("data:"):
            continue
        content = line[len("data:"):].strip()
        try:
            parts.append(json.loads(content))
        except json.JSONDecodeError:
            parts.append(content)
    return "".join(parts) if parts else raw_text


def _extract_trailing_json(raw_text):
    """The runtime streams phase-progress text, then ends with one JSON object.

    Scan from the end for a '{' whose decoded object's closing brace lands
    exactly at the end of the text — the outermost trailing object, not a
    nested one inside it. Same tail-JSON approach already used elsewhere in
    this project for CLI output.
    """
    trimmed = _reassemble_sse(raw_text).rstrip()
    decoder = json.JSONDecoder()
    for match in reversed(list(re.finditer(r"\{", trimmed))):
        start = match.start()
        try:
            obj, end = decoder.raw_decode(trimmed, start)
        except json.JSONDecodeError:
            continue
        if end == len(trimmed):
            return obj
    return None


def _handle_invoke(event):
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    if headers.get("x-demo-key") != EXPECTED_KEY:
        return _response(401, {"status": "error", "message": "Missing or invalid demo key."})

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _response(400, {"status": "error", "message": "Body must be JSON."})

    sow_text = (body.get("sow_text") or "").strip()
    diagram_text = body.get("diagram_text") or ""
    diagram_filename = body.get("diagram_filename") or "diagram.mmd"
    segment = body.get("segment") or "enterprise"
    industry = body.get("industry") or "generic"
    region = body.get("region") or "us-east-1"

    if not sow_text and not diagram_text:
        return _response(400, {"status": "error", "message": "Provide at least an SOW document or a diagram."})

    # A stable per-browser id (generated client-side, kept in localStorage) so
    # AgentCore Memory's USER_PREFERENCE strategy has a real, consistent actor
    # to attach preferences to instead of every visitor sharing one identity.
    # Validated strictly — this becomes part of a Memory namespace string.
    browser_id = body.get("browser_id") or ""
    if not re.fullmatch(r"[a-f0-9]{32}", browser_id):
        browser_id = "anonymous"

    payload = {
        "segment": segment,
        "industry": industry,
        "region": region,
        "sow_text": sow_text,
        "diagram_text": diagram_text,
        "diagram_filename": diagram_filename,
        "user_id": f"web-{browser_id}",
    }

    try:
        result = _client.invoke_agent_runtime(
            agentRuntimeArn=RUNTIME_ARN,
            runtimeSessionId=f"web-{uuid.uuid4().hex}",
            payload=json.dumps(payload).encode("utf-8"),
            contentType="application/json",
            accept="application/json",
        )
        raw = result["response"].read().decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001 — surface any failure as a clean JSON error
        return _response(502, {"status": "error", "message": f"Agent invocation failed: {exc}"})

    parsed = _extract_trailing_json(raw)
    if parsed is None:
        return _response(502, {"status": "error", "message": "Could not parse agent response.", "raw_tail": raw[-2000:]})

    if parsed.get("status") == "complete":
        # The entrypoint's result never echoes the raw SOW/diagram text back —
        # only the analysis (findings, sow scoring, cost, recommendations) —
        # so what lands in the public share/ prefix is already safe to expose.
        run_id = uuid.uuid4().hex
        expires_at = int(time.time()) + SHARE_TTL_SECONDS
        try:
            _s3.put_object(
                Bucket=RESULTS_BUCKET,
                Key=f"share/{run_id}.json",
                Body=json.dumps(parsed).encode("utf-8"),
                ContentType="application/json",
                CacheControl="no-store",  # view-count enforcement needs every read to hit the Lambda
                Tagging="AutoExpire=true",
            )
            _views_table.put_item(Item={"share_id": run_id, "view_count": 0, "ttl": expires_at})
            parsed["share_url"] = f"{PUBLIC_BASE_URL}/share/view.html?id={run_id}"
        except Exception as exc:  # noqa: BLE001 — sharing is a bonus, never block the result on it
            parsed["share_url"] = None
            parsed["share_error"] = str(exc)

    return _response(200, parsed)


def _check_and_increment_view(share_id):
    """Atomically claim one of the 3 allowed views. Returns a dict describing
    the outcome so the caller can give a precise error rather than a generic
    403 — worth doing since "never existed" and "viewed out" are different
    situations for someone clicking a stale link.
    """
    try:
        resp = _views_table.update_item(
            Key={"share_id": share_id},
            UpdateExpression="ADD view_count :incr",
            ConditionExpression="attribute_exists(share_id) AND view_count < :max",
            ExpressionAttributeValues={":incr": 1, ":max": MAX_VIEWS},
            ReturnValues="UPDATED_NEW",
        )
        return {"ok": True, "view_count": int(resp["Attributes"]["view_count"])}
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        existing = _views_table.get_item(Key={"share_id": share_id}).get("Item")
        return {"ok": False, "reason": "not_found" if existing is None else "limit_reached"}


def _handle_share_read(share_id):
    if not re.fullmatch(r"[a-f0-9]{32}", share_id or ""):
        return _response(404, {"status": "error", "message": "Not a valid share link."})

    outcome = _check_and_increment_view(share_id)
    if not outcome["ok"]:
        if outcome["reason"] == "not_found":
            return _response(404, {"status": "error", "message": "This link has expired or never existed."})
        return _response(403, {"status": "error", "message": "This shared result has already been viewed the maximum of 3 times."})

    try:
        obj = _s3.get_object(Bucket=RESULTS_BUCKET, Key=f"share/{share_id}.json")
        data = json.loads(obj["Body"].read())
    except ClientError:
        return _response(404, {"status": "error", "message": "This link has expired or never existed."})

    data["_views_remaining"] = MAX_VIEWS - outcome["view_count"]
    return _response(200, data)


def handler(event, context):
    method = (event.get("requestContext", {}).get("http", {}) or {}).get("method", "")
    path = event.get("rawPath") or (event.get("requestContext", {}).get("http", {}) or {}).get("path", "")

    if method == "OPTIONS":
        return {"statusCode": 204, "headers": _CORS_HEADERS, "body": ""}

    share_match = re.fullmatch(r"/share/([a-f0-9]{32})\.json", path)
    if method == "GET" and share_match:
        return _handle_share_read(share_match.group(1))

    if method == "POST":
        return _handle_invoke(event)

    return _response(404, {"status": "error", "message": "Not found."})
