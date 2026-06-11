"""AWS Lambda handler: serves GEO content from Amazon DynamoDB.

Supports three cache-miss modes (via querystring ?mode=):
  - passthrough (default): Return original page, trigger async generation.
  - async: Return 202 immediately, trigger async generation.
  - sync: Wait for Amazon Bedrock AgentCore to generate, return GEO content.

Additional querystring controls:
  - ?purge=true: Deletes the Amazon DynamoDB record and invalidates
    Amazon CloudFront cache for the requested path.
  - ?action=scores: Returns an HTML dashboard of GEO scores for the host.

DynamoDB status lifecycle:
  - (no record): First visit, trigger generation.
  - "processing": Generation in progress, don't re-trigger.
  - "ready": GEO content available, serve it.

All records include a TTL field (default 86400s / 24h, configurable via
GEO_TTL_SECONDS). Stale processing records are auto-recovered after
PROCESSING_TIMEOUT_SECONDS (default 300s / 5min).
"""

import json
import os
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import urlencode, urlparse
from urllib.request import urlopen, Request

import boto3
from botocore.exceptions import ClientError

TABLE_NAME = os.environ.get("GEO_TABLE_NAME", "geo-content")
GENERATOR_FUNCTION_NAME = os.environ.get("GENERATOR_FUNCTION_NAME", "")
DEFAULT_ORIGIN_HOST = os.environ.get("DEFAULT_ORIGIN_HOST", "")
AGENT_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN", "")
AGENTCORE_REGION = os.environ.get("AGENTCORE_REGION", "us-east-1")
ORIGIN_VERIFY_SECRET = os.environ.get("ORIGIN_VERIFY_SECRET", "")
GEO_TTL_SECONDS = int(os.environ.get("GEO_TTL_SECONDS", "86400"))  # 24h default
PROCESSING_TIMEOUT_SECONDS = int(os.environ.get("PROCESSING_TIMEOUT_SECONDS", "300"))  # 5min default
CF_DISTRIBUTION_ID = os.environ.get("CF_DISTRIBUTION_ID", "")

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)
lambda_client = boto3.client("lambda")


CONTROL_PARAMS = {"ua", "mode", "purge", "action"}


def _filtered_qs(event):
    """Return sorted querystring without control params, for use in DDB key and origin URL."""
    params = event.get("queryStringParameters") or {}
    filtered = {k: v for k, v in params.items() if k not in CONTROL_PARAMS}
    return urlencode(sorted(filtered.items())) if filtered else ""


def _ddb_key(host, path, qs=""):
    """Build composite DDB key '{host}#{path}[?qs]' for multi-tenancy."""
    full_path = f"{path}?{qs}" if qs else path
    return f"{host}#{full_path}" if host else full_path


def _get_mode(event):
    """Extract the cache-miss mode from querystring (passthrough/async/sync)."""
    params = event.get("queryStringParameters") or {}
    mode = params.get("mode", "passthrough")
    return mode if mode in ("async", "passthrough", "sync") else "passthrough"


def _is_purge(event):
    """Check if the request is a cache purge request."""
    params = event.get("queryStringParameters") or {}
    return params.get("purge", "").lower() in ("true", "1", "yes")


def _ttl_value():
    """Calculate the TTL Unix timestamp for a new DynamoDB record."""
    return int(time.time()) + GEO_TTL_SECONDS


def _get_original_url(event, path):
    """Reconstruct the original URL using x-original-host for multi-tenant routing."""
    headers = event.get("headers") or {}
    host = headers.get("x-original-host") or DEFAULT_ORIGIN_HOST
    if not host:
        host = headers.get("x-forwarded-host") or headers.get("host") or ""
    base = f"https://{host}{path}" if host else path

    qs = _filtered_qs(event)
    return f"{base}?{qs}" if qs else base


def _trigger_async(ddb_key, original_url, host="", mode="passthrough"):
    """Invoke the generator Lambda asynchronously to produce GEO content."""
    if not GENERATOR_FUNCTION_NAME:
        return
    try:
        payload = {"url_path": ddb_key, "original_url": original_url, "mode": mode}
        if host:
            payload["host"] = host
        lambda_client.invoke(
            FunctionName=GENERATOR_FUNCTION_NAME,
            InvocationType="Event",
            Payload=json.dumps(payload),
        )
        print(f"Async generation triggered for {ddb_key}")
    except Exception as e:
        print(f"Failed to trigger generator: {e}")


