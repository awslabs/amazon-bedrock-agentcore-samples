"""MCP tool schemas published through the AgentCore Gateway.

The Gateway uses these schemas (rather than introspection of the Lambda)
to advertise tools to MCP clients. Keep them aligned with the Lambda
handlers in lambdas/tools/.
"""

LOOKUP_USER = {
    "name": "lookup_user",
    "description": (
        "Look up an internal user by user_id. Returns profile and quotas. "
        "Use this to understand the requester's context. Recurring-incident "
        "history is surfaced separately from AgentCore Memory."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "user_id": {"type": "string", "description": "Internal user ID, e.g. U-1001"},
        },
        "required": ["user_id"],
    },
}

GET_PROCESS_INFO = {
    "name": "get_process_info",
    "description": (
        "Look up an internal service / application / hardware process by "
        "name. Returns owner team, version, criticality, current_status, "
        "and known issues."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "process_name": {
                "type": "string",
                "description": "Canonical process name, e.g. corp-vpn",
            }
        },
        "required": ["process_name"],
    },
}

CREATE_CHANGE_REQUEST = {
    "name": "create_change_request",
    "description": (
        "Record a corrective action against a ticket. Stamps the user's "
        "record with last_incident_at and increments incident_count. "
        "Returns a change_id."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "ticket_id": {"type": "string"},
            "user_id": {"type": "string"},
            "summary": {"type": "string", "description": "Human-readable summary of the change."},
            "action": {
                "type": "string",
                "description": "Machine-readable action key (e.g. apply_smb_gateway_override).",
            },
        },
        "required": ["ticket_id", "user_id", "summary"],
    },
}

QUERY_KB = {
    "name": "query_kb",
    "description": (
        "Search the IT runbook knowledge base for relevant guidance. "
        "Use a focused query that names symptoms or affected processes."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "top_k": {"type": "integer", "default": 4},
        },
        "required": ["query"],
    },
}
