"""Card and action contracts — **the one place a card shape is defined.**

Cards cross a language boundary: Python tools emit them, the TypeScript frontend renders one
component per `card_type`. So the definition cannot live inside either side. Two hand-maintained
copies would drift, and drift here means raw JSON leaking into the UI — a card the frontend does
not recognise renders as nothing, silently.

`generated/cards.ts` is **derived from this file** by `scripts/generate_card_types.py`. Never edit
it by hand.

**Why a card at all, rather than letting the model describe a hotel in prose?** Three reasons:

1. The model never authors UI, which is an XSS boundary as much as a design one.
2. A card carries *actions* — a click posts a structured event back as a user turn, so "select this
   flight" is an id the server re-validates, not a sentence the model re-interprets.
3. Cards are presentation, not the source of truth. Every tool also returns `facts` so model
   narration, verification, and future interfaces do not have to scrape meaning back out of a tile.

**Versioning:** a card change is a UI-contract change. Adding an optional field is safe; renaming
or removing one is not, and needs the frontend updated in the same change.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class CardType(StrEnum):
    """Every card the tools may emit. The frontend has one component per member."""

    FLIGHT_OPTION = "flight_option"
    HOTEL_OPTION = "hotel_option"
    TRIP = "trip"
    PROFILE = "profile"
    POLICY_VERDICT = "policy_verdict"
    BOOKING_SUMMARY = "booking_summary"
    BOOKING_CONFIRMED = "booking_confirmed"
    CANCELLATION = "cancellation"
    ENTRY_REQUIREMENTS = "entry_requirements"
    PLACE = "place"
    ROUTE = "route"
    ESCALATION = "escalation"
    CITATION = "citation"


class Action(StrEnum):
    """**A closed registry, and the closure is the point.**

    The frontend refuses to render an action it does not know, and the conversation API refuses to
    relay one. An open set would mean the model could invent `action_id: "transfer_funds"` and the
    UI would render a button for it — so the registry is a security boundary, not a convenience.
    """

    SELECT_FLIGHT = "select_flight"
    SELECT_HOTEL = "select_hotel"
    VIEW_DETAILS = "view_details"
    VIEW_FARE_RULES = "view_fare_rules"
    VIEW_TRIP = "view_trip"
    VIEW_TRAVEL_POLICY = "view_travel_policy"
    CONFIRM_BOOKING = "confirm_booking"
    DECLINE_BOOKING = "decline_booking"
    CONFIRM_CANCEL = "confirm_cancel"
    KEEP_BOOKING = "keep_booking"
    GET_DIRECTIONS = "get_directions"


# Required `data` keys per card type. Deliberately a *minimum*, not a closed schema: a card may
# carry optional extras (`policy_note`, `distance_note`) that the frontend renders when present.
#
# Checked in each tool's own test rather than at deploy time, because the failure this prevents is
# silent — a missing key renders as a blank line in a tile, which nobody notices until a demo.
REQUIRED_DATA: dict[CardType, frozenset[str]] = {
    CardType.FLIGHT_OPTION: frozenset(
        {
            "carrier",
            "flight_number",
            "depart_airport",
            "depart_time",
            "arrive_airport",
            "arrive_time",
            "duration_min",
            "stops",
            "cabin",
            "price",
            "in_policy",
        }
    ),
    CardType.HOTEL_OPTION: frozenset(
        {"name", "address", "star_rating", "nightly_rate", "total", "in_policy", "amenities"}
    ),
    CardType.TRIP: frozenset(
        {"trip_id", "status", "destination", "start_date", "end_date", "segments"}
    ),
    CardType.PROFILE: frozenset({"traveler_name", "home_airport", "loyalty", "passport_country"}),
    CardType.POLICY_VERDICT: frozenset({"request_label", "eligible", "rule_quote", "reason_code"}),
    CardType.BOOKING_SUMMARY: frozenset(
        {"items", "total", "payment_label", "policy_status", "mode"}
    ),
    CardType.BOOKING_CONFIRMED: frozenset({"confirmation_number", "items", "total", "issued_at"}),
    CardType.CANCELLATION: frozenset({"booking_label", "terms", "stage"}),
    CardType.ENTRY_REQUIREMENTS: frozenset(
        {"destination_country", "passport_country", "requirement", "disclaimer"}
    ),
    CardType.PLACE: frozenset({"name", "address", "distance_m", "categories"}),
    CardType.ROUTE: frozenset({"origin", "destination", "mode", "duration_min", "distance_km"}),
    CardType.ESCALATION: frozenset({"status", "reason_label", "context_summary_line"}),
    # `doc_id` is what the frontend presigns through `GET /documents/{doc_id}` — see
    # `conversation-api/app/documents.py`. Not a URL: this card is built at retrieval time, and a
    # link signed then would be a bearer token for a policy document with no ownership re-check.
    # `version` is optional (present when the source document declares one) and deliberately not
    # required here, since `REQUIRED_DATA` is a floor, not the full shape.
    CardType.CITATION: frozenset({"doc_id", "label"}),
}

# Which actions each card type may carry. A card offering an action outside this set is a bug:
# either the registry is stale or a tool is inventing UI.
#
# `booking_summary` is the interesting entry — its actions depend on the **tenant's booking mode**,
# so both possibilities are listed here and the *tool* decides. A handoff tenant's card carries no
# actions at all and renders a checkout link instead.
ALLOWED_ACTIONS: dict[CardType, frozenset[Action]] = {
    CardType.FLIGHT_OPTION: frozenset({Action.SELECT_FLIGHT, Action.VIEW_FARE_RULES}),
    CardType.HOTEL_OPTION: frozenset({Action.SELECT_HOTEL, Action.VIEW_DETAILS}),
    CardType.TRIP: frozenset({Action.VIEW_TRIP}),
    CardType.PROFILE: frozenset(),
    CardType.POLICY_VERDICT: frozenset({Action.VIEW_TRAVEL_POLICY}),
    CardType.BOOKING_SUMMARY: frozenset({Action.CONFIRM_BOOKING, Action.DECLINE_BOOKING}),
    CardType.BOOKING_CONFIRMED: frozenset(),
    CardType.CANCELLATION: frozenset({Action.CONFIRM_CANCEL, Action.KEEP_BOOKING}),
    CardType.ENTRY_REQUIREMENTS: frozenset(),
    CardType.PLACE: frozenset({Action.GET_DIRECTIONS}),
    CardType.ROUTE: frozenset(),
    CardType.ESCALATION: frozenset(),
    # No actions — same shape as the calendar download on `booking_confirmed`. Opening the document
    # means presigning through the caller's own session (`GET /documents/{doc_id}`), not asking the
    # agent to relay a click: there is no tool that could answer "open this document", and inventing
    # one would put a model call between a click and a link that is already one fetch away.
    CardType.CITATION: frozenset(),
}


class CardContractError(AssertionError):
    """A card does not match its contract. Raised in tests, never in a request path."""


def card(
    card_type: CardType,
    card_id: str,
    data: dict[str, Any],
    actions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build one card in the envelope the frontend expects.

    A constructor rather than a dict literal per tool, so the envelope's shape lives in one place —
    fourteen tools hand-assembling `{"card_type": …, "id": …}` is fourteen chances to typo a key
    that then renders as nothing.

    Deliberately **not validating** here: this runs on the conversational path, and a card that
    fails its contract should fail a *test*, not a user's request. `assert_valid` does the checking.
    """
    built: dict[str, Any] = {"card_type": str(card_type), "id": card_id, "data": data}
    if actions:
        built["actions"] = actions
    return built