def _mark_processing(ddb_key, original_url, host="", mode="passthrough"):
    """Write a processing placeholder to DDB to prevent duplicate triggers."""
    try:
        item = {
            "url_path": ddb_key,
            "status": "processing",
            "original_url": original_url,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "ttl": _ttl_value(),
            "mode": mode,
        }
        if host:
            item["host"] = host
        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(url_path)",
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False  # already exists
        raise


def _fetch_original(url):
    """Fetch the original page content from the origin site.

    Validates the URL scheme and host before making the request
    to prevent server-side request forgery.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http"):
        print(f"Blocked fetch: invalid scheme '{parsed.scheme}' in {url}")
        return None, None
    if not parsed.hostname or parsed.hostname in ("localhost", "127.0.0.1", "169.254.169.254"):
        print(f"Blocked fetch: disallowed host '{parsed.hostname}' in {url}")
        return None, None
    if parsed.hostname.startswith(("10.", "172.", "192.168.")):
        print(f"Blocked fetch: private IP range in {url}")
        return None, None
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            ct = resp.headers.get("Content-Type", "text/html; charset=utf-8")
            return body, ct
    except Exception as e:
        print(f"Fetch original failed: {e}")
        return None, None


def _invoke_agentcore_sync(url):
    """Invoke Amazon Bedrock AgentCore synchronously and return the response text."""
    if not AGENT_RUNTIME_ARN:
        return None
    client = boto3.client("bedrock-agentcore", region_name=AGENTCORE_REGION)
    payload = json.dumps({"prompt": f"Generate GEO-optimized content and store to DynamoDB: {url}"}).encode()
    try:
        resp = client.invoke_agent_runtime(
            agentRuntimeArn=AGENT_RUNTIME_ARN,
            runtimeSessionId=str(uuid.uuid4()),
            payload=payload,
        )
        ct = resp.get("contentType", "")
        parts = []
        if "text/event-stream" in ct:
            for line in resp["response"].iter_lines(chunk_size=10):
                if line:
                    d = line.decode("utf-8")
                    if d.startswith("data: "):
                        parts.append(d[6:])
        else:
            for chunk in resp.get("response", []):
                parts.append(chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk))
        return "".join(parts) if parts else None
    except Exception as e:
        print(f"AgentCore sync failed: {e}")
        return None


def _scores_dashboard(host):
    """Return an HTML dashboard showing Amazon DynamoDB records for this host."""
    try:
        # Scan with filter for this host's records
        items = []
        scan_kwargs = {
            "FilterExpression": "begins_with(url_path, :prefix)",
            "ExpressionAttributeValues": {":prefix": f"{host}#"},
        }
        while True:
            resp = table.scan(**scan_kwargs)
            items.extend(resp.get("Items", []))
            if "LastEvaluatedKey" not in resp:
                break
            scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    except Exception as e:
        return _error(500, f"Scan failed: {e}")

    # Build rows
    rows = []
    for item in items:
        url_path = item.get("url_path", "")
        # Strip host prefix for display
        display_path = url_path.split("#", 1)[1] if "#" in url_path else url_path
        status = item.get("status", "")
        created = item.get("created_at", "")[:19]  # trim to seconds
        gen_ms = item.get("generation_duration_ms", "")
        orig = item.get("original_score", {})
        geo = item.get("geo_score", {})
        orig_score = orig.get("overall_score", "") if orig else ""
        geo_score = geo.get("overall_score", "") if geo else ""
        improvement = item.get("score_improvement", "")
        # Convert Decimal
        orig_score = float(orig_score) if orig_score != "" else ""
        geo_score = float(geo_score) if geo_score != "" else ""
        improvement = float(improvement) if improvement != "" else ""
        gen_ms = int(float(gen_ms)) if gen_ms != "" else ""
        rows.append({
            "path": display_path,
            "status": status,
            "original": orig_score,
            "geo": geo_score,
            "improvement": improvement,
            "gen_ms": gen_ms,
            "created": created,
        })

    rows_json = json.dumps(rows, default=str)
    html = _dashboard_html(host, rows_json, len(rows))

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-cache"},
        "body": html,
    }


def _dashboard_html(host, rows_json, count):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GEO Scores - {host}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f5f5f5; color: #333; padding: 20px; }}
  h1 {{ font-size: 1.4em; margin-bottom: 4px; }}
  .meta {{ color: #666; font-size: 0.85em; margin-bottom: 16px; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff;
           box-shadow: 0 1px 3px rgba(0,0,0,0.1); font-size: 0.85em; }}
  th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #eee; }}
  th {{ background: #fafafa; cursor: pointer; user-select: none; position: sticky; top: 0; }}
  th:hover {{ background: #f0f0f0; }}
  th .arrow {{ font-size: 0.7em; margin-left: 4px; }}
  tr:hover {{ background: #f9f9f9; }}
  .status-ready {{ color: #2e7d32; }}
  .status-processing {{ color: #e65100; }}
  .positive {{ color: #2e7d32; font-weight: 600; }}
  .negative {{ color: #c62828; font-weight: 600; }}
  .zero {{ color: #666; }}
  .path {{ max-width: 350px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
</style>
</head>
<body>
<h1>GEO Score Dashboard</h1>
<p class="meta">{host} &mdash; {count} records</p>
<table id="t">
<thead>
<tr>
  <th data-col="path">Path <span class="arrow"></span></th>
  <th data-col="status">Status <span class="arrow"></span></th>
  <th data-col="original" class="num">Original <span class="arrow"></span></th>
  <th data-col="geo" class="num">GEO <span class="arrow"></span></th>
  <th data-col="improvement" class="num">+/- <span class="arrow"></span></th>
  <th data-col="gen_ms" class="num">Gen (ms) <span class="arrow"></span></th>
  <th data-col="created">Created <span class="arrow"></span></th>
</tr>
</thead>
<tbody id="tb"></tbody>
</table>
<script>
const rows = {rows_json};
let sortCol = "improvement", sortAsc = false;

function render() {{
  const sorted = [...rows].sort((a, b) => {{
    let va = a[sortCol], vb = b[sortCol];
    if (va === "" || va === null) return 1;
    if (vb === "" || vb === null) return -1;
    if (typeof va === "number") return sortAsc ? va - vb : vb - va;
    return sortAsc ? String(va).localeCompare(String(vb)) : String(vb).localeCompare(String(va));
  }});
  const tb = document.getElementById("tb");
  tb.innerHTML = sorted.map(r => {{
    const impClass = r.improvement > 0 ? "positive" : r.improvement < 0 ? "negative" : "zero";
    const stClass = r.status === "ready" ? "status-ready" : "status-processing";
    return `<tr>
      <td class="path" title="${{r.path}}">${{r.path}}</td>
      <td class="${{stClass}}">${{r.status}}</td>
      <td class="num">${{r.original !== "" ? r.original : "-"}}</td>
      <td class="num">${{r.geo !== "" ? r.geo : "-"}}</td>
      <td class="num ${{impClass}}">${{r.improvement !== "" ? (r.improvement > 0 ? "+" : "") + r.improvement : "-"}}</td>
      <td class="num">${{r.gen_ms !== "" ? r.gen_ms.toLocaleString() : "-"}}</td>
      <td>${{r.created || "-"}}</td>
    </tr>`;
  }}).join("");
  document.querySelectorAll("th .arrow").forEach(el => el.textContent = "");
  const active = document.querySelector(`th[data-col="${{sortCol}}"] .arrow`);
  if (active) active.textContent = sortAsc ? " \\u25B2" : " \\u25BC";
}}

document.querySelectorAll("th[data-col]").forEach(th => {{
  th.addEventListener("click", () => {{
    const col = th.dataset.col;
    if (sortCol === col) sortAsc = !sortAsc;
    else {{ sortCol = col; sortAsc = col === "path" || col === "created"; }}
    render();
  }});
}});

render();
</script>
</body>
</html>"""


