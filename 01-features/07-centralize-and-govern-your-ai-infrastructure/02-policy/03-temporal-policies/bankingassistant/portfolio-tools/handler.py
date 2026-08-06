"""
Portfolio advisor Lambda handler.

Implements a simulated investment advisory back-end for the temporal-policy workshop.
All state is in-memory (resets per Lambda cold start) — sufficient for demos.

Tools exposed via MCP:
  get_client_profile   - retrieve client risk tolerance, restrictions, and portfolio IDs
  load_portfolio       - retrieve holdings and current positions for a portfolio
  get_market_price     - fetch current market price for a security
  execute_trade        - execute a buy or sell order against a portfolio
  rebalance_portfolio  - adjust portfolio allocations across holdings
  approve_trade        - record advisor approval for a large trade
  interact_advisor     - record an advisor interaction (resets the trust-decay clock)

Temporal policies on the gateway enforce:
  1. Workflow sequencing    : load_portfolio requires prior get_client_profile;
                             rebalance_portfolio requires prior load_portfolio
  2. Output-to-input        : execute_trade.portfolio_id must match get_client_profile output
  3. Data freshness         : execute_trade requires get_market_price within 30s
  4. Cumulative budget cap  : total trade value per session < $60,000
  5. Human approval gate    : trades > $25,000 require approve_trade (one-time consumption)
  6. Mutual exclusion       : cannot sell a security at a loss after buying it in the same session
  7. Progressive trust decay: execute_trade / rebalance_portfolio denied after 15 min without
                              advisor interaction
"""

import json
import random
import string
from datetime import datetime

# ---------------------------------------------------------------------------
# Simulated data store
# ---------------------------------------------------------------------------

CLIENTS: dict[str, dict] = {
    "CLIENT-001": {
        "name": "Alice Johnson",
        "risk_tolerance": "moderate",
        "restrictions": ["no_tobacco", "no_weapons"],
        "portfolio_ids": ["PORT-8821", "PORT-8822"],
    },
    "CLIENT-002": {
        "name": "Bob Smith",
        "risk_tolerance": "aggressive",
        "restrictions": [],
        "portfolio_ids": ["PORT-3347"],
    },
    "CLIENT-003": {
        "name": "Carol White",
        "risk_tolerance": "conservative",
        "restrictions": ["esg_only"],
        "portfolio_ids": ["PORT-5501", "PORT-5502"],
    },
}

PORTFOLIOS: dict[str, dict] = {
    "PORT-8821": {
        "client_id": "CLIENT-001",
        "holdings": [
            {"symbol": "AAPL", "shares": 100, "avg_cost": 155.00},
            {"symbol": "MSFT", "shares": 50, "avg_cost": 310.00},
            {"symbol": "AMZN", "shares": 20, "avg_cost": 3200.00},
        ],
        "cash": 12_500.00,
    },
    "PORT-8822": {
        "client_id": "CLIENT-001",
        "holdings": [
            {"symbol": "GOOGL", "shares": 10, "avg_cost": 2800.00},
        ],
        "cash": 5_000.00,
    },
    "PORT-3347": {
        "client_id": "CLIENT-002",
        "holdings": [
            {"symbol": "TSLA", "shares": 200, "avg_cost": 220.00},
            {"symbol": "NVDA", "shares": 30, "avg_cost": 450.00},
        ],
        "cash": 8_000.00,
    },
    "PORT-5501": {
        "client_id": "CLIENT-003",
        "holdings": [
            {"symbol": "VTI", "shares": 300, "avg_cost": 220.00},
        ],
        "cash": 25_000.00,
    },
    "PORT-5502": {
        "client_id": "CLIENT-003",
        "holdings": [],
        "cash": 50_000.00,
    },
}

MARKET_PRICES: dict[str, float] = {
    "AAPL": 178.50,
    "MSFT": 335.00,
    "AMZN": 3_450.00,
    "GOOGL": 2_950.00,
    "TSLA": 195.00,
    "NVDA": 520.00,
    "VTI": 235.00,
    "SPY": 445.00,
    "QQQ": 380.00,
}

TRADE_LOG: list[dict] = []
APPROVALS: dict[str, dict] = {}


def _generate_id(prefix: str) -> str:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefix}-{suffix}"


def _timestamp() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def get_client_profile(client_id: str) -> dict:
    if client_id not in CLIENTS:
        return {"error": f"Client {client_id} not found"}
    client = CLIENTS[client_id]
    return {
        "clientId": client_id,
        "name": client["name"],
        "riskTolerance": client["risk_tolerance"],
        "restrictions": client["restrictions"],
        "portfolioIds": client["portfolio_ids"],
        "asOf": _timestamp(),
    }


def load_portfolio(portfolio_id: str) -> dict:
    if portfolio_id not in PORTFOLIOS:
        return {"error": f"Portfolio {portfolio_id} not found"}
    port = PORTFOLIOS[portfolio_id]
    holdings_with_value = []
    for h in port["holdings"]:
        price = MARKET_PRICES.get(h["symbol"], h["avg_cost"])
        market_value = price * h["shares"]
        unrealized_pnl = (price - h["avg_cost"]) * h["shares"]
        holdings_with_value.append(
            {
                "symbol": h["symbol"],
                "shares": h["shares"],
                "avgCost": h["avg_cost"],
                "currentPrice": price,
                "marketValue": round(market_value, 2),
                "unrealizedPnL": round(unrealized_pnl, 2),
            }
        )
    total_value = sum(h["marketValue"] for h in holdings_with_value) + port["cash"]
    return {
        "portfolioId": portfolio_id,
        "clientId": port["client_id"],
        "holdings": holdings_with_value,
        "cash": port["cash"],
        "totalValue": round(total_value, 2),
        "asOf": _timestamp(),
    }