def action(action_id: Action, label: str, **payload: Any) -> dict[str, Any]:
    """One action on a card. `payload` is what the server receives back on click."""
    return {"id": str(action_id), "label": label, "payload": payload}


def assert_valid(built: dict[str, Any]) -> None:
    """Check one card against its contract. **For tests.**

    Checks the three things that fail silently in a UI: an unknown `card_type` (renders as
    nothing), a missing required `data` key (renders as a blank line), and an action outside the
    closed registry (a button the frontend refuses, or worse, renders).
    """
    raw_type = built.get("card_type")
    try:
        card_type = CardType(raw_type)
    except ValueError:
        raise CardContractError(
            f"unknown card_type {raw_type!r} — the frontend renders this as nothing"
        ) from None

    if not built.get("id"):
        raise CardContractError(f"{raw_type}: no id, so the model cannot reference it")

    data = built.get("data") or {}
    missing = REQUIRED_DATA[card_type] - set(data)
    if missing:
        raise CardContractError(f"{raw_type}: missing required data keys {sorted(missing)}")

    allowed = ALLOWED_ACTIONS[card_type]
    for entry in built.get("actions") or []:
        try:
            used = Action(entry.get("id"))
        except ValueError:
            raise CardContractError(
                f"{raw_type}: action {entry.get('id')!r} is not in the closed registry"
            ) from None
        if used not in allowed:
            raise CardContractError(
                f"{raw_type}: action {used} is not allowed on this card type "
                f"(allowed: {sorted(str(a) for a in allowed)})"
            )


def assert_all_valid(response: dict[str, Any]) -> None:
    """Check every card in a tool response. The helper each tool's smoke test calls."""
    for built in response.get("cards") or []:
        assert_valid(built)
