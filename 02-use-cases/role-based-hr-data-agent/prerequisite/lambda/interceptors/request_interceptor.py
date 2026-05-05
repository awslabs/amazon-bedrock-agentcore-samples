"""
Amazon Bedrock AgentCore Gateway Request Interceptor.

Processes AgentCore interceptor payloads to:
- Decode JWT and resolve tenant context (client_id → tenantId/role/department)
- Inject tenantId into tool arguments (override mismatched values)
- Normalize scope strings for Cedar evaluation
- Generate correlation IDs for end-to-end request tracing
- Pass through tools/list unchanged (filtering handled by response interceptor)

Payload format (interceptorInputVersion: "1.0"):
{
  "mcp": {
    "rawGatewayRequest": {...},
    "gatewayRequest": {
      "path": "/mcp",
      "httpMethod": "POST",
      "headers": {"Authorization": "Bearer <token>", ...},
      "body": {"jsonrpc": "2.0", "method": "tools/call", "params": {...}}
    }
  }
}
"""

import base64
import json
import logging
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tenant_mapping import resolve_client_context

logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class JWTClaims:
    sub: str
    username: str
    tenant_id: str
    role: Optional[str]
    department: Optional[str]
    scopes: List[str]

    @classmethod
    def from_jwt_payload(cls, payload: Dict[str, Any]) -> "JWTClaims":
        client_id = payload.get("sub", "")
        scopes = payload.get("scope", "").split() if payload.get("scope") else []
        tenant_id = payload.get("custom:tenantId", "")
        role = payload.get("custom:role")
        department = payload.get("custom:department")
        username = payload.get("username", payload.get("cognito:username", ""))
        if not tenant_id:
            ctx = resolve_client_context(client_id)
            tenant_id = ctx["tenantId"]
            role = ctx["role"]
            department = ctx["department"]
            username = ctx["username"]
        return cls(sub=client_id, username=username, tenant_id=tenant_id,
                   role=role, department=department, scopes=scopes)


class HRRequestInterceptor:
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self._correlation_id: Optional[str] = None

    def lambda_handler(self, event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        try:
            if not self._valid_payload(event):
                return self._error("Invalid AgentCore interceptor payload")
            mcp = event["mcp"]
            req = mcp["gatewayRequest"]
            claims = self._decode_jwt(req.get("headers", {}))
            return self._process(mcp, req, claims)
        except Exception as e:
            self.logger.error(f"Request interceptor error: {e}")
            return self._error(f"Request processing failed: {e}")

    def _valid_payload(self, event: Dict[str, Any]) -> bool:
        if event.get("interceptorInputVersion") != "1.0":
            return False
        mcp = event.get("mcp", {})
        return bool(mcp.get("gatewayRequest", {}).get("body"))

    def _decode_jwt(self, headers: Dict[str, str]) -> JWTClaims:
        headers_ci = {k.lower(): v for k, v in headers.items()}
        auth = headers_ci.get("authorization", "")
        if not auth.startswith("Bearer "):
            raise ValueError("Missing Authorization header")
        token = auth[7:]
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT format")
        pad = parts[1] + "=" * (4 - len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(pad).decode())
        return JWTClaims.from_jwt_payload(payload)

    def _process(self, mcp: Dict, req: Dict, claims: JWTClaims) -> Dict[str, Any]:
        body = req.get("body", {})
        method = body.get("method", "")
        params = body.get("params", {})
        cid = str(uuid.uuid4())
        self._correlation_id = cid

        if method == "tools/call":
            tool_name = params.get("name", "")
            args = params.get("arguments", {})
            self._inject_tenant(args, claims, tool_name, cid)
            scope_string = " ".join(claims.scopes)
            return {
                "interceptorOutputVersion": "1.0",
                "mcp": {
                    "transformedGatewayRequest": {
                        "headers": {"X-Correlation-ID": cid},
                        "body": {
                            "jsonrpc": "2.0",
                            "id": body.get("id"),
                            "method": method,
                            "params": {
                                "name": tool_name,
                                "arguments": {
                                    **args,
                                    "normalized_scope": f" {scope_string} ",
                                    "correlation_id": cid,
                                },
                            },
                        },
                    }
                },
            }

        # tools/list and all other methods — pass through unchanged
        self.logger.info(json.dumps({
            "event": "tool_discovery_request", "correlation_id": cid,
            "tenant_id": claims.tenant_id, "scopes": claims.scopes,
            "timestamp": datetime.utcnow().isoformat(),
        }))
        return {
            "interceptorOutputVersion": "1.0",
            "mcp": {"transformedGatewayRequest": {"body": body}},
        }

    def _inject_tenant(self, args: Dict, claims: JWTClaims, tool_name: str, cid: str) -> None:
        if "tenantId" not in args:
            args["tenantId"] = claims.tenant_id
            self.logger.info(json.dumps({
                "event": "tenant_injection", "correlation_id": cid,
                "tenant_id": claims.tenant_id, "tool_name": tool_name,
                "timestamp": datetime.utcnow().isoformat(),
            }))
        elif args["tenantId"] != claims.tenant_id:
            self.logger.warning(json.dumps({
                "event": "tenant_override",
                "security_alert": "POTENTIAL_CROSS_TENANT_ACCESS",
                "correlation_id": cid,
                "attempted_tenant": args["tenantId"],
                "correct_tenant": claims.tenant_id,
                "tool_name": tool_name,
                "timestamp": datetime.utcnow().isoformat(),
            }))
            args["tenantId"] = claims.tenant_id

    def _error(self, message: str) -> Dict[str, Any]:
        return {
            "interceptorOutputVersion": "1.0",
            "mcp": {
                "transformedGatewayResponse": {
                    "statusCode": 400,
                    "body": {"jsonrpc": "2.0", "id": 1,
                             "error": {"code": -32600, "message": "Invalid Request", "data": message}},
                }
            },
        }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    interceptor = HRRequestInterceptor()
    return interceptor.lambda_handler(event, context)
