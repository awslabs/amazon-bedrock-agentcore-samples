"""
Mock Lambda tool handlers for multi-tenant gateway isolation demo.

Each function simulates a tool that belongs to a specific tenant domain.
In production these would be separate Lambda functions; here they share
one handler dispatched by the event's tool name.
"""

import json


def handler(event, context):
    """Single Lambda handler dispatching by tool_name."""
    tool_name = event.get("tool_name", "unknown")
    arguments = event.get("arguments", {})

    dispatch = {
        # Insurance tenant tools
        "submit_decision": _submit_decision,
        "notify_team": _notify_team,
        "query_claims": _query_claims,
        "query_members": _query_members,
        "query_providers": _query_providers,
        "query_benefits": _query_benefits,
        # Banking tenant tools
        "flag_suspicious": _flag_suspicious,
        "query_accounts": _query_accounts,
        "query_transactions": _query_transactions,
    }

    fn = dispatch.get(tool_name)
    if not fn:
        return {"statusCode": 400, "body": json.dumps({"error": f"Unknown tool: {tool_name}"})}

    result = fn(arguments)
    return {"statusCode": 200, "body": json.dumps(result)}


# Insurance tools


def _submit_decision(args):
    claim_id = args.get("claim_id", "CLM-001")
    decision = args.get("decision", "approved")
    return {"claim_id": claim_id, "decision": decision, "status": "recorded"}


def _notify_team(args):
    team = args.get("team", "underwriting")
    message = args.get("message", "Decision submitted")
    return {"team": team, "message": message, "delivered": True}


def _query_claims(args):
    member_id = args.get("member_id", "MBR-100")
    return {
        "member_id": member_id,
        "claims": [
            {"claim_id": "CLM-001", "amount": 2500, "status": "pending"},
            {"claim_id": "CLM-002", "amount": 800, "status": "approved"},
        ],
    }


def _query_members(args):
    plan_id = args.get("plan_id", "PLAN-A")
    return {
        "plan_id": plan_id,
        "members": [
            {"member_id": "MBR-100", "name": "Alice Johnson"},
            {"member_id": "MBR-101", "name": "Bob Smith"},
        ],
    }


def _query_providers(args):
    specialty = args.get("specialty", "general")
    return {
        "specialty": specialty,
        "providers": [
            {"provider_id": "PRV-01", "name": "City Hospital", "in_network": True},
            {"provider_id": "PRV-02", "name": "Valley Clinic", "in_network": True},
        ],
    }


def _query_benefits(args):
    plan_id = args.get("plan_id", "PLAN-A")
    return {
        "plan_id": plan_id,
        "benefits": {
            "deductible": 1000,
            "out_of_pocket_max": 5000,
            "copay_primary": 25,
            "copay_specialist": 50,
        },
    }


# Banking tools


def _flag_suspicious(args):
    transaction_id = args.get("transaction_id", "TXN-999")
    reason = args.get("reason", "unusual_amount")
    return {"transaction_id": transaction_id, "flagged": True, "reason": reason}


def _query_accounts(args):
    customer_id = args.get("customer_id", "CUST-001")
    return {
        "customer_id": customer_id,
        "accounts": [
            {"account_id": "ACC-100", "type": "checking", "balance": 15420.50},
            {"account_id": "ACC-101", "type": "savings", "balance": 82300.00},
        ],
    }


def _query_transactions(args):
    account_id = args.get("account_id", "ACC-100")
    return {
        "account_id": account_id,
        "transactions": [
            {"txn_id": "TXN-501", "amount": -250.00, "merchant": "AWS", "date": "2026-05-27"},
            {"txn_id": "TXN-502", "amount": -89.99, "merchant": "Grocery Store", "date": "2026-05-26"},
            {"txn_id": "TXN-503", "amount": 3200.00, "merchant": "Direct Deposit", "date": "2026-05-25"},
        ],
    }