def get_market_price(symbol: str) -> dict:
    symbol = symbol.upper()
    if symbol not in MARKET_PRICES:
        return {"error": f"Symbol {symbol} not found"}
    price = MARKET_PRICES[symbol]
    return {
        "symbol": symbol,
        "price": price,
        "currency": "USD",
        "asOf": _timestamp(),
    }


def execute_trade(
    portfolio_id: str,
    symbol: str,
    action: str,
    shares: int,
    cost: float,
) -> dict:
    if portfolio_id not in PORTFOLIOS:
        return {"error": f"Portfolio {portfolio_id} not found"}

    symbol = symbol.upper()
    action = action.upper()
    if action not in ("BUY", "SELL"):
        return {"error": "action must be BUY or SELL"}

    port = PORTFOLIOS[portfolio_id]
    price = MARKET_PRICES.get(symbol)
    if price is None:
        return {"error": f"Symbol {symbol} not found"}

    total = shares * price

    if action == "BUY":
        if port["cash"] < total:
            return {
                "error": f"Insufficient cash: have ${port['cash']:.2f}, need ${total:.2f}"
            }
        port["cash"] -= total
        holding = next((h for h in port["holdings"] if h["symbol"] == symbol), None)
        if holding:
            new_shares = holding["shares"] + shares
            holding["avg_cost"] = (
                holding["avg_cost"] * holding["shares"] + total
            ) / new_shares
            holding["shares"] = new_shares
        else:
            port["holdings"].append(
                {"symbol": symbol, "shares": shares, "avg_cost": price}
            )
    else:
        holding = next((h for h in port["holdings"] if h["symbol"] == symbol), None)
        if not holding or holding["shares"] < shares:
            available = holding["shares"] if holding else 0
            return {"error": f"Insufficient shares: have {available}, need {shares}"}
        holding["shares"] -= shares
        if holding["shares"] == 0:
            port["holdings"].remove(holding)
        port["cash"] += total

    trade_id = _generate_id("TRD")
    trade = {
        "tradeId": trade_id,
        "portfolioId": portfolio_id,
        "symbol": symbol,
        "action": action,
        "shares": shares,
        "price": price,
        "cost": round(total, 2),
        "timestamp": _timestamp(),
        "status": "executed",
    }
    TRADE_LOG.append(trade)
    return trade


def rebalance_portfolio(portfolio_id: str, target_allocations: list) -> dict:
    """
    Adjust portfolio to target allocations.
    target_allocations: list of {"symbol": str, "target_pct": float}
    """
    if portfolio_id not in PORTFOLIOS:
        return {"error": f"Portfolio {portfolio_id} not found"}

    port = PORTFOLIOS[portfolio_id]
    total_value = (
        sum(
            MARKET_PRICES.get(h["symbol"], h["avg_cost"]) * h["shares"]
            for h in port["holdings"]
        )
        + port["cash"]
    )

    rebalance_id = _generate_id("RBL")
    actions = []
    for alloc in target_allocations:
        symbol = alloc["symbol"].upper()
        target_pct = alloc["target_pct"]
        target_value = total_value * (target_pct / 100.0)
        price = MARKET_PRICES.get(symbol, 0)
        if price == 0:
            continue
        target_shares = int(target_value / price)
        current = next((h for h in port["holdings"] if h["symbol"] == symbol), None)
        current_shares = current["shares"] if current else 0
        delta = target_shares - current_shares
        if delta != 0:
            actions.append(
                {
                    "symbol": symbol,
                    "action": "BUY" if delta > 0 else "SELL",
                    "shares": abs(delta),
                    "estimatedCost": round(abs(delta) * price, 2),
                }
            )

    return {
        "rebalanceId": rebalance_id,
        "portfolioId": portfolio_id,
        "totalPortfolioValue": round(total_value, 2),
        "proposedActions": actions,
        "timestamp": _timestamp(),
        "status": "proposed",
    }


def approve_trade(trade_request_id: str, approved_by: str, notes: str = "") -> dict:
    APPROVALS[trade_request_id] = {
        "status": "approved",
        "approvedBy": approved_by,
        "notes": notes,
        "timestamp": _timestamp(),
    }
    return {
        "tradeRequestId": trade_request_id,
        "status": "approved",
        "approvedBy": approved_by,
        "notes": notes,
        "timestamp": APPROVALS[trade_request_id]["timestamp"],
    }


def interact_advisor(
    advisor_id: str, action: str = "check_in", notes: str = ""
) -> dict:
    """Record an advisor interaction — resets the 15-minute trust-decay clock."""
    return {
        "advisorId": advisor_id,
        "action": action,
        "notes": notes,
        "timestamp": _timestamp(),
        "message": "Advisor interaction recorded. Write access restored for 15 minutes.",
    }


# ---------------------------------------------------------------------------
# MCP dispatch
# ---------------------------------------------------------------------------

TOOL_MAP = {
    "get_client_profile": get_client_profile,
    "load_portfolio": load_portfolio,
    "get_market_price": get_market_price,
    "execute_trade": execute_trade,
    "rebalance_portfolio": rebalance_portfolio,
    "approve_trade": approve_trade,
    "interact_advisor": interact_advisor,
}


def _resolve_tool_name(event: dict, context) -> str:
    """
    AgentCore Gateway passes the tool name in the Lambda client context under
    custom["bedrockAgentCoreToolName"], prefixed with the target name
    (e.g. "portfolio-tools___execute_trade"). Strip the target prefix.
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