def handler(event, context):
    """Main Lambda handler for GEO content serving."""
    handler_start = time.time()

    headers = event.get("headers") or {}
    if headers.get("x-origin-verify") != ORIGIN_VERIFY_SECRET:
        return _error(403, "Forbidden")

    path = event.get("rawPath") or event.get("path") or "/"

    SKIP_EXTENSIONS = (
        '.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico',
        '.woff', '.woff2', '.ttf', '.eot', '.map', '.webp', '.avif',
    )
    path_lower = path.lower().split('?')[0]
    if path_lower.endswith(SKIP_EXTENSIONS):
        return _error(404, "Not a content page")

    mode = _get_mode(event)
    qs = _filtered_qs(event)
    original_url = _get_original_url(event, path)
    original_host = headers.get("x-original-host") or headers.get("x-forwarded-host") or headers.get("host") or ""
    ddb_key = _ddb_key(original_host, path, qs)

    params = event.get("queryStringParameters") or {}
    if params.get("action") == "scores":
        return _scores_dashboard(original_host)

    if _is_purge(event):
        try:
            table.delete_item(Key={"url_path": ddb_key})
            print(f"Purged {ddb_key}")
            cf_invalidated = _invalidate_cf_cache(path)
            result = {"status": "purged", "url_path": path, "ddb_key": ddb_key}
            if cf_invalidated:
                result["cf_invalidation"] = cf_invalidated
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json", "Cache-Control": "no-cache"},
                "body": json.dumps(result),
            }
        except Exception as e:
            return _error(500, f"Purge failed: {e}")

    try:
        resp = table.get_item(Key={"url_path": ddb_key})
    except ClientError as e:
        return _error(500, f"DynamoDB error: {e.response['Error']['Message']}")

    item = resp.get("Item")

    if item and item.get("status") == "ready":
        gc = (item.get("geo_content") or "").strip()
        if not (gc.startswith("<") or gc.lower().startswith("<!doctype")):
            print(f"Non-HTML content in cache for {ddb_key}, purging and regenerating")
            try:
                table.delete_item(Key={"url_path": ddb_key})
            except Exception:
                pass
            return _passthrough_or_202(mode, original_url, path, ddb_key, already_triggered=False, handler_start=handler_start, host=original_host)
        handler_ms = int((time.time() - handler_start) * 1000)
        ct = item.get("content_type", "text/html")
        if "charset" not in ct.lower():
            ct += "; charset=utf-8"
        headers = {
            "Content-Type": ct,
            "X-GEO-Optimized": "true",
            "X-GEO-Source": "cache",
            "X-GEO-Created": item.get("created_at", ""),
            "X-GEO-Handler-Ms": str(handler_ms),
            "Cache-Control": "public, max-age=3600",
        }
        dur = item.get("generation_duration_ms")
        if dur is not None:
            headers["X-GEO-Duration-Ms"] = str(dur)
        return {"statusCode": 200, "headers": headers, "body": item.get("geo_content", "")}

    if item and item.get("status") == "processing":
        if _is_processing_stale(item):
            print(f"Stale processing record for {ddb_key}, resetting")
            try:
                table.delete_item(Key={"url_path": ddb_key})
            except Exception:
                pass
            return _passthrough_or_202(mode, original_url, path, ddb_key, already_triggered=False, handler_start=handler_start, host=original_host)
        return _passthrough_or_202(mode, original_url, path, ddb_key, already_triggered=True, handler_start=handler_start, host=original_host)

    return _passthrough_or_202(mode, original_url, path, ddb_key, already_triggered=False, handler_start=handler_start, host=original_host)


