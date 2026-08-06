"""
Banking tools Lambda handler.

Implements a simulated banking back-end for the temporal-policy workshop.
All state is in-memory (resets per Lambda cold start) — sufficient for demos.

Tools exposed via MCP:
  get_account_balance   - look up an account and return its balance + account ID
  transfer_funds        - move money between accounts
  get_transaction_history - return recent transactions for an account
  freeze_account        - flag an account as frozen (admin action)
  unfreeze_account      - remove freeze flag (admin action)
  approve_transfer      - record a human approval for a pending transfer
  reject_transfer       - record a human rejection for a pending transfer

Temporal policies on the gateway enforce:
  1. Output-to-input integrity  : transfer_funds.toAccount must match a prior
                                  get_account_balance.output.accountId
  2. Cumulative daily cap       : sum of transfer_funds.amount in 24h < $60,000
  3. Session rate limit         : at most 5 transfer_funds requests per 5 minutes
  4. Approval gate              : transfer_funds > $10,000 requires a prior
                                  approve_transfer that has not been consumed
  5. Mutual exclusion           : approve_transfer and reject_transfer cannot
                                  both occur for the same transferId in 5 minutes
  6. Freshness gate             : transfer_funds must follow get_account_balance
                                  within 2 minutes (not just any time in the session)
"""

import json
import random
import string
from datetime import datetime

# ---------------------------------------------------------------------------
# Simulated account store
# ---------------------------------------------------------------------------

ACCOUNTS: dict[str, dict] = {
    "ACC-1001": {"owner": "Alice Johnson", "balance": 85_000.00, "frozen": False},
    "ACC-2002": {"owner": "Bob Smith", "balance": 12_500.00, "frozen": False},
    "ACC-3003": {"owner": "Carol White", "balance": 250_000.00, "frozen": False},
    "ACC-4004": {"owner": "David Lee", "balance": 3_400.00, "frozen": False},
    "ACC-5005": {"owner": "Eve Martinez", "balance": 99_000.00, "frozen": True},
}

# Simulated transaction log (in-memory)
TRANSACTIONS: list[dict] = [
    {
        "id": "TXN-0001",
        "from": "ACC-1001",
        "to": "ACC-2002",
        "amount": 500.00,
        "ts": "2026-08-04T10:00:00Z",
        "status": "completed",
    },
    {
        "id": "TXN-0002",
        "from": "ACC-3003",
        "to": "ACC-1001",
        "amount": 1200.00,
        "ts": "2026-08-04T11:30:00Z",
        "status": "completed",
    },
    {
        "id": "TXN-0003",
        "from": "ACC-2002",
        "to": "ACC-4004",
        "amount": 300.00,
        "ts": "2026-08-04T14:00:00Z",
        "status": "completed",
    },
]

# Pending approvals: transferId -> {"status": "approved"|"rejected", "approvedBy": str}
APPROVALS: dict[str, dict] = {}


def _generate_id(prefix: str) -> str:
    suffix = "".join(random.choices(string.digits, k=6))
    return f"{prefix}-{suffix}"


def _timestamp() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def get_account_balance(account_id: str) -> dict:
    """
    Look up an account and return its current balance and owner.

    Returns:
        accountId, owner, balance, frozen, currency, timestamp
    """
    if account_id not in ACCOUNTS:
        return {"error": f"Account {account_id} not found"}

    acct = ACCOUNTS[account_id]
    return {
        "accountId": account_id,
        "owner": acct["owner"],
        "balance": acct["balance"],
        "frozen": acct["frozen"],
        "currency": "USD",
        "asOf": _timestamp(),
    }


def transfer_funds(
    from_account: str, to_account: str, amount: float, memo: str = ""
) -> dict:
    """
    Transfer funds between two accounts.

    The gateway enforces:
    - to_account must match the accountId returned by a prior get_account_balance
    - cumulative daily transfers must stay under $60,000
    - at most 5 transfers per 5-minute window
    - transfers > $10,000 require a prior approve_transfer

    Returns:
        transactionId, status, fromAccount, toAccount, amount, timestamp
    """
    if from_account not in ACCOUNTS:
        return {"error": f"Source account {from_account} not found"}
    if to_account not in ACCOUNTS:
        return {"error": f"Destination account {to_account} not found"}

    src = ACCOUNTS[from_account]
    dst = ACCOUNTS[to_account]

    if src["frozen"]:
        return {"error": f"Account {from_account} is frozen"}
    if dst["frozen"]:
        return {"error": f"Account {to_account} is frozen"}
    if amount <= 0:
        return {"error": "Transfer amount must be positive"}
    if src["balance"] < amount:
        return {"error": f"Insufficient funds: balance is ${src['balance']:.2f}"}

    src["balance"] -= amount
    dst["balance"] += amount

    txn_id = _generate_id("TXN")
    txn = {
        "id": txn_id,
        "from": from_account,
        "to": to_account,
        "amount": amount,
        "memo": memo,
        "ts": _timestamp(),
        "status": "completed",
    }
    TRANSACTIONS.append(txn)

    return {
        "transactionId": txn_id,
        "status": "completed",
        "fromAccount": from_account,
        "toAccount": to_account,
        "amount": amount,
        "memo": memo,
        "timestamp": txn["ts"],
    }


