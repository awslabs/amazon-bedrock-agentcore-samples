"""Smoke test for the write path.

    BACKEND_API_URL=... tools/.venv/bin/python -m tools.booking.test_local

**The refusals matter more than the happy path here**, because these are the only tools where an
error is unrecoverable. A booking that succeeds when it should have refused cannot be undone by
apologising.

So the checks are, in order of what they protect:

- **Nothing is booked without a separate confirm call.** prepare holds and prices; that is all.
- **A `handoff` tenant cannot confirm at all** — no confirm action on the card, and the tool refuses
  even if asked directly. This is the two-tenant contrast, expressed as capability rather than copy.
- **A stale or reused hold refuses**, rather than re-searching and booking something else.
- **Cancellation shows terms first** and cancels nothing on the first call.
"""

from __future__ import annotations

import sys

from shared.cards import assert_all_valid
from tools.common.testing import GLOBEX, INITECH, FakeLambdaContext, ok, summarise

from .handler import handler as lambda_handler
from .schemas import CANCEL_RESERVATION, CONFIRM_BOOKING, PREPARE_BOOKING

# A search the fixtures support, far enough out to satisfy advance-purchase rules.
CITY = "London"
CHECK_IN = "2026-11-10"
CHECK_OUT = "2026-11-13"


def call(tool: str, arguments: dict, identity=GLOBEX) -> dict:
    return lambda_handler(arguments, FakeLambdaContext(tool, identity=identity))


def first_hotel_option(identity=GLOBEX) -> str | None:
    """An option id from a real search — never invented, which is the contract."""
    from tools.search.handler import handler as search_handler
    from tools.search.schemas import SEARCH_HOTELS

    response = search_handler(
        {"destination": CITY, "check_in": CHECK_IN, "check_out": CHECK_OUT},
        FakeLambdaContext(SEARCH_HOTELS, identity=identity),
    )
    cards = response.get("cards") or []
    return cards[0]["id"] if cards else None


