"""`search_flights` and `search_hotels` — options, annotated with policy.

**The annotation is the product, not the listing.** Any API can return flights. What makes this
useful to a corporate traveller is that each option already says whether *their* company allows it —
computed against the tenant's own cap and cabin rule, server-side, before the model sees anything.

Two consequences shape this file:

**The tool never decides policy.** `policy_status` and `policy_note` arrive from the backend, which
computes them with the same code `check_policy_eligibility` uses. A tool that re-derived "in policy"
from a cap and a price would be a second implementation of a policy rule, and the two would drift.

**Aggregates come from the backend too.** `total_options`, `in_policy_options`, `cheapest_in_policy`
are computed over the *whole* result set and returned as facts — because the model must never count
cards. It sees a truncated list of tiles; counting those would answer "how many options are in
policy?" wrongly and confidently.
"""

from __future__ import annotations

import json
from typing import Any

from shared.cards import Action, CardType, action, card
from tools.common import (
    BackendError,
    RequestContext,
    ToolError,
    backend_url,
    dispatch,
    ensure_can_act_for,
    log_decision,
    post,
    resolve_target_traveler,
    tool_response,
)

from .schemas import CABINS, SEARCH_FLIGHTS, SEARCH_HOTELS, SORTS

# Enough to choose from, few enough to keep the context window (and the user's attention) small.
# The full counts ride in `facts`, so truncation never becomes a wrong answer.
MAX_OPTIONS = 5


