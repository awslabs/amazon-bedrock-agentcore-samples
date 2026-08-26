"""Every tool answers through the real gateway, and the tenant changes the answer.

    cd backend && AWS_REGION=us-east-1 uv run python ../scripts/verify_tools.py
Four things are checked, in order of what they protect:

  1. **Every advertised tool answers through the real gateway** with a real token — not through a
     local handler, so the interceptor, Cedar and the target registration are all in the path.
  2. **No tool advertises a tenant field.** Fourteen schemas is fourteen chances to leak one, and
  the
     model must have no field in which to name another company.
  3. **A complete booking**: search → eligibility → prepare → confirm → cancel, with the
  cancellation
     terms shown before anything is cancelled.
  4. **The tenant changes the answer, three ways** — cap and currency, entitlement reasoning, and
     *capability* (whether `confirm_booking` is offered at all). Different data would be a weaker
     claim; a different *verdict* and a different *available action* is the real claim.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, "..")
from deployed_refs import refs  # noqa: E402

from scripts.verify_guardrails import (
    GATEWAY_URL,
    MCP_PROTOCOL_VERSION,
    call_tool,
    token_for,
)

CITY = "London"
DEPART = "2026-11-10"
CHECK_IN = "2026-11-10"
CHECK_OUT = "2026-11-13"


def report(name: str, passed: bool, detail: str = "") -> bool:
    print(f"  {'PASS' if passed else 'FAIL'}  {name}")
    for line in str(detail).splitlines():
        if line:
            print(f"        {line}")
    return passed


def list_tools(token: str) -> dict[str, list[str]]:
    """Every tool the gateway advertises, with its argument names."""
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}).encode()
    request = urllib.request.Request(
        GATEWAY_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {token}",
            "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            raw = response.read().decode()
    except urllib.error.HTTPError as error:
        raw = error.read().decode()
    for line in raw.splitlines():
        if line.startswith("data:"):
            raw = line[5:].strip()
            break
    tools = json.loads(raw).get("result", {}).get("tools", [])
    return {
        t["name"]: sorted((t.get("inputSchema") or {}).get("properties", {}).keys()) for t in tools
    }


def ok_response(response: dict) -> bool:
    """Whether the tool actually answered — transport *and* result.

    **`result.isError` is the part this originally missed, and the omission hid a total outage.** A
    gateway that cannot invoke any target still replies `200` with a well-formed JSON-RPC envelope
    whose `result` is `{"isError": true, "content": [{"text": "An internal error occurred."}]}`.
    With
    only the envelope checked, all eleven read tools reported *"every read tool answers through the
    real gateway"* while **not one of them ran** — a green check over a capability layer returning
    nothing but errors (the missing `GetWorkloadAccessToken` grant; see `configure_gateway.py`).

    So the check has to reach one level past the protocol: a JSON-RPC error and an MCP *tool* error
    are
    different failures, and only the first is visible in the envelope.
    """
    if isinstance(response.get("error"), dict) or response.get("http_error") is not None:
        return False
    return not (response.get("result") or {}).get("isError")


def payload(response: dict) -> dict:
    """The tool's own `{cards, facts, ...}` out of the MCP envelope."""
    content = (response.get("result") or {}).get("content") or []
    for block in content:
        text = block.get("text")
        if not text:
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            continue
    return {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--password",
        help="shared demo password; read from Parameter Store when omitted",
    )
    args = parser.parse_args()

    # Read rather than required, so a credential need not travel through shell history.
    password = args.password or refs.demo_password
    globex = token_for("priya", password)
    initech = token_for("sam", password)
    results: list[bool] = []

    print("\n1. Every advertised tool answers through the gateway")
    schemas = list_tools(globex)
    print(f"     {len(schemas)} tool(s) advertised: {', '.join(sorted(schemas))}")

    # One representative call per tool. Arguments are minimal-but-valid; the point is that the whole
    # path works, not that every branch does — the per-family smoke tests cover branches.
    calls: dict[str, dict] = {
        "policy___get_travel_policy": {"topic": "hotel"},
        "policy___check_policy_eligibility": {
            "check": "hotel",
            "nightly_rate_amount": 240,
            "star_rating": 4,
        },
        "profile___get_traveler_profile": {},
        "knowledge___search_policy_knowledge": {"question": "can I expense breakfast?"},
        "trips___get_trips": {},
        "search___search_flights": {
            "origin": "Atlanta",
            "destination": CITY,
            "depart_on": DEPART,
        },
        "search___search_hotels": {
            "destination": CITY,
            "check_in": CHECK_IN,
            "check_out": CHECK_OUT,
        },
        "entry___check_entry_requirements": {"destination_country": "IN"},
        "location___find_nearby": {
            "near": "Trafalgar Square, London",
            "what": "coffee",
            "limit": 2,
        },
        "location___get_route": {
            "origin": "Heathrow Airport, London",
            "destination": "Trafalgar Square, London",
        },
        "escalation___escalate_to_human": {"reason": "needs a policy exception"},
    }

    unreachable = []
    for name in sorted(schemas):
        if name not in calls:
            # The write tools are exercised by the lifecycle check below rather than in isolation,
            # because a bare `prepare_booking` needs an option id from a live search.
            continue
        if not ok_response(call_tool(globex, name, calls[name])):
            unreachable.append(name)
    results.append(
        report(
            "every read tool answers through the real gateway",
            not unreachable,
            f"unreachable: {unreachable}"
            if unreachable
            else f"{len(calls)} tool(s) exercised through the interceptor, Cedar and registration",
        )
    )

    print("\n2. No tool advertises a tenant field")
    leaked = [
        f"{tool}.{arg}"
        for tool, arguments in schemas.items()
        for arg in arguments
        if "tenant" in arg.lower()
    ]
    results.append(
        report(
            "no tenant argument in any advertised schema",
            not leaked and bool(schemas),
            f"FOUND: {leaked}"
            if leaked
            else f"checked {len(schemas)} schema(s); identity arrives in the Lambda client "
            "context, a channel the model cannot reach",
        )
    )

    print("\n3. A complete booking: search → eligibility → prepare → confirm → cancel")
    hotels = payload(
        call_tool(
            globex,
            "search___search_hotels",
            {
                "destination": CITY,
                "check_in": CHECK_IN,
                "check_out": CHECK_OUT,
            },
        )
    )
    option_id = (hotels.get("cards") or [{}])[0].get("id")
    results.append(report("search returned a selectable option", bool(option_id), f"{option_id}"))

    prepared = payload(
        call_tool(
            globex,
            "booking___prepare_booking",
            {
                "option_id": option_id,
                "kind": "hotel",
                "destination": CITY,
                "check_in": CHECK_IN,
                "check_out": CHECK_OUT,
            },
        )
    )
    booking_ref = (prepared.get("facts") or {}).get("booking_ref")
    results.append(
        report(
            "prepare holds and prices it, booking nothing",
            bool(booking_ref) and (prepared.get("facts") or {}).get("booked") is not True,
            f"ref={booking_ref} total={(prepared.get('facts') or {}).get('total')}",
        )
    )

    confirmed = payload(
        call_tool(globex, "booking___confirm_booking", {"booking_ref": booking_ref})
    )
    c_facts = confirmed.get("facts") or {}
    results.append(
        report(
            "confirm books it and returns a confirmation number",
            c_facts.get("booked") is True and bool(c_facts.get("confirmation_number")),
            f"confirmation={c_facts.get('confirmation_number')}",
        )
    )

    ref = c_facts.get("booking_ref")
    terms = payload(call_tool(globex, "booking___cancel_reservation", {"booking_ref": ref}))
    t_stage = ((terms.get("cards") or [{}])[0].get("data") or {}).get("stage")
    results.append(
        report(
            "cancellation shows terms first and cancels nothing",
            t_stage == "terms_shown" and (terms.get("facts") or {}).get("cancelled") is False,
            f"stage={t_stage} — 'cancel my hotel' is not agreement to a penalty nobody has seen",
        )
    )

    cancelled = payload(
        call_tool(globex, "booking___cancel_reservation", {"booking_ref": ref, "confirm": True})
    )
    results.append(
        report(
            "the confirmed second call cancels it",
            (cancelled.get("facts") or {}).get("cancelled") is True,
            f"stage={((cancelled.get('cards') or [{}])[0].get('data') or {}).get('stage')}",
        )
    )

    print("\n4. The tenant changes the answer — three different ways")
    g_hotels = (
        payload(
            call_tool(
                globex,
                "search___search_hotels",
                {
                    "destination": CITY,
                    "check_in": CHECK_IN,
                    "check_out": CHECK_OUT,
                },
            )
        ).get("facts")
        or {}
    )
    i_hotels = (
        payload(
            call_tool(
                initech,
                "search___search_hotels",
                {
                    "destination": CITY,
                    "check_in": CHECK_IN,
                    "check_out": CHECK_OUT,
                },
            )
        ).get("facts")
        or {}
    )
    results.append(
        report(
            "cap and currency: the same search judged against each tenant's own policy",
            (g_hotels.get("policy_cap") or {}).get("currency")
            != (i_hotels.get("policy_cap") or {}).get("currency"),
            f"globex {g_hotels.get('in_policy_options')}/{g_hotels.get('total_options')} "
            f"in policy, cap {g_hotels.get('policy_cap')}\n"
            f"initech {i_hotels.get('in_policy_options')}/{i_hotels.get('total_options')} "
            f"in policy, cap {i_hotels.get('policy_cap')}",
        )
    )

    g_cabin = (
        payload(
            call_tool(
                globex,
                "policy___check_policy_eligibility",
                {
                    "check": "air",
                    "cabin": "business",
                    "flight_hours": 13.3,
                },
            )
        ).get("facts")
        or {}
    )
    i_cabin = (
        payload(
            call_tool(
                initech,
                "policy___check_policy_eligibility",
                {
                    "check": "air",
                    "cabin": "business",
                    "flight_hours": 13.3,
                },
            )
        ).get("facts")
        or {}
    )
    results.append(
        report(
            "reasoning: the same question refused for different reasons",
            g_cabin.get("reason_code") != i_cabin.get("reason_code"),
            f"globex: {g_cabin.get('reason_code')} — {g_cabin.get('computation')}\n"
            f"initech: {i_cabin.get('reason_code')} — {i_cabin.get('computation')}",
        )
    )

    i_option = (
        payload(
            call_tool(
                initech,
                "search___search_hotels",
                {
                    "destination": CITY,
                    "check_in": CHECK_IN,
                    "check_out": CHECK_OUT,
                },
            )
        ).get("cards")
        or [{}]
    )[0].get("id")
    i_prepared = payload(
        call_tool(
            initech,
            "booking___prepare_booking",
            {
                "option_id": i_option,
                "kind": "hotel",
                "destination": CITY,
                "check_in": CHECK_IN,
                "check_out": CHECK_OUT,
            },
        )
    )
    i_card = (i_prepared.get("cards") or [{}])[0]
    i_actions = {a["id"] for a in i_card.get("actions") or []}
    g_card = (prepared.get("cards") or [{}])[0]
    g_actions = {a["id"] for a in g_card.get("actions") or []}
    results.append(
        report(
            "capability: confirm is offered to one tenant and absent for the other",
            "confirm_booking" in g_actions and not i_actions,
            f"globex actions: {sorted(g_actions)}\n"
            f"initech actions: {sorted(i_actions) or 'none'} "
            f"(checkout link: {bool((i_card.get('data') or {}).get('checkout_url'))})\n"
            "Not a config difference — a different set of things the agent may do.",
        )
    )

    refused = payload(
        call_tool(
            initech,
            "booking___confirm_booking",
            {
                "booking_ref": (i_prepared.get("facts") or {}).get("booking_ref"),
            },
        )
    )
    results.append(
        report(
            "and the handoff tenant's confirm is refused at the tool, not just hidden in the UI",
            (refused.get("facts") or {}).get("booked") is not True,
            (refused.get("message") or "")[:130],
        )
    )

    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
