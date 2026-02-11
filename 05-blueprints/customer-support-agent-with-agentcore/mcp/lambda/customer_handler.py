import json
from typing import Any, Dict

# Mock Data Store
CUSTOMERS = {
    "CUST-001": {
        "customer_id": "CUST-001",
        "name": "John Doe",
        "email": "john@example.com",
        "member_since": "2023-06-01",
    },
    "CUST-002": {
        "customer_id": "CUST-002",
        "name": "Jane Smith",
        "email": "jane@example.com",
        "member_since": "2024-01-15",
    },
}


def lambda_handler(event, context):
    """
    Lambda handler for Customer APIs via Bedrock AgentCore Gateway.
    """
    try:
        extended_name = context.client_context.custom.get("bedrockAgentCoreToolName")
        tool_name = None

        if extended_name and "___" in extended_name:
            tool_name = extended_name.split("___", 1)[1]

        if not tool_name:
            return _response(400, {"error": "Missing tool name"})

        if tool_name == "get_customer":
            return get_customer(event)
        elif tool_name == "list_customers":
            return list_customers(event)
        else:
            return _response(400, {"error": f"Unknown tool '{tool_name}'"})

    except Exception as e:
        return _response(500, {"system_error": str(e)})


def _response(status_code: int, body: Dict[str, Any]):
    """Consistent JSON response wrapper."""
    return {"statusCode": status_code, "body": json.dumps(body)}


def get_customer(event: Dict[str, Any]):
    """Look up customer information and summary."""
    customer_id = event.get("customer_id")

    if not customer_id:
        return _response(
            400,
            {
                "success": False,
                "error": "customer_id is required",
                "error_code": "MISSING_PARAMETER",
            },
        )

    customer = CUSTOMERS.get(customer_id)

    if not customer:
        return _response(
            404,
            {
                "success": False,
                "error": f"Customer {customer_id} not found",
                "error_code": "CUSTOMER_NOT_FOUND",
            },
        )

    return _response(200, customer)


def list_customers(event: Dict[str, Any]):
    """List all customers with optional name filter."""
    name_filter = event.get("name", "").lower()

    customers_list = []
    for customer in CUSTOMERS.values():
        if name_filter and name_filter not in customer["name"].lower():
            continue
        customers_list.append(customer)

    return _response(200, {"customers": customers_list, "count": len(customers_list)})