def get_transaction_history(account_id: str, limit: int = 10) -> dict:
    """
    Return the most recent transactions for an account.

    Returns:
        accountId, transactions (list), count
    """
    if account_id not in ACCOUNTS:
        return {"error": f"Account {account_id} not found"}

    acct_txns = [
        t for t in TRANSACTIONS if t["from"] == account_id or t["to"] == account_id
    ]
    recent = sorted(acct_txns, key=lambda t: t["ts"], reverse=True)[:limit]

    return {
        "accountId": account_id,
        "transactions": recent,
        "count": len(recent),
    }


def freeze_account(account_id: str, reason: str = "") -> dict:
    """
    Freeze an account, preventing all transfers from or to it.

    Returns:
        accountId, frozen, reason, timestamp
    """
    if account_id not in ACCOUNTS:
        return {"error": f"Account {account_id} not found"}

    ACCOUNTS[account_id]["frozen"] = True
    return {
        "accountId": account_id,
        "frozen": True,
        "reason": reason,
        "timestamp": _timestamp(),
    }


def unfreeze_account(account_id: str) -> dict:
    """
    Remove the freeze flag from an account.

    Returns:
        accountId, frozen, timestamp
    """
    if account_id not in ACCOUNTS:
        return {"error": f"Account {account_id} not found"}

    ACCOUNTS[account_id]["frozen"] = False
    return {
        "accountId": account_id,
        "frozen": False,
        "timestamp": _timestamp(),
    }


def approve_transfer(transfer_id: str, approved_by: str, notes: str = "") -> dict:
    """
    Record a human approval for a pending high-value transfer.

    The gateway's approval-gate temporal policy checks for this event before
    permitting transfer_funds calls above $10,000.

    Returns:
        transferId, status, approvedBy, notes, timestamp
    """
    APPROVALS[transfer_id] = {
        "status": "approved",
        "approvedBy": approved_by,
        "notes": notes,
        "timestamp": _timestamp(),
    }
    return {
        "transferId": transfer_id,
        "status": "approved",
        "approvedBy": approved_by,
        "notes": notes,
        "timestamp": APPROVALS[transfer_id]["timestamp"],
    }


def reject_transfer(transfer_id: str, rejected_by: str, reason: str = "") -> dict:
    """
    Record a human rejection for a pending transfer.

    The gateway's mutual-exclusion temporal policy prevents approve_transfer
    and reject_transfer from both occurring for the same transferId in 5 minutes.

    Returns:
        transferId, status, rejectedBy, reason, timestamp
    """
    APPROVALS[transfer_id] = {
        "status": "rejected",
        "rejectedBy": rejected_by,
        "reason": reason,
        "timestamp": _timestamp(),
    }
    return {
        "transferId": transfer_id,
        "status": "rejected",
        "rejectedBy": rejected_by,
        "reason": reason,
        "timestamp": APPROVALS[transfer_id]["timestamp"],
    }


# ---------------------------------------------------------------------------
# MCP dispatch
# ---------------------------------------------------------------------------

TOOL_MAP = {
    "get_account_balance": get_account_balance,
    "transfer_funds": transfer_funds,
    "get_transaction_history": get_transaction_history,
    "freeze_account": freeze_account,
    "unfreeze_account": unfreeze_account,
    "approve_transfer": approve_transfer,
    "reject_transfer": reject_transfer,
}


def _resolve_tool_name(event: dict, context) -> str:
    """
    AgentCore Gateway passes the tool name in the Lambda client context under
    custom["bedrockAgentCoreToolName"], prefixed with the target name
    (e.g. "banking-tools___get_account_balance"). Strip the target prefix.
    """
    name = ""
    client_context = getattr(context, "client_context", None)
    if client_context is not None:
        custom = getattr(client_context, "custom", None) or {}
        name = custom.get("bedrockAgentCoreToolName", "")
    # Fallbacks for local testing.
    if not name:
        name = event.get("toolName") or event.get("name") or ""
    if "___" in name:
        name = name.split("___", 1)[1]
    return name


def lambda_handler(event: dict, context) -> dict:
    """
    Lambda entry point for AgentCore Gateway MCP tool calls.

    The gateway invokes this function with the tool arguments as the event
    payload and the tool name in the client context. It does not send an
    MCP-style {method, params} envelope, and it never calls tools/list (the
    tool schema is provided inline when the gateway target is created).
    """
    tool_name = _resolve_tool_name(event, context)
    arguments = event if isinstance(event, dict) else {}

    fn = TOOL_MAP.get(tool_name)
    if fn is None:
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"Unknown tool: {tool_name!r}"}],
        }

    try:
        result = fn(**arguments)
    except TypeError as e:
        return {
            "isError": True,
            "content": [
                {"type": "text", "text": f"Invalid arguments for {tool_name}: {e}"}
            ],
        }

    if "error" in result:
        return {
            "isError": True,
            "content": [{"type": "text", "text": result["error"]}],
        }

    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
