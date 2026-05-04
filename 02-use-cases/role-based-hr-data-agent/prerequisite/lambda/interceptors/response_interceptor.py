"""
Amazon Bedrock AgentCore Gateway Response Interceptor — DLP enforcement.

Processes AgentCore response interceptor payloads to:
- Filter tool discovery (tools/list) based on caller OAuth scopes
- Apply field-level DLP redaction (tools/call responses) based on scopes:
    • Without hr-dlp-gateway/pii   → redact email, phone, emergency_contact
    • Without hr-dlp-gateway/address → redact address, city, state, zip_code
    • Without hr-dlp-gateway/comp  → redact salary, bonus, stock_options, pay_grade
- Pass through all other MCP methods unchanged

Redacted fields receive the value: "[REDACTED - Insufficient Permissions]"
"""

import base64
import copy
import json
import logging
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tenant_mapping import resolve_client_context

logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger(__name__)

REDACTED = "[REDACTED - Insufficient Permissions]"


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
            tenant_id, role, department, username = (
                ctx["tenantId"], ctx["role"], ctx["department"], ctx["username"]
            )
        return cls(sub=client_id, username=username, tenant_id=tenant_id,
                   role=role, department=department, scopes=scopes)


def _normalize_scopes(scopes: List[str]) -> List[str]:
    """Expand scope list to include both hr:x and x and hr-dlp-gateway/x forms."""
    out = list(scopes)
    for s in scopes:
        if "/" in s:
            short = s.split("/")[-1]
            out.append(short)
            out.append(f"hr:{short}")
        if s.startswith("hr:"):
            out.append(s[3:])
    return out


