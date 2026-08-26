"""Smoke test for `check_entry_requirements`.

    BACKEND_API_URL=... tools/.venv/bin/python -m tools.entry.test_local

**The check that matters most is the absent one.** A visa-required answer being right is table
stakes; "no rules on file" being narrated as *unknown* rather than as *unrestricted* is the
difference between an inconvenience and a traveller turned away at a border.
"""

from __future__ import annotations

import sys

from shared.cards import assert_all_valid
from tools.common.testing import GLOBEX, FakeLambdaContext, ok, summarise

from .handler import handler as lambda_handler
from .schemas import CHECK_ENTRY_REQUIREMENTS


def call(arguments: dict, identity=GLOBEX) -> dict:
    return lambda_handler(arguments, FakeLambdaContext(CHECK_ENTRY_REQUIREMENTS, identity=identity))


def main() -> int:
    results: list[bool] = []

    print("\nA pair that needs a visa or authorisation")
    evisa = call({"destination_country": "IN"})
    facts = evisa.get("facts") or {}
    results.append(
        ok(
            "returns the requirement with a plain-language meaning",
            facts.get("requirement") in ("visa", "evisa") and bool(facts.get("meaning")),
            f"{facts.get('requirement')}: {facts.get('meaning')}",
        )
    )
    try:
        assert_all_valid(evisa)
        results.append(ok("the card matches the contract", True))
    except AssertionError as error:
        results.append(ok("the card matches the contract", False, str(error)))

    card_data = (evisa.get("cards") or [{}])[0].get("data") or {}
    results.append(
        ok(
            "the disclaimer is on the card, not only in facts",
            bool(card_data.get("disclaimer")),
            f"{card_data.get('disclaimer')}\nThe tile is what a user screenshots.",
        )
    )
    results.append(
        ok(
            "the passport country comes from the profile, not from arguments",
            bool(card_data.get("passport_country")),
            f"passport_country={card_data.get('passport_country')} — never a model input",
        )
    )

    print("\nA visa-free pair")
    free = call({"destination_country": "GB"}).get("facts") or {}
    results.append(
        ok(
            "a visa-free pair says so explicitly",
            free.get("requirement") == "none",
            f"{free.get('requirement')}: {free.get('meaning')}",
        )
    )

    print("\nNo rules on file — the check that protects a traveller")
    unknown = call({"destination_country": "ZZ"})
    u_facts = unknown.get("facts") or {}
    message = (unknown.get("message") or "").lower()
    results.append(
        ok(
            "absence is reported as unknown, never as 'no visa needed'",
            u_facts.get("requirement") == "unknown" and "don't know" in message,
            f"{message[:150]}",
        )
    )
    results.append(
        ok(
            "and no card is rendered, because there is no answer to render",
            not unknown.get("cards"),
            "a tile would read as an answer",
        )
    )

    print("\nRefusals")
    name = call({"destination_country": "India"})
    results.append(
        ok(
            "a country name is refused rather than silently missing the lookup",
            "two-letter" in (name.get("message") or "").lower(),
            (name.get("message") or "")[:120],
        )
    )
    empty = call({})
    results.append(
        ok(
            "a missing destination is refused",
            "destination" in (empty.get("message") or "").lower(),
            (empty.get("message") or "")[:120],
        )
    )

    return summarise(results)


if __name__ == "__main__":
    sys.exit(main())
