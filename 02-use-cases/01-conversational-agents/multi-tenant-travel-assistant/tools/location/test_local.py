"""Smoke test for the location tools — live against Amazon Location Service.

    AWS_REGION=us-east-1 tools/.venv/bin/python -m tools.location.test_local

**Live rather than mocked, deliberately.** Every bug worth catching here is a provider-shape bug: a
travel mode whose response nests its totals differently, a category that resolves to the wrong kind
of business, a place name that geocodes to another continent. A mock encodes the shape we *believe*
and would have passed while walking routes crashed.
"""

from __future__ import annotations

import sys

from shared.cards import assert_all_valid
from tools.common.testing import GLOBEX, FakeLambdaContext, ok, summarise

from .handler import handler as lambda_handler
from .schemas import FIND_NEARBY, GET_ROUTE

# Real, unambiguous places, so a failure means the tool rather than the fixture.
ANCHOR = "Trafalgar Square, London"
NEARBY_TARGET = "Covent Garden, London"
AIRPORT = "Heathrow Airport, London"


def call(tool: str, arguments: dict) -> dict:
    return lambda_handler(arguments, FakeLambdaContext(tool, identity=GLOBEX))


def main() -> int:
    results: list[bool] = []

    print("\nfind_nearby — a known category takes the precise path")
    coffee = call(FIND_NEARBY, {"near": ANCHOR, "what": "coffee", "limit": 3})
    facts = coffee.get("facts") or {}
    results.append(
        ok(
            "returns nearby places with distances",
            (facts.get("count") or 0) > 0
            and all((c["data"].get("distance_m") or 0) >= 0 for c in coffee.get("cards") or []),
            f"{facts.get('count')} result(s) around {facts.get('searched_around')}",
        )
    )
    results.append(
        ok(
            "a known word resolves via an exact category, not free text",
            "category:" in ((coffee.get("provenance") or {}).get("resolved_via") or ""),
            f"resolved_via={(coffee.get('provenance') or {}).get('resolved_via')} — "
            "the tier is recorded so a surprising result can be explained",
        )
    )
    try:
        assert_all_valid(coffee)
        results.append(ok("every place card matches the contract", True))
    except AssertionError as error:
        results.append(ok("every place card matches the contract", False, str(error)))

    results.append(
        ok(
            "no coordinates reach the model",
            not any(
                k in (c.get("data") or {})
                for c in coffee.get("cards") or []
                for k in ("position", "latitude", "longitude")
            ),
            "coordinates are a provider detail and invite the model to do arithmetic on them",
        )
    )

    print("\nget_route — both travel modes, which nest their totals differently")
    car = (
        call(
            GET_ROUTE,
            {
                "origin": AIRPORT,
                "destination": ANCHOR,
                "departure_time": "2026-11-10T09:00:00Z",
            },
        ).get("facts")
        or {}
    )
    results.append(
        ok(
            "a car route is traffic-aware when a departure time is given",
            (car.get("duration_min") or 0) > 0 and car.get("traffic_aware") is True,
            f"{car.get('duration_min')} min, {car.get('distance_km')} km",
        )
    )

    walk = call(GET_ROUTE, {"origin": ANCHOR, "destination": NEARBY_TARGET, "mode": "walk"})
    w_facts = walk.get("facts") or {}
    results.append(
        ok(
            "a walking route works too — its totals live in the legs, not a top-level Summary",
            (w_facts.get("duration_min") or 0) > 0 and (w_facts.get("distance_km") or 0) > 0,
            f"{w_facts.get('duration_min')} min, {w_facts.get('distance_km')} km\n"
            "Reading route['Summary'] unconditionally crashed every pedestrian route.",
        )
    )
    try:
        assert_all_valid(walk)
        results.append(ok("the route card matches the contract", True))
    except AssertionError as error:
        results.append(ok("the route card matches the contract", False, str(error)))

    results.append(
        ok(
            "a free-flow estimate is labelled as such",
            w_facts.get("traffic_aware") is False,
            "so the model cannot present it as a rush-hour figure",
        )
    )

    print("\nFailure paths")
    unknown = call(FIND_NEARBY, {"near": "Zzqqxx Nonexistent Place 99", "what": "coffee"})
    results.append(
        ok(
            "an unlocatable place refuses and suggests using an address",
            "couldn't find" in (unknown.get("message") or "").lower(),
            (unknown.get("message") or "")[:120],
        )
    )
    bad_mode = call(GET_ROUTE, {"origin": ANCHOR, "destination": NEARBY_TARGET, "mode": "teleport"})
    results.append(
        ok(
            "an unknown travel mode is refused, not silently defaulted",
            "car, walk, truck" in (bad_mode.get("message") or ""),
            (bad_mode.get("message") or "")[:120],
        )
    )
    missing = call(FIND_NEARBY, {"near": ANCHOR})
    results.append(
        ok(
            "a missing 'what' is refused",
            "look for" in (missing.get("message") or "").lower(),
            (missing.get("message") or "")[:120],
        )
    )

    return summarise(results)


if __name__ == "__main__":
    sys.exit(main())