class HRResponseInterceptor:
    def __init__(self, log: Optional[logging.Logger] = None):
        self.logger = log or logging.getLogger(__name__)

    def lambda_handler(self, event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        try:
            if not self._valid_payload(event):
                return self._error("Invalid AgentCore interceptor payload")
            mcp = event["mcp"]
            req_headers = mcp["gatewayRequest"].get("headers", {})
            req_body = mcp["gatewayRequest"].get("body", {})
            resp_body = mcp["gatewayResponse"].get("body", {})
            claims = self._decode_jwt(req_headers)
            method = req_body.get("method", "")
            cid = str(uuid.uuid4())

            if method == "tools/list":
                processed = self._filter_tools(resp_body, claims, cid)
            elif method == "tools/call":
                processed = self._redact(resp_body, claims, cid)
            else:
                processed = resp_body

            return {
                "interceptorOutputVersion": "1.0",
                "mcp": {"transformedGatewayResponse": {"statusCode": 200, "body": processed}},
            }
        except Exception as e:
            self.logger.error(f"Response interceptor error: {e}", exc_info=True)
            return self._error(f"Response processing failed: {e}")

    def _valid_payload(self, event: Dict[str, Any]) -> bool:
        if event.get("interceptorInputVersion") != "1.0":
            return False
        mcp = event.get("mcp", {})
        return bool(
            mcp.get("gatewayRequest", {}).get("body")
            and mcp.get("gatewayResponse", {}).get("body") is not None
        )

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

    # ------------------------------------------------------------------
    # Tool discovery filtering
    # ------------------------------------------------------------------

    def _filter_tools(self, resp_body: Dict, claims: JWTClaims, cid: str) -> Dict:
        result = resp_body.get("result", {})
        if not isinstance(result, dict) or "tools" not in result:
            return resp_body

        ns = _normalize_scopes(claims.scopes)
        filtered, hidden = [], 0

        for tool in result.get("tools", []):
            name = tool.get("name", "")
            if "search_employee" in name:
                if any(s in ns for s in ["hr:read", "read", "hr-dlp-gateway/read"]):
                    filtered.append(tool)
                else:
                    hidden += 1
            elif "get_employee_profile" in name:
                if any(s in ns for s in ["hr:pii", "pii", "hr-dlp-gateway/pii"]):
                    filtered.append(tool)
                else:
                    hidden += 1
            elif "get_employee_compensation" in name:
                if any(s in ns for s in ["hr:comp", "comp", "hr-dlp-gateway/comp"]):
                    filtered.append(tool)
                else:
                    hidden += 1

        if hidden:
            self.logger.info(json.dumps({
                "event": "tool_discovery_filtering", "correlation_id": cid,
                "tenant_id": claims.tenant_id, "hidden_tools": hidden,
                "scopes": claims.scopes, "timestamp": datetime.utcnow().isoformat(),
            }))

        return {**resp_body, "result": {**result, "tools": filtered}}

    # ------------------------------------------------------------------
    # Field-level DLP redaction
    # ------------------------------------------------------------------

    def _redact(self, resp_body: Dict, claims: JWTClaims, cid: str) -> Dict:
        result = resp_body.get("result", {})
        if not isinstance(result, dict):
            return resp_body

        content = result.get("content", [])
        if not content or not isinstance(content, list):
            return resp_body

        text = content[0].get("text", "") if content else ""
        if not text:
            return resp_body

        try:
            lambda_resp = json.loads(text)
            body_data = json.loads(lambda_resp.get("body", "{}"))
            redacted_body, log = self._redact_data(body_data, claims.scopes)
            lambda_resp["body"] = json.dumps(redacted_body)
            content[0]["text"] = json.dumps(lambda_resp)

            if log:
                self.logger.info(json.dumps({
                    "event": "dlp_redaction", "correlation_id": cid,
                    "tenant_id": claims.tenant_id, "redacted_fields": log,
                    "timestamp": datetime.utcnow().isoformat(),
                }))

            return {**resp_body, "result": result}
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            self.logger.warning(f"DLP parse failed: {e}")
            return resp_body

    def _redact_data(self, data: Dict, scopes: List[str]) -> Tuple[Dict, List[str]]:
        ns = _normalize_scopes(scopes)
        redacted = copy.deepcopy(data)
        log: List[str] = []

        if "employees" in redacted and isinstance(redacted["employees"], list):
            for i, emp in enumerate(redacted["employees"]):
                if isinstance(emp, dict):
                    redacted["employees"][i], emp_log = self._redact_employee(emp, ns)
                    log.extend(emp_log)
        elif any(k in redacted for k in ["employee_id", "name", "email", "salary"]):
            redacted, log = self._redact_employee(redacted, ns)

        return redacted, log

    def _redact_employee(self, emp: Dict, ns: List[str]) -> Tuple[Dict, List[str]]:
        out = emp.copy()
        log: List[str] = []

        if not any(s in ns for s in ["hr:pii", "pii", "hr-dlp-gateway/pii"]):
            for f in ["email", "phone", "personal_phone", "emergency_contact"]:
                if f in out:
                    out[f] = REDACTED
                    log.append(f"Redacted {f} (missing hr-dlp-gateway/pii)")

        if not any(s in ns for s in ["hr:address", "address", "hr-dlp-gateway/address"]):
            for f in ["address", "home_address", "street", "city", "state", "zip_code"]:
                if f in out:
                    out[f] = REDACTED
                    log.append(f"Redacted {f} (missing hr-dlp-gateway/address)")

        if not any(s in ns for s in ["hr:comp", "comp", "hr-dlp-gateway/comp"]):
            for f in ["salary", "bonus", "stock_options", "pay_grade", "benefits_value", "total_compensation"]:
                if f in out:
                    out[f] = REDACTED
                    log.append(f"Redacted {f} (missing hr-dlp-gateway/comp)")
            if "compensation_history" in out and isinstance(out["compensation_history"], list):
                out["compensation_history"] = [
                    {**e, "salary": REDACTED, "bonus": REDACTED}
                    if isinstance(e, dict) else e
                    for e in out["compensation_history"]
                ]
                log.append("Redacted compensation_history (missing hr-dlp-gateway/comp)")

        return out, log

    def _error(self, message: str) -> Dict[str, Any]:
        return {
            "interceptorOutputVersion": "1.0",
            "mcp": {
                "transformedGatewayResponse": {
                    "statusCode": 500,
                    "body": {"jsonrpc": "2.0", "id": 1,
                             "error": {"code": -32603, "message": "Internal Error", "data": message}},
                }
            },
        }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    interceptor = HRResponseInterceptor()
    return interceptor.lambda_handler(event, context)
