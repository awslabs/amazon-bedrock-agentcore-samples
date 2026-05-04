"""
Audit Logger for the HR Data Provider Lambda.

All HR data access attempts are logged to CloudWatch with structured JSON,
correlation IDs, and tenant context for compliance analysis.
"""

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class AuditEventType(Enum):
    LAMBDA_EXECUTION = "lambda_execution"
    TOOL_INVOCATION = "tool_invocation"
    DATA_ACCESS = "data_access"
    ERROR_OCCURRED = "error_occurred"
    VALIDATION_FAILED = "validation_failed"
    TENANT_ACCESS_CHECK = "tenant_access_check"


class AuditLogger:
    """Centralized audit logger for Lambda HR operations."""

    def __init__(self, logger_name: str = "hr-lambda-audit"):
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(handler)

    def log_lambda_execution(
        self,
        correlation_id: str,
        tool_name: str,
        tenant_id: str,
        function_name: str,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.logger.info(
            json.dumps(
                {
                    "event_type": AuditEventType.LAMBDA_EXECUTION.value,
                    "correlation_id": correlation_id,
                    "tool_name": tool_name,
                    "tenant_id": tenant_id,
                    "function_name": function_name,
                    "arguments": self._sanitize(arguments or {}),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
        )

    def log_tool_invocation(
        self,
        correlation_id: str,
        tool_name: str,
        tenant_id: str,
        result_count: Optional[int] = None,
        success: bool = True,
    ) -> None:
        self.logger.info(
            json.dumps(
                {
                    "event_type": AuditEventType.TOOL_INVOCATION.value,
                    "correlation_id": correlation_id,
                    "tool_name": tool_name,
                    "tenant_id": tenant_id,
                    "result_count": result_count,
                    "success": success,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
        )

    def log_data_access(
        self,
        correlation_id: str,
        tenant_id: str,
        employee_id: Optional[str] = None,
        data_type: str = "employee_data",
        access_granted: bool = True,
        reason: Optional[str] = None,
    ) -> None:
        entry = json.dumps(
            {
                "event_type": AuditEventType.DATA_ACCESS.value,
                "correlation_id": correlation_id,
                "tenant_id": tenant_id,
                "employee_id": employee_id,
                "data_type": data_type,
                "access_granted": access_granted,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        if access_granted:
            self.logger.info(entry)
        else:
            self.logger.warning(entry)

    def log_tenant_access_check(
        self,
        correlation_id: str,
        tenant_id: str,
        employee_id: str,
        access_granted: bool,
        reason: Optional[str] = None,
    ) -> None:
        entry = json.dumps(
            {
                "event_type": AuditEventType.TENANT_ACCESS_CHECK.value,
                "correlation_id": correlation_id,
                "tenant_id": tenant_id,
                "employee_id": employee_id,
                "access_granted": access_granted,
                "reason": reason or ("Access granted" if access_granted else "Tenant mismatch"),
                "security_check": "tenant_isolation",
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        if access_granted:
            self.logger.info(entry)
        else:
            self.logger.warning(entry)

    def log_error(
        self,
        correlation_id: str,
        error_message: str,
        error_type: str,
        tool_name: Optional[str] = None,
        tenant_id: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.logger.error(
            json.dumps(
                {
                    "event_type": AuditEventType.ERROR_OCCURRED.value,
                    "correlation_id": correlation_id,
                    "error_message": error_message,
                    "error_type": error_type,
                    "tool_name": tool_name,
                    "tenant_id": tenant_id,
                    "additional_context": additional_context or {},
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
        )

    def _sanitize(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        sanitized = arguments.copy()
        for field in ["password", "token", "secret", "key", "credential", "ssn"]:
            if field in sanitized:
                sanitized[field] = "[REDACTED]"
        for key, value in sanitized.items():
            if isinstance(value, str) and len(value) > 200:
                sanitized[key] = value[:200] + "...[TRUNCATED]"
        return sanitized


# Global instance + module-level convenience functions
audit_logger = AuditLogger()


def log_lambda_execution(correlation_id, tool_name, tenant_id, function_name, arguments=None):
    audit_logger.log_lambda_execution(correlation_id, tool_name, tenant_id, function_name, arguments)


def log_tool_invocation(correlation_id, tool_name, tenant_id, result_count=None, success=True):
    audit_logger.log_tool_invocation(correlation_id, tool_name, tenant_id, result_count, success)


def log_data_access(correlation_id, tenant_id, employee_id=None, data_type="employee_data",
                    access_granted=True, reason=None):
    audit_logger.log_data_access(correlation_id, tenant_id, employee_id, data_type, access_granted, reason)


def log_tenant_access_check(correlation_id, tenant_id, employee_id, access_granted, reason=None):
    audit_logger.log_tenant_access_check(correlation_id, tenant_id, employee_id, access_granted, reason)


def log_error(correlation_id, error_message, error_type, tool_name=None, tenant_id=None,
              additional_context=None):
    audit_logger.log_error(correlation_id, error_message, error_type, tool_name, tenant_id, additional_context)