def _passthrough_or_202(mode, original_url, path, ddb_key, already_triggered, handler_start, host=""):
    """Handle cache miss or processing state based on mode."""

    if mode == "sync":
        body, ct = _fetch_original(original_url)
        if body and not _is_text_content(ct):
            handler_ms = int((time.time() - handler_start) * 1000)
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": ct,
                    "X-GEO-Source": "passthrough-skip",
                    "X-GEO-Handler-Ms": str(handler_ms),
                    "Cache-Control": "no-cache",
                },
                "body": body,
            }
        if not already_triggered:
            _mark_processing(ddb_key, original_url, host, mode="sync")
        start = time.time()
        _invoke_agentcore_sync(original_url)
        agent_duration_ms = int((time.time() - start) * 1000)

        try:
            resp = table.get_item(Key={"url_path": ddb_key})
            item = resp.get("Item")
        except Exception:
            item = None

        handler_ms = int((time.time() - handler_start) * 1000)

        if item and item.get("status") == "ready":
            gc = (item.get("geo_content") or "").strip()
            if not (gc.startswith("<") or gc.lower().startswith("<!doctype")):
                print(f"Non-HTML content in DDB for {ddb_key}, falling through")
                try:
                    table.delete_item(Key={"url_path": ddb_key})
                except Exception:
                    pass
                return _do_passthrough(original_url, path, handler_start)
            try:
                table.update_item(
                    Key={"url_path": ddb_key},
                    UpdateExpression="SET generation_duration_ms = :d, handler_duration_ms = :h, #m = :mode",
                    ExpressionAttributeNames={"#m": "mode"},
                    ExpressionAttributeValues={
                        ":d": Decimal(str(agent_duration_ms)),
                        ":h": Decimal(str(handler_ms)),
                        ":mode": "sync",
                    },
                )
            except Exception:
                pass
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "text/html; charset=utf-8",
                    "X-GEO-Optimized": "true",
                    "X-GEO-Source": "generated",
                    "X-GEO-Duration-Ms": str(agent_duration_ms),
                    "X-GEO-Handler-Ms": str(handler_ms),
                    "Cache-Control": "public, max-age=3600",
                },
                "body": item.get("geo_content", ""),
            }
        return _do_passthrough(original_url, path, handler_start)

    if mode == "async":
        if not already_triggered:
            _mark_processing(ddb_key, original_url, host, mode="async")
            _trigger_async(ddb_key, original_url, host, mode="async")
        handler_ms = int((time.time() - handler_start) * 1000)
        return {
            "statusCode": 202,
            "headers": {
                "Content-Type": "application/json",
                "Cache-Control": "no-cache",
                "X-GEO-Handler-Ms": str(handler_ms),
            },
            "body": json.dumps({
                "status": "generating",
                "message": f"GEO content for {path} is being generated. Please retry shortly.",
            }),
        }

    # Default: passthrough
    body, ct = _fetch_original(original_url)
    if body and not _is_text_content(ct):
        handler_ms = int((time.time() - handler_start) * 1000)
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": ct,
                "X-GEO-Source": "passthrough-skip",
                "X-GEO-Handler-Ms": str(handler_ms),
                "Cache-Control": "no-cache",
            },
            "body": body,
        }
    if not already_triggered:
        _mark_processing(ddb_key, original_url, host, mode="passthrough")
        _trigger_async(ddb_key, original_url, host, mode="passthrough")
    return _do_passthrough_with_body(body, ct, path, handler_start)


