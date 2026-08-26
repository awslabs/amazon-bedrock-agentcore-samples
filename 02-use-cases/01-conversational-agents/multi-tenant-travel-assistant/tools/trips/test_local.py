"""Standalone smoke test for the trips tool.

    BACKEND_API_URL=... tools/.venv/bin/python -m tools.trips.test_local

Runs against the **deployed backend** with no Gateway, no Runtime and no model in the loop, which is
the point: if the answers are right here, any later failure is in the identity chain rather than in
the tool.

Beyond "does it return trips", three things are worth asserting because each fails silently:

- **Cards match the contract.** A missing required key renders as a blank line in a tile; nobody
  notices until a demo.
- **Hotel addresses survive.** This tool is the context resolver — `find_nearby` geocodes the
  address it emits, so losing it here degrades a *different* tool in a way that looks like a
  geocoding bug.
- **Arranger scope.** Adaeze may act for Priya and must not reach Initech's Sam.
"""

from __future__ import annotations

import sys

from shared.cards import assert_all_valid
from tools.common.testing import GLOBEX, GLOBEX_ARRANGER, INITECH, FakeLambdaContext, ok, summarise

from .handler import handler as lambda_handler
from .schemas import GET_TRIPS


def call(arguments: dict, identity=GLOBEX) -> dict:
    return lambda_handler(arguments, FakeLambdaContext(GET_TRIPS, identity=identity))


def main() -> int:
    results: list[bool] = []

    print("\nPriya's own trips")
    response = call({})
    facts = response.get("facts") or {}
    cards = response.get("cards") or []
    results.append(
        ok(
            "returns trips with cards and facts",
            bool(cards) and facts.get("trip_count", 0) > 0,
            f"{facts.get('trip_count')} trip(s), {len(cards)} card(s)",
        )
    )

    try:
        assert_all_valid(response)
        results.append(ok("every card matches the contract", True))
    except AssertionError as error:
        results.append(ok("every card matches the contract", False, str(error)))

    # The handoff the location tools depend on. Asserted here rather than discovered later as a
    # geocoding failure two tools away.
    addresses = [
        stay.get("location", {}).get("address")
        for trip in facts.get("trips", [])
        for stay in trip.get("hotels", [])
    ]
    results.append(
        ok(
            "hotel stays carry a full address for the location tools",
            any(addresses),
            f"addresses: {[a for a in addresses if a][:2]}",
        )
    )

    print("\nWindow filter")
    in_progress = call({"window": "in_progress"})
    statuses = {t.get("status") for t in (in_progress.get("facts") or {}).get("trips", [])}
    results.append(
        ok(
            "in_progress returns only in-progress trips",
            statuses <= {"in_progress"},
            f"statuses seen: {statuses or 'none'}",
        )
    )

    unknown = call({"window": "current"})
    results.append(
        ok(
            "an unrecognised window is refused, not silently ignored",
            "current" in (unknown.get("message") or ""),
            unknown.get("message", "")[:120],
        )
    )

    print("\nArranger scope")
    for_priya = call({"traveler_name": "Priya"}, identity=GLOBEX_ARRANGER)
    results.append(
        ok(
            "an arranger may list a traveller they can book for",
            bool(for_priya.get("cards")),
            f"{(for_priya.get('facts') or {}).get('trip_count')} trip(s)",
        )
    )

    cross = call({"traveler_name": "Sam Whitfield"}, identity=GLOBEX_ARRANGER)
    leaked = bool(cross.get("cards"))
    results.append(
        ok(
            "another tenant's traveller is not reachable by name",
            not leaked,
            (cross.get("message") or "")[:140],
        )
    )

    plain = call({"traveler_name": "Adaeze"}, identity=GLOBEX)
    results.append(
        ok(
            "a plain traveller cannot list someone else's trips",
            not plain.get("cards"),
            (plain.get("message") or "")[:140],
        )
    )

    print("\nSecond tenant")
    initech = call({}, identity=INITECH)
    initech_facts = initech.get("facts") or {}
    results.append(
        ok(
            "Initech's traveller sees their own trips",
            initech_facts.get("trip_count", 0) > 0,
            f"{initech_facts.get('trip_count')} trip(s)",
        )
    )

    return summarise(results)


if __name__ == "__main__":
    sys.exit(main())