def _money(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    """A `Money` as the card contract wants it, or nothing."""
    if not raw:
        return None
    return {"amount": raw.get("amount"), "currency": raw.get("currency")}


def _summary_facts(summary: dict[str, Any], shown: int) -> dict[str, Any]:
    """Counts over the whole result set, computed by the backend.

    The model must never count cards: it sees at most `MAX_OPTIONS` tiles, so counting those would
    answer "how many are in policy?" from a truncated list.
    """
    facts: dict[str, Any] = {
        "total_options": summary.get("total_options"),
        "in_policy_options": summary.get("in_policy_options"),
    }
    if cheapest := _money(summary.get("cheapest_in_policy")):
        facts["cheapest_in_policy"] = cheapest
    if cap := _money(summary.get("policy_cap")):
        facts["policy_cap"] = cap
    total = summary.get("total_options") or 0
    if total > shown:
        # Stated, because a model that thinks it has every option will describe the cheapest tile as
        # the cheapest option.
        facts["truncated"] = f"showing {shown} of {total}"
    return facts


def _flight_card(option: dict[str, Any]) -> dict[str, Any]:
    option_id = option.get("option_id") or ""
    in_policy = option.get("policy_status") == "in_policy"
    data: dict[str, Any] = {
        "carrier": option.get("carrier_name") or option.get("carrier"),
        "flight_number": option.get("flight_number"),
        "depart_airport": option.get("depart_airport"),
        "depart_time": option.get("depart_at"),
        "arrive_airport": option.get("arrive_airport"),
        "arrive_time": option.get("arrive_at"),
        "duration_min": option.get("duration_minutes"),
        "stops": option.get("stops"),
        "cabin": option.get("cabin"),
        "price": _money(option.get("price")),
        "in_policy": in_policy,
    }
    if note := option.get("policy_note"):
        # Only when out of policy: a note on a compliant option is noise, and noise on every tile
        # trains a user to stop reading the notes that matter.
        data["policy_note"] = note
    return card(
        CardType.FLIGHT_OPTION,
        option_id,
        data,
        [
            action(Action.SELECT_FLIGHT, "Select", option_id=option_id),
            action(Action.VIEW_FARE_RULES, "Fare rules", option_id=option_id),
        ],
    )


def _hotel_card(option: dict[str, Any]) -> dict[str, Any]:
    option_id = option.get("option_id") or ""
    data: dict[str, Any] = {
        "name": option.get("property_name"),
        "address": option.get("address"),
        "star_rating": option.get("star_rating"),
        "nightly_rate": _money(option.get("nightly_rate")),
        "total": _money(option.get("total")),
        "in_policy": option.get("policy_status") == "in_policy",
        # Capped at four by the card contract: a tile listing fourteen amenities is unreadable, and
        # the details tool answers "does it have X?" properly.
        "amenities": (option.get("amenities") or [])[:4],
    }
    if option.get("is_preferred_chain"):
        data["preferred"] = True
    if note := option.get("policy_note"):
        data["policy_note"] = note
    return card(
        CardType.HOTEL_OPTION,
        option_id,
        data,
        [
            action(Action.SELECT_HOTEL, "Select", option_id=option_id),
            action(
                Action.VIEW_DETAILS,
                "Details",
                hotel_id=option.get("property_code"),
            ),
        ],
    )


def _detail(error: BackendError) -> dict[str, Any]:
    """FastAPI's `detail` dict, parsed back out of the error message.

    The `BackendError` text embeds the response body, and the useful half of an unresolvable
    place is
    in there — suggestions, or the candidate places. Losing it turns a recoverable dead end into a
    conversation that stalls.
    """
    try:
        start = str(error).find("{")
        if start >= 0:
            return json.loads(str(error)[start:]).get("detail") or {}
    except (json.JSONDecodeError, AttributeError):
        pass
    return {}


def _ambiguous_place(error: BackendError) -> dict[str, Any]:
    """Turn the backend's 409 into the question it is.

    **No card, and no options.** A card would render as an answer to a question that has not been
    answered yet, and returning search results for one of the candidates is precisely the silent
    choice the backend refused to make. The traveller names the place; the next turn searches it.
    """
    detail = _detail(error)
    candidates = [c.get("label") for c in detail.get("candidates") or [] if c.get("label")]
    question = detail.get("message") or "That place name could mean more than one place."
    if candidates:
        question = f"{question} Did you mean {' or '.join(candidates)}?"
    raise ToolError(question)


def _unsupported_place(error: BackendError, what: str) -> dict[str, Any]:
    """Turn the backend's 404 into a refusal that *helps*.

    The backend answers an unknown place with `{message, suggestions}` — nearby airports it does
    support. Swallowing that into "I couldn't find that" throws away the only part the traveller can
    act on, and turns a recoverable dead end into a conversation that stalls. So the suggestions are
    parsed back out and offered.

    Deliberately a refusal rather than a guess: picking the nearest supported airport for them would
    silently search a different city than the one they asked about.
    """
    suggestions: list[str] = _detail(error).get("suggestions") or []

    message = f"I don't have {what} in this demo's route network."
    if suggestions:
        message += " Nearby places I can search: " + ", ".join(suggestions[:4]) + "."
    return tool_response(message=message, provenance={"source": "place_resolution"})


def _resolve_traveler(arguments: dict[str, Any], context: RequestContext) -> str:
    """Whose policy history applies. Defaults to the caller."""
    traveler_id, _ = resolve_target_traveler(context, arguments.get("traveler_name"))
    ensure_can_act_for(context, traveler_id)
    return traveler_id


def _sort(arguments: dict[str, Any]) -> str | None:
    sort = (arguments.get("sort") or "").strip().lower() or None
    if sort and sort not in SORTS:
        raise ToolError(f"I can't sort by {sort!r}. I can sort by: {', '.join(SORTS)}.")
    return sort


def search_flights(arguments: dict[str, Any], context: RequestContext) -> dict[str, Any]:
    """Flights between two places, each annotated against the caller's policy."""
    destination = (arguments.get("destination") or "").strip()
    depart_on = (arguments.get("depart_on") or "").strip()
    if not destination or not depart_on:
        raise ToolError("To search flights I need at least a destination and a departure date.")

    cabin = (arguments.get("cabin") or "").strip().lower() or None
    if cabin and cabin not in CABINS:
        raise ToolError(
            f"I don't recognise the cabin {cabin!r}. Valid cabins are: {', '.join(CABINS)}."
        )

    traveler_id = _resolve_traveler(arguments, context)

    body: dict[str, Any] = {
        # Absent origin means the traveller's home airport, which the backend reads from their
        # profile — the model is not asked to remember or guess it.
        "origin": (arguments.get("origin") or "").strip() or None,
        "destination": destination,
        "depart_on": depart_on,
    }
    if return_on := (arguments.get("return_on") or "").strip():
        body["return_on"] = return_on
    if cabin:
        body["cabin"] = cabin
    if sort := _sort(arguments):
        body["sort"] = sort

    # The traveller rides on `X-Traveler-Id`, injected by `_headers` from the verified context.
    # Passing it again as a parameter would be a second channel for the same fact — and the second
    # one would be caller-supplied, which is precisely the thing the design forbids.
    try:
        payload = post(
            backend_url(),
            "/v1/booking/search/air",
            context,
            body={k: v for k, v in body.items() if v is not None},
        )
    except BackendError as error:
        if error.status == 409:
            _ambiguous_place(error)
        if error.status == 404:
            return _unsupported_place(error, f"a route to {destination}")
        if error.status == 400:
            # The backend could not resolve an origin and is asking for one. Raised as a
            # ToolError so
            # the model relays the question, rather than propagating as a backend failure — which is
            # what turned "flight to London" into "I couldn't reach the flight search system".
            raise ToolError(
                "I need to know which airport you're flying from — your profile doesn't list a "
                "home airport."
            ) from None
        raise
    options = (payload or {}).get("options") or []
    summary = (payload or {}).get("summary") or {}

    if not options:
        return tool_response(
            message=(
                f"I couldn't find any flights to {destination} on {depart_on}. "
                "A different date or nearby airport may have options."
            ),
            provenance={"source": "flight_search", "tenant_id": context.tenant_id},
        )

    shown = options[:MAX_OPTIONS]
    log_decision(
        "searched flights",
        destination=destination,
        depart_on=depart_on,
        cabin=cabin,
        returned=summary.get("total_options"),
        in_policy=summary.get("in_policy_options"),
        shown=len(shown),
    )

    return tool_response(
        cards=[_flight_card(option) for option in shown],
        facts=_summary_facts(summary, len(shown)),
        provenance={
            "source": "flight_search",
            "tenant_id": context.tenant_id,
            "traveler_id": traveler_id,
            "resolved_origin": (payload or {}).get("resolved_origin"),
            "resolved_destination": (payload or {}).get("resolved_destination"),
            # Named so a reader knows the annotation is not the model's judgement.
            "policy_annotated_by": "backend policy engine",
        },
    )


def search_hotels(arguments: dict[str, Any], context: RequestContext) -> dict[str, Any]:
    """Hotels in a city, each annotated against the caller's cap and star limit."""
    destination = (arguments.get("destination") or "").strip()
    check_in = (arguments.get("check_in") or "").strip()
    check_out = (arguments.get("check_out") or "").strip()
    if not destination or not check_in or not check_out:
        raise ToolError(
            "To search hotels I need a destination and both check-in and check-out dates."
        )

    traveler_id = _resolve_traveler(arguments, context)

    # Filters ride as parameters — this is the sizing rule in practice. Five amenity-specific tools
    # would dilute selection for no new capability.
    filters = {
        key: arguments.get(key)
        for key in ("breakfast_included", "gym", "workspace", "chain", "max_star_rating")
        if arguments.get(key) is not None
    }

    body: dict[str, Any] = {
        "destination": destination,
        "check_in": check_in,
        "check_out": check_out,
    }
    if filters:
        body["filters"] = filters
    if sort := _sort(arguments):
        body["sort"] = sort

    try:
        payload = post(backend_url(), "/v1/booking/search/hotels", context, body=body)
    except BackendError as error:
        if error.status == 409:
            _ambiguous_place(error)
        if error.status == 404:
            return _unsupported_place(error, destination)
        raise
    options = (payload or {}).get("options") or []
    summary = (payload or {}).get("summary") or {}

    if not options:
        return tool_response(
            message=(
                f"I couldn't find any hotels in {destination} for those dates"
                + (" with those requirements." if filters else ".")
            ),
            provenance={"source": "hotel_search", "tenant_id": context.tenant_id},
        )

    shown = options[:MAX_OPTIONS]
    log_decision(
        "searched hotels",
        destination=destination,
        check_in=check_in,
        filters=sorted(filters),
        returned=summary.get("total_options"),
        in_policy=summary.get("in_policy_options"),
        shown=len(shown),
    )

    return tool_response(
        cards=[_hotel_card(option) for option in shown],
        facts=_summary_facts(summary, len(shown)),
        provenance={
            "source": "hotel_search",
            "tenant_id": context.tenant_id,
            "traveler_id": traveler_id,
            "resolved_city": (payload or {}).get("resolved_city"),
            "policy_annotated_by": "backend policy engine",
        },
    )


TOOLS = {SEARCH_FLIGHTS: search_flights, SEARCH_HOTELS: search_hotels}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Gateway target entry point. All the shared work lives in `dispatch`."""
    return dispatch(event, context, TOOLS)
