"""
AgentCore Gateway Interceptor for Customer Service Agent
=========================================================
Handles both REQUEST and RESPONSE interception in a single Lambda function.

REQUEST path capabilities:
  1. Token validation       - verify inbound JWT is present and well-formed
  2. Header injection       - add downstream auth headers (API keys, bearer tokens)
  3. Request validation     - block malformed or disallowed tool calls
  4. Logging / auditing     - structured CloudWatch log per tool call
  5. Rate limiting          - per-user call quota enforced via DynamoDB
  6. Input transformation   - normalise parameter names before hitting targets

RESPONSE path capabilities:
  7. PII masking            - redact emails, phone numbers, SSNs from tool responses
  8. Response logging       - record what each tool returned
  9. Error normalisation    - standardise error shapes returned to the agent
"""

import json
import logging
import os
import re
import time
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Configuration (override via Lambda environment variables)
# ---------------------------------------------------------------------------
RATE_LIMIT_TABLE   = os.environ.get("RATE_LIMIT_TABLE", "agentcore-gateway-rate-limits")
RATE_LIMIT_MAX     = int(os.environ.get("RATE_LIMIT_MAX", "100"))   # calls per window
RATE_LIMIT_WINDOW  = int(os.environ.get("RATE_LIMIT_WINDOW", "3600"))  # seconds (1 hour)
DOWNSTREAM_API_KEY = os.environ.get("DOWNSTREAM_API_KEY", "")       # injected header value
ENABLE_RATE_LIMIT  = os.environ.get("ENABLE_RATE_LIMIT", "true").lower() == "true"

# Tools that are allowed through the gateway — block anything not in this list
ALLOWED_TOOLS = {
    "tavily_search",
    "retrieve_context",
    "create_ticket",
    "update_ticket",
    "get_ticket",
    "list_tickets",
}

