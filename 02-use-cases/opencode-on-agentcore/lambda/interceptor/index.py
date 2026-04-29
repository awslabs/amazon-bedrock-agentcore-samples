# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Gateway REQUEST interceptor — extracts user_id from JWT and injects into tool arguments."""

import base64
import json


def handler(event, context):
    mcp = event.get("mcp", {})
    gw_req = mcp.get("gatewayRequest", {})
    headers = gw_req.get("headers", {})
    body = gw_req.get("body", {})

    # Extract sub from JWT (no verification needed — Gateway already validated it)
    auth = headers.get("Authorization", "") or headers.get("authorization", "")
    if not auth or not auth.startswith("Bearer "):
        # Internal Gateway calls (e.g., policy validation, tool discovery) may
        # not carry a Cognito JWT.  Pass them through without user injection.
        forwarded_headers = {k: v for k, v in headers.items() if k.lower() != "authorization"}
        return {
            "interceptorOutputVersion": "1.0",
            "mcp": {
                "transformedGatewayRequest": {
                    "headers": forwarded_headers,
                    "body": body,
                }
            },
        }

    try:
        payload = auth.split(".")[1]
        payload += "=" * (4 - len(payload) % 4)  # pad base64
        claims = json.loads(base64.b64decode(payload))
    except Exception:
        # Return a proper interceptor response that short-circuits with an error.
        return {
            "interceptorOutputVersion": "1.0",
            "mcp": {
                "transformedGatewayResponse": {
                    "statusCode": 401,
                    "body": {"jsonrpc": "2.0", "error": {"code": -32600, "message": "JWT decode failed"}},
                }
            },
        }

    user_id = claims.get("sub") or claims.get("email")
    if not user_id:
        return {
            "interceptorOutputVersion": "1.0",
            "mcp": {
                "transformedGatewayResponse": {
                    "statusCode": 401,
                    "body": {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Missing sub/email in JWT"}},
                }
            },
        }

    # Inject user_id into tool call arguments
    if body.get("method") == "tools/call" and "params" in body:
        args = body["params"].setdefault("arguments", {})
        args["_user_id"] = user_id

    # Strip the inbound Authorization header so it does not override the
    # Gateway's outbound SigV4 Authorization header.  When GATEWAY_IAM_ROLE
    # is the credential provider, the Gateway signs outbound requests with
    # SigV4.  Any headers returned in transformedGatewayRequest.headers are
    # forwarded verbatim to the target (see interceptor header propagation:
    # https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-headers.html#gateway-headers-interceptor-propagation).
    # If we return the inbound "Authorization: Bearer <cognito-jwt>" here,
    # it replaces the Gateway's SigV4 Authorization header, causing a
    # signature mismatch at the Runtime — this was the root cause of the
    # original SigV4 "bug".
    forwarded_headers = {k: v for k, v in headers.items() if k.lower() != "authorization"}

    return {
        "interceptorOutputVersion": "1.0",
        "mcp": {
            "transformedGatewayRequest": {
                "headers": forwarded_headers,
                "body": body,
            }
        },
    }
