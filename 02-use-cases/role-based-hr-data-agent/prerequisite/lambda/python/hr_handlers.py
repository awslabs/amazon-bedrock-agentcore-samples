"""
HR tool handlers: search_employee, get_employee_profile, get_employee_compensation.

The Lambda returns all data; field-level DLP redaction is applied downstream
by the Gateway Response Interceptor based on the caller's OAuth scopes.
"""

from typing import Any, Dict, List

from dummy_data import (
    get_employee_by_id,
    get_employee_compensation_data,
    search_employees_by_query,
    validate_tenant_access,
)
from audit_logger import (
    log_data_access,
    log_tenant_access_check,
    log_tool_invocation,
)


def inject_correlation_id(arguments: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
    out = arguments.copy()
    out["_correlation_id"] = correlation_id
    return out


# ---------------------------------------------------------------------------
# search_employee
# ---------------------------------------------------------------------------

def handle_search_employee(arguments: Dict[str, Any]) -> Dict[str, Any]:
    query = arguments.get("query", "").strip()
    tenant_id = arguments.get("tenantId", "")
    correlation_id = arguments.get("_correlation_id", "unknown")

    if not tenant_id:
        return {"error": "Missing required parameter: tenantId", "error_code": "MISSING_TENANT_ID"}
    if not query:
        return {"error": "Missing required parameter: query", "error_code": "MISSING_QUERY"}

    try:
        employees = search_employees_by_query(query, tenant_id, max_results=10)
        log_data_access(correlation_id, tenant_id, data_type="employee_search", access_granted=True,
                        reason=f"Search query: {query}")
        log_tool_invocation(correlation_id, "search_employee", tenant_id, result_count=len(employees), success=True)
        return {
            "employees": employees,
            "total_count": len(employees),
            "query": query,
            "tenant_id": tenant_id,
        }
    except Exception as e:
        log_tool_invocation(correlation_id, "search_employee", tenant_id, success=False)
        return {"error": f"Employee search failed: {str(e)}", "error_code": "SEARCH_FAILED"}


# ---------------------------------------------------------------------------
# get_employee_profile
# ---------------------------------------------------------------------------

def handle_get_employee_profile(arguments: Dict[str, Any]) -> Dict[str, Any]:
    employee_id = arguments.get("employeeId", "").strip()
    tenant_id = arguments.get("tenantId", "")
    correlation_id = arguments.get("_correlation_id", "unknown")

    if not tenant_id:
        return {"error": "Missing required parameter: tenantId", "error_code": "MISSING_TENANT_ID"}
    if not employee_id:
        return {"error": "Missing required parameter: employeeId", "error_code": "MISSING_EMPLOYEE_ID"}

    access_ok = validate_tenant_access(employee_id, tenant_id)
    log_tenant_access_check(correlation_id, tenant_id, employee_id, access_ok)
    if not access_ok:
        return {"error": "Employee not found or access denied", "error_code": "EMPLOYEE_NOT_FOUND",
                "employee_id": employee_id, "tenant_id": tenant_id}

    try:
        emp = get_employee_by_id(employee_id, tenant_id)
        if not emp:
            return {"error": "Employee not found", "error_code": "EMPLOYEE_NOT_FOUND",
                    "employee_id": employee_id, "tenant_id": tenant_id}

        log_data_access(correlation_id, tenant_id, employee_id, "employee_profile", True)
        log_tool_invocation(correlation_id, "get_employee_profile", tenant_id, result_count=1, success=True)

        return {
            "employee_id": emp["employee_id"],
            "name": emp["name"],
            "department": emp["department"],
            "role": emp["role"],
            "hire_date": emp["hire_date"],
            "manager": emp["manager"],
            "status": emp["status"],
            # PII — redacted by Response Interceptor without hr-dlp-gateway/pii scope
            "email": emp["email"],
            "phone": emp["phone"],
            "personal_phone": emp["personal_phone"],
            "emergency_contact": emp["emergency_contact"],
            # Address — redacted without hr-dlp-gateway/address scope
            "address": emp["address"],
            "city": emp["city"],
            "state": emp["state"],
            "zip_code": emp["zip_code"],
            # Compensation hint — redacted without hr-dlp-gateway/comp scope
            "pay_grade": emp["pay_grade"],
        }
    except Exception as e:
        log_tool_invocation(correlation_id, "get_employee_profile", tenant_id, success=False)
        return {"error": f"Profile retrieval failed: {str(e)}", "error_code": "PROFILE_RETRIEVAL_FAILED"}


# ---------------------------------------------------------------------------
# get_employee_compensation
# ---------------------------------------------------------------------------

def handle_get_employee_compensation(arguments: Dict[str, Any]) -> Dict[str, Any]:
    employee_id = arguments.get("employeeId", "").strip()
    tenant_id = arguments.get("tenantId", "")
    correlation_id = arguments.get("_correlation_id", "unknown")

    if not tenant_id:
        return {"error": "Missing required parameter: tenantId", "error_code": "MISSING_TENANT_ID"}
    if not employee_id:
        return {"error": "Missing required parameter: employeeId", "error_code": "MISSING_EMPLOYEE_ID"}

    access_ok = validate_tenant_access(employee_id, tenant_id)
    log_tenant_access_check(correlation_id, tenant_id, employee_id, access_ok)
    if not access_ok:
        return {"error": "Employee not found or access denied", "error_code": "EMPLOYEE_NOT_FOUND",
                "employee_id": employee_id, "tenant_id": tenant_id}

    try:
        comp = get_employee_compensation_data(employee_id, tenant_id)
        if not comp:
            return {"error": "Employee not found", "error_code": "EMPLOYEE_NOT_FOUND"}

        log_data_access(correlation_id, tenant_id, employee_id, "employee_compensation", True)
        log_tool_invocation(correlation_id, "get_employee_compensation", tenant_id, result_count=1, success=True)
        return comp
    except Exception as e:
        log_tool_invocation(correlation_id, "get_employee_compensation", tenant_id, success=False)
        return {"error": f"Compensation retrieval failed: {str(e)}", "error_code": "COMPENSATION_RETRIEVAL_FAILED"}


# ---------------------------------------------------------------------------
# Schema + validation helpers
# ---------------------------------------------------------------------------

def get_available_tools() -> List[Dict[str, Any]]:
    return [
        {
            "name": "hr-lambda-target___search_employee",
            "description": "Search for employees by name, department, or role",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "tenantId": {"type": "string"},
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
        },
        {
            "name": "hr-lambda-target___get_employee_profile",
            "description": "Get detailed employee profile information",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "tenantId": {"type": "string"},
                    "employeeId": {"type": "string"},
                },
                "required": ["employeeId"],
            },
        },
        {
            "name": "hr-lambda-target___get_employee_compensation",
            "description": "Get employee compensation data (requires hr-dlp-gateway/comp scope)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "tenantId": {"type": "string"},
                    "employeeId": {"type": "string"},
                },
                "required": ["employeeId"],
            },
        },
    ]


def validate_tool_arguments(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    tools = get_available_tools()
    tool_def = next((t for t in tools if t["name"] == tool_name), None)
    if not tool_def:
        # Unknown tool name — pass through for base-tool routing
        return {"valid": True, "message": "Unknown tool name, routing by base name"}

    required = tool_def["inputSchema"].get("required", [])
    missing = [f for f in required if not arguments.get(f)]
    if missing:
        return {
            "valid": False,
            "error": f"Missing required fields: {', '.join(missing)}",
            "error_code": "MISSING_REQUIRED_FIELDS",
        }
    return {"valid": True, "message": "Arguments are valid"}
