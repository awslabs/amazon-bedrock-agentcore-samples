"""Smoke test for `check_policy_eligibility`.

    BACKEND_API_URL=... tools/.venv/bin/python -m tools.policy.test_eligibility

**What actually needs proving here** is not "it returns a verdict" — it is that the verdict is
*decided* and its arithmetic is visible. So every check asserts on `computation` as well as
`eligible`: a verdict without shown arithmetic is one the user has to take on trust, and one the
model may be tempted to re-derive.

The two-tenant contrast is the interesting part: Globex grants business on every 4th international
trip (an entitlement that can be *earned*), Initech grants none. Same question, two different
correct answers, and the reason differs too — not just the boolean.
"""

from __future__ import annotations

import sys

from shared.cards import assert_all_valid
from tools.common.testing import GLOBEX, INITECH, FakeLambdaContext, ok, summarise

from .handler import handler as lambda_handler
from .schemas import CHECK_POLICY_ELIGIBILITY


def call(arguments: dict, identity=GLOBEX) -> dict:
    return lambda_handler(arguments, FakeLambdaContext(CHECK_POLICY_ELIGIBILITY, identity=identity))


def main() -> int:
    results: list[bool] = []

    print("\nGlobex — business cabin, trip-count entitlement")
    response = call({"check": "air", "cabin": "business", "flight_hours": 13.3})
    facts = response.get("facts") or {}
    results.append(
        ok(
            "returns a decided verdict with the arithmetic shown",
            facts.get("eligible") is not None and bool(facts.get("computation")),
            f"eligible={facts.get('eligible')} reason={facts.get('reason_code')}\n"
            f"computation: {facts.get('computation')}",
        )
    )
    try:
        assert_all_valid(response)
        results.append(ok("the verdict card matches the contract", True))
    except AssertionError as error:
        results.append(ok("the verdict card matches the contract", False, str(error)))

    results.append(
        ok(
            "a not-yet-earned entitlement says how many trips remain",
            facts.get("eligible") is True or facts.get("trips_until_entitled") is not None,
            f"trips_until_entitled={facts.get('trips_until_entitled')} — a refusal that "
            "explains itself is actionable",
        )
    )

    print("\nAsking about a real trip excludes that trip from its own history")
    # Priya has 3 past international trips plus one upcoming. Asking about the upcoming one must
    # count 3 prior — making it the 4th, which *is* entitled. Counting it as its own history would
    # make it the 5th and wrongly refuse: exactly the off-by-one this design exists to prevent.
    by_trip = call({"check": "air", "cabin": "business", "trip_id": "trip_priya_next"})
    by_trip_facts = by_trip.get("facts") or {}
    results.append(
        ok(
            "the trip under question is not counted as its own prior history",
            by_trip_facts.get("eligible") is True,
            f"eligible={by_trip_facts.get('eligible')}\n"
            f"computation: {by_trip_facts.get('computation')}",
        )
    )

    print("\nGlobex — hotel against the cap")
    within = (
        call({"check": "hotel", "nightly_rate_amount": 240, "star_rating": 4}).get("facts") or {}
    )
    over = call({"check": "hotel", "nightly_rate_amount": 400, "star_rating": 5}).get("facts") or {}
    results.append(
        ok(
            "within the cap is eligible, over it is not",
            within.get("eligible") is True and over.get("eligible") is False,
            f"240/4★: {within.get('computation')}\n400/5★: {over.get('computation')}",
        )
    )
    results.append(
        ok(
            "currency defaults to the caller's own policy currency",
            "USD" in (within.get("computation") or ""),
            "the model is never asked to guess a currency",
        )
    )

    print("\nInitech — the same question, a different rule")
    initech = (
        call({"check": "air", "cabin": "business", "flight_hours": 13.3}, identity=INITECH).get(
            "facts"
        )
        or {}
    )
    results.append(
        ok(
            "the second tenant gets a different verdict for a different reason",
            initech.get("eligible") is False
            and initech.get("reason_code") != facts.get("reason_code"),
            f"globex: {facts.get('reason_code')} / initech: {initech.get('reason_code')}\n"
            f"initech rule: {initech.get('rule_quote')}",
        )
    )

    print("\nRefuses an incomplete question rather than assuming a value")
    for arguments, expect in [
        ({"check": "air", "cabin": "business"}, "flight length"),
        ({"check": "hotel"}, "nightly rate"),
        ({"check": "air", "flight_hours": 4}, "cabin"),
        ({"check": "nonsense"}, "can check"),
    ]:
        message = (call(arguments).get("message") or "").lower()
        results.append(
            ok(
                f"{arguments} is refused",
                expect.lower() in message,
                message[:110],
            )
        )

    return summarise(results)


if __name__ == "__main__":
    sys.exit(main())