# PII patterns to redact from responses
PII_PATTERNS = [
    # Email addresses
    (re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"), "[EMAIL]"),
    # US phone numbers (various formats)
    (re.compile(r"\b(\+?1[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}\b"), "[PHONE]"),
    # US Social Security Numbers
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    # Credit card numbers (basic pattern)
    (re.compile(r"\b(?:\d[ \-]?){13,16}\b"), "[CARD]"),
    # US ZIP codes (standalone — 5 digit)
    (re.compile(r"\b\d{5}(?:-\d{4})?\b"), "[ZIP]"),
]

# ---------------------------------------------------------------------------
# DynamoDB client (lazy init)
# ---------------------------------------------------------------------------
_dynamodb = None

def get_dynamodb():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb")
    return _dynamodb


# ===========================================================================
# ENTRY POINT
# ===========================================================================

def lambda_handler(event, context):
    mcp            = event.get("mcp", {}) or {}
    gateway_request  = mcp.get("gatewayRequest") or {}
    gateway_response = mcp.get("gatewayResponse")

    if gateway_response is not None:
        return _handle_response(gateway_request, gateway_response)
    return _handle_request(gateway_request)


# ===========================================================================
# REQUEST INTERCEPTION
# ===========================================================================

def _handle_request(gateway_request: dict) -> dict:
    body    = gateway_request.get("body") or {}
    headers = dict(gateway_request.get("headers") or {})

    method  = body.get("method") if isinstance(body, dict) else None
    msg_id  = body.get("id")     if isinstance(body, dict) else None
    params  = body.get("params", {}) if isinstance(body, dict) else {}
    tool_name = (params.get("name") or "") if isinstance(params, dict) else ""

    # ------------------------------------------------------------------
    # 1. TOKEN VALIDATION
    # ------------------------------------------------------------------
    auth_header = headers.get("authorization") or headers.get("Authorization", "")
    validation_error = _validate_token(auth_header)
    if validation_error:
        logger.warning(f"TOKEN VALIDATION FAILED: {validation_error} | method={method} id={msg_id}")
        return _error_response(msg_id, code=-32001, message=f"Unauthorized: {validation_error}")

    # Extract caller identity from token for downstream use
    caller_id = _extract_caller_id(auth_header)

    # ------------------------------------------------------------------
    # 2. LOGGING / AUDITING (before processing so we always capture intent)
    # ------------------------------------------------------------------
    logger.info(json.dumps({
        "event":     "tool_call_request",
        "caller_id": caller_id,
        "method":    method,
        "tool":      tool_name,
        "msg_id":    msg_id,
        "timestamp": int(time.time()),
    }))

    # ------------------------------------------------------------------
    # 3. REQUEST VALIDATION — only allow known tools
    # ------------------------------------------------------------------
    if method == "tools/call" and tool_name:
        if tool_name not in ALLOWED_TOOLS:
            logger.warning(f"BLOCKED TOOL: {tool_name} | caller={caller_id}")
            return _error_response(
                msg_id,
                code=-32002,
                message=f"Tool '{tool_name}' is not permitted on this gateway",
            )

    # ------------------------------------------------------------------
    # 4. RATE LIMITING — per caller, per hour
    # ------------------------------------------------------------------
    if ENABLE_RATE_LIMIT and caller_id and method == "tools/call":
        rate_error = _check_rate_limit(caller_id)
        if rate_error:
            logger.warning(f"RATE LIMIT EXCEEDED: caller={caller_id}")
            return _error_response(msg_id, code=-32003, message=rate_error)

    # ------------------------------------------------------------------
    # 5. INPUT TRANSFORMATION — normalise parameter names
    # ------------------------------------------------------------------
    body = _transform_request_body(body, tool_name)

    # ------------------------------------------------------------------
    # 6. HEADER INJECTION — add downstream auth headers
    # ------------------------------------------------------------------
    headers = _inject_headers(headers, caller_id)

    return {
        "interceptorOutputVersion": "1.0",
        "mcp": {
            "transformedGatewayRequest": {
                "body":    body,
                "headers": headers,
            }
        },
    }


# ===========================================================================
# RESPONSE INTERCEPTION
# ===========================================================================

def _handle_response(gateway_request: dict, gateway_response: dict) -> dict:
    body         = gateway_response.get("body") or {}
    is_streaming = bool(gateway_response.get("isStreamingResponse"))
    has_status   = "statusCode" in gateway_response
    has_headers  = "headers" in gateway_response

    inbound_method = (gateway_request.get("body") or {}).get("method")
    msg_id         = body.get("id") if isinstance(body, dict) else None

    # ------------------------------------------------------------------
    # 7. PII MASKING — scrub sensitive data before it reaches the agent
    # ------------------------------------------------------------------
    body = _mask_pii(body)

    # ------------------------------------------------------------------
    # 8. RESPONSE LOGGING
    # ------------------------------------------------------------------
    logger.info(json.dumps({
        "event":      "tool_call_response",
        "method":     inbound_method,
        "msg_id":     msg_id,
        "streaming":  is_streaming,
        "has_error":  "error" in body if isinstance(body, dict) else False,
        "timestamp":  int(time.time()),
    }))

    # ------------------------------------------------------------------
    # 9. ERROR NORMALISATION — standardise error shapes
    # ------------------------------------------------------------------
    body = _normalise_error(body)

    # Build output — streaming subsequent events can only return body
    out = {"body": body}
    if not is_streaming or has_status:
        if has_status:
            out["statusCode"] = gateway_response.get("statusCode", 200)
        if has_headers:
            out["headers"] = gateway_response.get("headers", {})

    return {
        "interceptorOutputVersion": "1.0",
        "mcp": {"transformedGatewayResponse": out},
    }


# ===========================================================================
# HELPER FUNCTIONS
# ===========================================================================

def _validate_token(auth_header: str):
    """
    Basic JWT presence and format check.
    Returns an error string if invalid, None if valid.
    For production, replace with full JWT signature verification
    using your Cognito JWKS endpoint.
    """
    if not auth_header:
        return "Missing Authorization header"
    if not auth_header.lower().startswith("bearer "):
        return "Authorization header must use Bearer scheme"
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        return "Empty bearer token"
    # Basic JWT structure check: three base64 segments separated by dots
    parts = token.split(".")
    if len(parts) != 3:
        return "Malformed JWT token"
    return None  # valid


def _extract_caller_id(auth_header: str) -> str:
    """
    Extract a caller identifier from the JWT payload (sub claim).
    Falls back to 'anonymous' if extraction fails.
    For production, use a proper JWT library (python-jose, PyJWT).
    """
    try:
        token = auth_header.split(" ", 1)[1].strip()
        payload_b64 = token.split(".")[1]
        # Add padding if needed
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        import base64
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get("sub") or payload.get("client_id") or "anonymous"
    except Exception:
        return "anonymous"


def _check_rate_limit(caller_id: str):
    """
    Enforce per-caller rate limit using DynamoDB.
    Uses a sliding window counter keyed by caller_id + current hour bucket.
    Returns an error string if limit exceeded, None if allowed.
    """
    try:
        table      = get_dynamodb().Table(RATE_LIMIT_TABLE)
        bucket_key = f"{caller_id}#{int(time.time()) // RATE_LIMIT_WINDOW}"
        ttl_value  = int(time.time()) + RATE_LIMIT_WINDOW * 2

        response = table.update_item(
            Key={"pk": bucket_key},
            UpdateExpression="ADD call_count :inc SET ttl = :ttl",
            ExpressionAttributeValues={":inc": 1, ":ttl": ttl_value},
            ReturnValues="UPDATED_NEW",
        )
        count = int(response["Attributes"]["call_count"])
        if count > RATE_LIMIT_MAX:
            return f"Rate limit exceeded: {count}/{RATE_LIMIT_MAX} calls in current window"
        return None
    except ClientError as e:
        # If DynamoDB is unavailable, log and allow through (fail open)
        logger.error(f"Rate limit DynamoDB error: {e} — allowing request through")
        return None
    except Exception as e:
        logger.error(f"Rate limit check failed: {e} — allowing request through")
        return None


def _transform_request_body(body: dict, tool_name: str) -> dict:
    """
    Normalise parameter names for known tools so the agent doesn't need
    to know each target's exact parameter schema.
    """
    if not isinstance(body, dict):
        return body

    params = body.get("params", {})
    if not isinstance(params, dict):
        return body

    arguments = params.get("arguments", {})
    if not isinstance(arguments, dict):
        return body

    # Tavily search: agent may send 'query', 'search_query', or 'value'
    if tool_name == "tavily_search":
        query = (
            arguments.get("query")
            or arguments.get("search_query")
            or arguments.get("value")
        )
        if query:
            arguments["query"] = query
            # Remove aliases to keep payload clean
            arguments.pop("search_query", None)
            arguments.pop("value", None)

    # Zendesk ticket creation: normalise 'subject' vs 'title'
    if tool_name == "create_ticket":
        if "title" in arguments and "subject" not in arguments:
            arguments["subject"] = arguments.pop("title")

    body["params"]["arguments"] = arguments
    return body


def _inject_headers(headers: dict, caller_id: str) -> dict:
    """
    Inject downstream authentication and tracing headers.
    """
    # Downstream API key (e.g. for an internal API gateway)
    if DOWNSTREAM_API_KEY:
        headers["x-api-key"] = DOWNSTREAM_API_KEY

    # Propagate caller identity for downstream audit trails
    if caller_id and caller_id != "anonymous":
        headers["x-caller-id"] = caller_id

    # Correlation ID for distributed tracing
    headers["x-request-time"] = str(int(time.time()))

    return headers


def _mask_pii(body) -> dict:
    """
    Recursively walk the response body and redact PII patterns.
    Operates on string values only — leaves structure intact.
    """
    if isinstance(body, str):
        for pattern, replacement in PII_PATTERNS:
            body = pattern.sub(replacement, body)
        return body
    if isinstance(body, dict):
        return {k: _mask_pii(v) for k, v in body.items()}
    if isinstance(body, list):
        return [_mask_pii(item) for item in body]
    return body


def _normalise_error(body: dict) -> dict:
    """
    If the tool returned a non-standard error shape, normalise it to
    JSON-RPC error format so the agent always sees a consistent structure.
    """
    if not isinstance(body, dict):
        return body

    # Already a proper JSON-RPC error
    if "error" in body and isinstance(body["error"], dict):
        err = body["error"]
        if "code" not in err:
            err["code"] = -32000
        if "message" not in err:
            err["message"] = "Unknown error"
        return body

    # Tool returned {"error": "some string"} — wrap it
    if "error" in body and isinstance(body["error"], str):
        body["error"] = {
            "code":    -32000,
            "message": body["error"],
        }

    return body


def _error_response(msg_id, code: int, message: str) -> dict:
    """
    Return a JSON-RPC error response that blocks the request from
    reaching the target. The gateway will return this directly to the agent.
    """
    return {
        "interceptorOutputVersion": "1.0",
        "mcp": {
            "transformedGatewayRequest": {
                "body": {
                    "jsonrpc": "2.0",
                    "id":      msg_id,
                    "error": {
                        "code":    code,
                        "message": message,
                    },
                }
            }
        },
    }