def _do_passthrough(original_url, path, handler_start):
    """Fetch original content and return it as a passthrough response."""
    body, ct = _fetch_original(original_url)
    return _do_passthrough_with_body(body, ct, path, handler_start)


def _do_passthrough_with_body(body, ct, path, handler_start):
    """Return a passthrough response with pre-fetched body content."""
    handler_ms = int((time.time() - handler_start) * 1000)
    if body:
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": ct or "text/html; charset=utf-8",
                "X-GEO-Source": "passthrough",
                "X-GEO-Handler-Ms": str(handler_ms),
                "Cache-Control": "no-cache",
            },
            "body": body,
        }
    return _error(502, f"Failed to fetch original content for {path}")


def _is_text_content(content_type):
    """Check if content-type is text-based (HTML, plain text, XML, JSON, etc.)."""
    if not content_type:
        return True  # assume text if unknown
    ct_lower = content_type.lower().split(";")[0].strip()
    return ct_lower.startswith("text/") or ct_lower in (
        "application/json",
        "application/xml",
        "application/xhtml+xml",
    )


def _is_processing_stale(item):
    """Check if a processing record has exceeded the timeout."""
    created_at = item.get("created_at", "")
    if not created_at:
        return True  # no timestamp = treat as stale
    try:
        created = datetime.fromisoformat(created_at)
        age_seconds = (datetime.now(timezone.utc) - created).total_seconds()
        return age_seconds > PROCESSING_TIMEOUT_SECONDS
    except (ValueError, TypeError):
        return True


def _invalidate_cf_cache(path):
    """Create an Amazon CloudFront cache invalidation for the given path."""
    if not CF_DISTRIBUTION_ID:
        return None
    try:
        cf_client = boto3.client("cloudfront")
        caller_ref = f"purge-{path}-{int(time.time())}"
        # Use wildcard to clear all querystring variants of this path
        invalidation_path = f"{path}*" if not path.endswith("*") else path
        resp = cf_client.create_invalidation(
            DistributionId=CF_DISTRIBUTION_ID,
            InvalidationBatch={
                "Paths": {"Quantity": 1, "Items": [invalidation_path]},
                "CallerReference": caller_ref,
            },
        )
        inv_id = resp["Invalidation"]["Id"]
        print(f"CF invalidation created: {inv_id} for {path}")
        return inv_id
    except Exception as e:
        print(f"CF invalidation failed (non-fatal): {e}")
        return None


def _error(code, msg):
    """Return a JSON error response."""
    return {
        "statusCode": code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": msg}),
    }
