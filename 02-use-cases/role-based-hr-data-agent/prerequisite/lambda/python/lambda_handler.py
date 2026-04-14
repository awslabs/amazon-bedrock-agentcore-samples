"""
HR Data Provider Lambda — main entry point.

Routes Amazon Bedrock AgentCore Gateway tool calls to the appropriate HR handler.
All data is returned unredacted; the Gateway Response Interceptor
applies field-level DLP based on the caller's OAuth scopes.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from audit_logger import log_error, log_lambda_execution
from hr_handlers import (
    handle_get_employee_compensation,
    handle_get_employee_profile,
    handle_search_employee,
    inject_correlation_id,
    validate_tool_arguments,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    correlation_id = _extract_correlation_id(event, context)

    try:
        logger.info(f"Event: {json.dumps(event)}")

        tool_name = _extract_tool_name(event, context)
        arguments = _extract_arguments(event, tool_name)
        tenant_id = arguments.get("tenantId", "")

        log_lambda_execution(
            correlation_id=correlation_id,
            tool_name=tool_name,
            tenant_id=tenant_id,
            function_name=getattr(context, "function_name", "hr-data-provider"),
            arguments=arguments,
        )

        if not tool_name:
            return _error(correlation_id, "Missing tool_name")

        # Strip target prefix: "hr-lambda-target___search_employee" → "search_employee"
        base_name = tool_name.split("___")[-1] if "___" in tool_name else tool_name.split("__")[-1] if "__" in tool_name else tool_name

        arguments_with_cid = inject_correlation_id(arguments, correlation_id)

        validation = validate_tool_arguments(tool_name, arguments_with_cid)
        if not validation["valid"]:
            return _error(correlation_id, validation["error"], validation.get("error_code", "VALIDATION_ERROR"))

        if base_name == "search_employee":
            result = handle_search_employee(arguments_with_cid)
        elif base_name == "get_employee_profile":
            result = handle_get_employee_profile(arguments_with_cid)
        elif base_name == "get_employee_compensation":
            result = handle_get_employee_compensation(arguments_with_cid)
        else:
            return _error(correlation_id, f"Unknown tool: {tool_name}")

        if "error" in result:
            status = 403 if result.get("error_code") == "EMPLOYEE_NOT_FOUND" else 400
            return _error(correlation_id, result["error"], result.get("error_code", "HANDLER_ERROR"), status)

        result["_metadata"] = {
            "data_type": "DUMMY_DEMONSTRATION_DATA",
            "correlation_id": correlation_id,
            "tenant_id": tenant_id,
            "tool_name": tool_name,
            "timestamp": datetime.utcnow().isoformat(),
        }

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json", "X-Correlation-ID": correlation_id},
            "body": json.dumps(result),
        }

    except Exception as e:
        log_error(correlation_id, str(e), type(e).__name__, additional_context={"event_keys": list(event.keys())})
        return _error(correlation_id, f"Lambda execution error: {str(e)}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_tool_name(event: Dict[str, Any], context: Any) -> str:
    # 1. AgentCore: context.client_context.custom
    if context and hasattr(context, "client_context") and context.client_context:
        custom = getattr(context.client_context, "custom", {}) or {}
        if custom.get("bedrockAgentCoreToolName"):
            return custom["bedrockAgentCoreToolName"]
    # 2. event.params.name (JSON-RPC style)
    if "params" in event and "name" in event.get("params", {}):
        return event["params"]["name"]
    # 3. explicit fields
    return event.get("tool_name") or event.get("tool", "")


def _extract_arguments(event: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
    if "params" in event and "arguments" in event.get("params", {}):
        return event["params"]["arguments"]
    if tool_name and not any(k in event for k in ["params", "tool_name", "tool", "arguments"]):
        return event  # event IS the arguments (AgentCore Gateway format)
    return event.get("arguments", {})


def _extract_correlation_id(event: Dict[str, Any], context: Any) -> str:
    for path in [["context", "correlation_id"], ["metadata", "correlation_id"]]:
        obj = event
        for key in path:
            if isinstance(obj, dict):
                obj = obj.get(key)
        if isinstance(obj, str):
            return obj
    headers = event.get("headers", {})
    cid = headers.get("X-Correlation-ID") or headers.get("x-correlation-id")
    return cid or str(uuid.uuid4())


def _error(
    correlation_id: str,
    message: str,
    error_code: str = "BAD_REQUEST",
    status_code: int = 400,
) -> Dict[str, Any]:
    body = {
        "error": message,
        "error_code": error_code,
        "correlation_id": correlation_id,
        "timestamp": datetime.utcnow().isoformat(),
    }
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json", "X-Correlation-ID": correlation_id},
        "body": json.dumps(body),
    }
