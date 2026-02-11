import json
import uuid
from typing import Any, Dict

# Mock Data Stores
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

ORDERS = {
    "ORD-12345": {
        "order_id": "ORD-12345",
        "customer_id": "CUST-001",
        "status": "delivered",
        "items": [{"name": "Wireless Headphones", "quantity": 1, "price": 79.99}],
        "total": 79.99,
        "order_date": "2025-01-15",
        "delivery_date": "2025-01-20",
    },
    "ORD-12300": {
        "order_id": "ORD-12300",
        "customer_id": "CUST-001",
        "status": "delivered",
        "items": [{"name": "Laptop Stand", "quantity": 1, "price": 249.00}],
        "total": 249.00,
        "order_date": "2025-01-02",
        "delivery_date": "2025-01-08",
    },
    "ORD-99000": {
        "order_id": "ORD-99000",
        "customer_id": "CUST-002",
        "status": "delivered",
        "items": [{"name": "Premium Laptop", "quantity": 1, "price": 1299.00}],
        "total": 1299.00,
        "order_date": "2025-01-10",
        "delivery_date": "2025-01-15",
    },
}

REFUNDS = {}  # Populated when refunds are processed


def lambda_handler(event, context):
    """
    Lambda handler for Customer Support APIs via Bedrock AgentCore Gateway.

    Expected input:
        event: {
            # tool-specific arguments
        }

    Context should contain:
        context.client_context.custom["bedrockAgentCoreToolName"]
        → e.g. "Target___get_order"
    """
    try:
        extended_name = context.client_context.custom.get("bedrockAgentCoreToolName")
        tool_name = None

        # handle agentcore gateway tool naming convention
        # https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-tool-naming.html
        if extended_name and "___" in extended_name:
            tool_name = extended_name.split("___", 1)[1]

        if not tool_name:
            return _response(400, {"error": "Missing tool name"})

        # Route to appropriate handler
        if tool_name == "get_order":
            return get_order(event)
        elif tool_name == "get_customer":
            return get_customer(event)
        elif tool_name == "list_orders":
            return list_orders(event)
        elif tool_name == "process_refund":
            return process_refund(event)
        else:
            return _response(400, {"error": f"Unknown tool '{tool_name}'"})

    except Exception as e:
        return _response(500, {"system_error": str(e)})


def _response(status_code: int, body: Dict[str, Any]):
    """Consistent JSON response wrapper."""
    return {"statusCode": status_code, "body": json.dumps(body)}


def get_order(event: Dict[str, Any]):
    """Look up order details by order ID."""
    order_id = event.get("order_id")

    if not order_id:
        return _response(
            400,
            {
                "success": False,
                "error": "order_id is required",
                "error_code": "MISSING_PARAMETER",
            },
        )

    order = ORDERS.get(order_id)

    if not order:
        return _response(
            404,
            {
                "success": False,
                "error": f"Order {order_id} not found",
                "error_code": "ORDER_NOT_FOUND",
            },
        )

    return _response(200, order)


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

    # Calculate order summary for this customer
    customer_orders = [o for o in ORDERS.values() if o["customer_id"] == customer_id]
    total_orders = len(customer_orders)
    total_spent = sum(o["total"] for o in customer_orders)

    return _response(
        200,
        {
            **customer,
            "total_orders": total_orders,
            "total_spent": round(total_spent, 2),
        },
    )


def list_orders(event: Dict[str, Any]):
    """List orders for a customer."""
    customer_id = event.get("customer_id")
    limit = event.get("limit", 10)

    if not customer_id:
        return _response(
            400,
            {
                "success": False,
                "error": "customer_id is required",
                "error_code": "MISSING_PARAMETER",
            },
        )

    # Check if customer exists
    if customer_id not in CUSTOMERS:
        return _response(
            404,
            {
                "success": False,
                "error": f"Customer {customer_id} not found",
                "error_code": "CUSTOMER_NOT_FOUND",
            },
        )

    # Get orders for this customer
    customer_orders = [
        {
            "order_id": o["order_id"],
            "total": o["total"],
            "status": o["status"],
            "order_date": o["order_date"],
        }
        for o in ORDERS.values()
        if o["customer_id"] == customer_id
    ]

    # Sort by order_date descending and apply limit
    customer_orders.sort(key=lambda x: x["order_date"], reverse=True)
    customer_orders = customer_orders[:limit]

    return _response(200, {"customer_id": customer_id, "orders": customer_orders})


def process_refund(event: Dict[str, Any]):
    """Process a refund for an order."""
    order_id = event.get("order_id")
    amount = event.get("amount")
    reason = event.get("reason")

    # Validate required parameters
    if not order_id:
        return _response(
            400,
            {
                "success": False,
                "error": "order_id is required",
                "error_code": "MISSING_PARAMETER",
            },
        )

    if amount is None:
        return _response(
            400,
            {
                "success": False,
                "error": "amount is required",
                "error_code": "MISSING_PARAMETER",
            },
        )

    if not reason:
        return _response(
            400,
            {
                "success": False,
                "error": "reason is required",
                "error_code": "MISSING_PARAMETER",
            },
        )

    # Check if order exists
    order = ORDERS.get(order_id)
    if not order:
        return _response(
            404,
            {
                "success": False,
                "error": f"Order {order_id} not found",
                "error_code": "ORDER_NOT_FOUND",
            },
        )

    # Validate refund amount
    if amount <= 0:
        return _response(
            400,
            {
                "success": False,
                "error": "Refund amount must be positive",
                "error_code": "INVALID_AMOUNT",
            },
        )

    if amount > order["total"]:
        return _response(
            400,
            {
                "success": False,
                "error": f"Refund amount ${amount} exceeds order total ${order['total']}",
                "error_code": "AMOUNT_EXCEEDS_ORDER",
            },
        )

    # Generate refund ID and process
    refund_id = f"REF-{uuid.uuid4().hex[:5].upper()}"

    refund_record = {
        "refund_id": refund_id,
        "order_id": order_id,
        "amount": amount,
        "reason": reason,
        "status": "processed",
    }

    # Store the refund
    REFUNDS[refund_id] = refund_record

    return _response(
        200,
        {
            "success": True,
            **refund_record,
            "message": f"Refund of ${amount:.2f} processed. Customer will receive funds in 3-5 business days.",
        },
    )