def main() -> int:
    results: list[bool] = []

    print("\nprepare_booking — holds and prices, books nothing")
    option_id = first_hotel_option()
    results.append(ok("got an option id from a real search", bool(option_id), f"{option_id}"))
    if not option_id:
        return summarise(results)

    prepared = call(
        PREPARE_BOOKING,
        {
            "option_id": option_id,
            "kind": "hotel",
            "destination": CITY,
            "check_in": CHECK_IN,
            "check_out": CHECK_OUT,
        },
    )
    facts = prepared.get("facts") or {}
    booking_ref = facts.get("booking_ref")
    results.append(
        ok(
            "returns a summary with a booking reference and total",
            bool(booking_ref) and bool(facts.get("total")),
            f"ref={booking_ref} total={facts.get('total')} mode={facts.get('booking_mode')}",
        )
    )
    try:
        assert_all_valid(prepared)
        results.append(ok("the summary card matches the contract", True))
    except AssertionError as error:
        results.append(ok("the summary card matches the contract", False, str(error)))

    summary_card = (prepared.get("cards") or [{}])[0]
    action_ids = {a["id"] for a in summary_card.get("actions") or []}
    results.append(
        ok(
            "a confirm_in_chat tenant gets confirm and decline actions",
            action_ids == {"confirm_booking", "decline_booking"},
            f"actions: {sorted(action_ids)}",
        )
    )
    results.append(
        ok(
            "no card digits reach the payment label",
            not any(ch.isdigit() for ch in summary_card["data"].get("payment_label", "")),
            f"payment_label: {summary_card['data'].get('payment_label')!r}",
        )
    )

    # **A malformed id whose digest cannot match these dates.** After the digest check was added
    # this
    # is a *mismatch* rather than an absence — the id encodes one query and the parameters describe
    # another. Both must refuse; the distinction is which one the caller is told about, because
    # "no longer available" sends an agent searching again while a mismatch means it should not.
    mismatched = call(
        PREPARE_BOOKING,
        {
            "option_id": "stale_option",
            "kind": "hotel",
            "destination": CITY,
            "check_in": CHECK_IN,
            "check_out": CHECK_OUT,
        },
    )
    message = (mismatched.get("message") or "").lower()
    results.append(
        ok(
            "an option id that cannot belong to these dates refuses, without holding anything",
            "mixed up the details" in message and not mismatched.get("cards"),
            (mismatched.get("message") or "")[:130]
            + "\nSilently re-searching could hold a different hotel at a different price.",
        )
    )

    # The paired case: a *well-formed* id for this exact query whose index does not exist. Genuinely
    # absent, so the caller is told to search again — and the two messages must stay
    # distinguishable,
    # or the agent cannot tell "my mistake" from "that room is gone".
    absent = call(
        PREPARE_BOOKING,
        {
            "option_id": f"{option_id.rsplit('_', 1)[0]}_999",
            "kind": "hotel",
            "destination": CITY,
            "check_in": CHECK_IN,
            "check_out": CHECK_OUT,
        },
    )
    absent_message = (absent.get("message") or "").lower()
    results.append(
        ok(
            "a genuinely absent option is reported as no longer available, not as a mix-up",
            "no longer available" in absent_message and not absent.get("cards"),
            (absent.get("message") or "")[:130],
        )
    )

    print("\nThe two-tenant contrast — a handoff tenant cannot transact")
    initech_option = first_hotel_option(identity=INITECH)
    initech_prepared = call(
        PREPARE_BOOKING,
        {
            "option_id": initech_option,
            "kind": "hotel",
            "destination": CITY,
            "check_in": CHECK_IN,
            "check_out": CHECK_OUT,
        },
        identity=INITECH,
    )
    i_card = (initech_prepared.get("cards") or [{}])[0]
    i_actions = {a["id"] for a in i_card.get("actions") or []}
    results.append(
        ok(
            "a handoff tenant's card carries NO confirm action",
            not i_actions and bool(i_card.get("data", {}).get("checkout_url")),
            f"actions: {sorted(i_actions) or 'none'}; "
            f"checkout_url present: {bool(i_card.get('data', {}).get('checkout_url'))}",
        )
    )
    i_ref = (initech_prepared.get("facts") or {}).get("booking_ref")
    refused = call(CONFIRM_BOOKING, {"booking_ref": i_ref}, identity=INITECH)
    results.append(
        ok(
            "and confirm_booking refuses even when called directly",
            (refused.get("facts") or {}).get("booked") is not True
            and "checkout" in (refused.get("message") or "").lower(),
            (refused.get("message") or "")[:130]
            + "\nRefused at the tool, not merely discouraged in the prompt.",
        )
    )

    print("\nconfirm_booking — the happy path, then the same hold reused")
    confirmed = call(CONFIRM_BOOKING, {"booking_ref": booking_ref})
    c_facts = confirmed.get("facts") or {}
    results.append(
        ok(
            "confirming a valid hold books it",
            c_facts.get("booked") is True and bool(c_facts.get("confirmation_number")),
            f"confirmation: {c_facts.get('confirmation_number')}",
        )
    )
    try:
        assert_all_valid(confirmed)
        results.append(ok("the confirmation card matches the contract", True))
    except AssertionError as error:
        results.append(ok("the confirmation card matches the contract", False, str(error)))

    again = call(CONFIRM_BOOKING, {"booking_ref": booking_ref})
    results.append(
        ok(
            "reusing a consumed hold refuses rather than double-booking",
            (again.get("facts") or {}).get("booked") is not True,
            (again.get("message") or "")[:130],
        )
    )

    invented = call(CONFIRM_BOOKING, {"booking_ref": "offer_does_not_exist"})
    results.append(
        ok(
            "an invented booking reference refuses",
            (invented.get("facts") or {}).get("booked") is not True,
            (invented.get("message") or "")[:130],
        )
    )

    print("\ncancel_reservation — terms first, and only then the cancellation")
    ref = c_facts.get("booking_ref")
    terms = call(CANCEL_RESERVATION, {"booking_ref": ref})
    t_facts = terms.get("facts") or {}
    t_card = (terms.get("cards") or [{}])[0]
    results.append(
        ok(
            "the first call shows terms and cancels NOTHING",
            t_facts.get("cancelled") is False
            and t_card.get("data", {}).get("stage") == "terms_shown",
            f"stage={t_card.get('data', {}).get('stage')} cancelled={t_facts.get('cancelled')}\n"
            "'Cancel my hotel' is not agreement to a penalty nobody has been shown.",
        )
    )
    try:
        assert_all_valid(terms)
        results.append(ok("the terms card matches the contract", True))
    except AssertionError as error:
        results.append(ok("the terms card matches the contract", False, str(error)))

    done = call(CANCEL_RESERVATION, {"booking_ref": ref, "confirm": True})
    d_card = (done.get("cards") or [{}])[0]
    results.append(
        ok(
            "the confirmed call cancels it",
            (done.get("facts") or {}).get("cancelled") is True
            and d_card.get("data", {}).get("stage") == "cancelled",
            f"stage={d_card.get('data', {}).get('stage')}",
        )
    )

    print("\nRefusals on bad input")
    for tool, arguments, expect in [
        (PREPARE_BOOKING, {"kind": "hotel", "destination": CITY}, "id of the option"),
        (PREPARE_BOOKING, {"option_id": "x", "kind": "car", "destination": CITY}, "air, hotel"),
        (CONFIRM_BOOKING, {}, "booking reference"),
        (CANCEL_RESERVATION, {}, "booking reference"),
    ]:
        message = (call(tool, arguments).get("message") or "").lower()
        results.append(ok(f"{tool} {arguments} refuses", expect.lower() in message, message[:110]))

    return summarise(results)


if __name__ == "__main__":
    sys.exit(main())
