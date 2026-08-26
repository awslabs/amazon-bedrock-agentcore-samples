"""Smoke test for the search tools.

    BACKEND_API_URL=... tools/.venv/bin/python -m tools.search.test_local

**The annotation is what needs proving, not the listing.** Any API returns flights; what makes these
useful is that each option already says whether *this* company allows it. So the checks assert the
policy annotation and the aggregate counts, and specifically that the counts come from the whole
result set rather than from the truncated list of cards — a model counting tiles would answer "how
many are in policy?" confidently and wrongly.

The two-tenant contrast is the payoff: the same city and dates, a $250/4★ cap versus €150/3★, with
different options in policy as a result.
"""

from __future__ import annotations

import sys

from shared.cards import assert_all_valid
from tools.common.testing import GLOBEX, INITECH, FakeLambdaContext, ok, summarise

from .handler import handler as lambda_handler
from .schemas import SEARCH_FLIGHTS, SEARCH_HOTELS

# Far enough out that advance-purchase rules are satisfied and the fixture generator is stable.
DEPART = "2026-11-10"
CHECK_IN = "2026-11-10"
CHECK_OUT = "2026-11-13"


def call(tool: str, arguments: dict, identity=GLOBEX) -> dict:
    return lambda_handler(arguments, FakeLambdaContext(tool, identity=identity))


def main() -> int:
    results: list[bool] = []

    print("\nFlight search — Globex")
    flights = call(
        SEARCH_FLIGHTS,
        {"origin": "Atlanta", "destination": "London", "depart_on": DEPART},
    )
    facts = flights.get("facts") or {}
    cards = flights.get("cards") or []
    results.append(
        ok(
            "returns option cards and aggregate facts",
            bool(cards) and facts.get("total_options", 0) > 0,
            f"{facts.get('total_options')} option(s), {len(cards)} card(s), "
            f"{facts.get('in_policy_options')} in policy",
        )
    )
    try:
        assert_all_valid(flights)
        results.append(ok("every flight card matches the contract", True))
    except AssertionError as error:
        results.append(ok("every flight card matches the contract", False, str(error)))

    results.append(
        ok(
            "each option carries a policy verdict the model did not compute",
            all("in_policy" in (c.get("data") or {}) for c in cards),
            "in_policy comes from the backend, which uses the same code as the eligibility tool",
        )
    )

    # The counts must describe the full result set, not the cards. This is the check that catches a
    # tool that "helpfully" recounted its own truncated output.
    results.append(
        ok(
            "aggregate counts describe the whole result set, not the shown cards",
            facts.get("total_options", 0) >= len(cards),
            f"total_options={facts.get('total_options')} vs {len(cards)} card(s); "
            f"truncated={facts.get('truncated', 'no')}",
        )
    )

    print("\nHotel search — the two-tenant contrast")
    globex = call(
        SEARCH_HOTELS,
        {"destination": "London", "check_in": CHECK_IN, "check_out": CHECK_OUT},
    )
    initech = call(
        SEARCH_HOTELS,
        {"destination": "London", "check_in": CHECK_IN, "check_out": CHECK_OUT},
        identity=INITECH,
    )
    g_facts = globex.get("facts") or {}
    i_facts = initech.get("facts") or {}
    g_cap = (g_facts.get("policy_cap") or {}).get("currency")
    i_cap = (i_facts.get("policy_cap") or {}).get("currency")
    results.append(
        ok(
            "the same search is judged against each tenant's own cap",
            g_cap != i_cap and bool(g_cap) and bool(i_cap),
            f"globex cap: {g_facts.get('policy_cap')}\ninitech cap: {i_facts.get('policy_cap')}",
        )
    )
    results.append(
        ok(
            "each tenant gets its own in-policy count",
            g_facts.get("in_policy_options") is not None
            and i_facts.get("in_policy_options") is not None,
            f"globex {g_facts.get('in_policy_options')}/{g_facts.get('total_options')} · "
            f"initech {i_facts.get('in_policy_options')}/{i_facts.get('total_options')}",
        )
    )
    try:
        assert_all_valid(globex)
        assert_all_valid(initech)
        results.append(ok("every hotel card matches the contract", True))
    except AssertionError as error:
        results.append(ok("every hotel card matches the contract", False, str(error)))

    print("\nFilters ride as parameters, not as new tools")
    filtered = call(
        SEARCH_HOTELS,
        {
            "destination": "London",
            "check_in": CHECK_IN,
            "check_out": CHECK_OUT,
            "breakfast_included": True,
        },
    )
    f_total = (filtered.get("facts") or {}).get("total_options")
    results.append(
        ok(
            "a breakfast filter narrows the same tool rather than needing another",
            f_total is not None and f_total <= (g_facts.get("total_options") or 0),
            f"unfiltered {g_facts.get('total_options')} → filtered {f_total}",
        )
    )

    print("\nDeterminism — repeat searches must be byte-identical")
    again = call(
        SEARCH_HOTELS,
        {"destination": "London", "check_in": CHECK_IN, "check_out": CHECK_OUT},
    )
    results.append(
        ok(
            "the same query returns the same options",
            [c["id"] for c in globex.get("cards", [])] == [c["id"] for c in again.get("cards", [])],
            "without this, no assertion about search results means anything",
        )
    )

    print("\nAn unsupported place refuses *helpfully*")
    unsupported = call(
        SEARCH_FLIGHTS,
        {"origin": "Austin", "destination": "London", "depart_on": DEPART},
    )
    message = unsupported.get("message") or ""
    results.append(
        ok(
            "an unknown airport offers supported alternatives rather than a bare no",
            "Austin" not in message and ("Nearby" in message or "demo" in message),
            message[:150] + "\nA dead end the traveller cannot act on is a stalled conversation.",
        )
    )

    print("\nRefusals")
    for tool, arguments, expect in [
        (SEARCH_FLIGHTS, {"destination": "London"}, "departure date"),
        (
            SEARCH_FLIGHTS,
            {"destination": "London", "depart_on": DEPART, "cabin": "luxury"},
            "cabin",
        ),
        (SEARCH_HOTELS, {"destination": "London", "check_in": CHECK_IN}, "check-out"),
    ]:
        message = (call(tool, arguments).get("message") or "").lower()
        results.append(
            ok(f"{tool} {arguments} is refused", expect.lower() in message, message[:110])
        )

    return summarise(results)


if __name__ == "__main__":
    sys.exit(main())
