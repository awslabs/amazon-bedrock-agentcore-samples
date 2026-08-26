"""`get_trips` — the context resolver.

**The tool other tools depend on.** Half the post-booking questions start here: "which hotel am I
in?", "when do I fly home?", "chargers near my hotel", and every eligibility question that counts
travel history. So this handler has an obligation the other read tools do not — its output is
consumed by *tools*, not only by the model.

That shapes one decision. Each hotel segment emits a `Place` with a full **address**, because the
location tools geocode a *string* and an address resolves far more reliably than a property name
("Hilton Midtown" is ambiguous across a city; a street address is not). Losing the address here
would degrade `find_nearby` in a way that looks like a geocoding problem three tools away.

Cards, not just facts: a trip is the clearest thing in the system to render as a tile, and
`view_trip` is the action that makes a list of them navigable. `facts` carries the counts the model
narrates, so the answer remains useful without requiring the model to interpret card structure.
"""

from __future__ import annotations

from typing import Any

from shared.cards import Action, CardType, action, card
from tools.common import (
    RequestContext,
    ToolError,
    backend_url,
    dispatch,
    ensure_can_act_for,
    get,
    log_decision,
    resolve_target_traveler,
    tool_response,
)

from .schemas import GET_TRIPS, WINDOWS

# Enough to answer "my trips" without flooding the context window. A traveller with forty past
# trips does not want forty tiles, and the model does not need them to answer a question about the
# next one — so the list is capped and the count is reported in `facts`, which is the honest way to
# truncate: say that you did.
MAX_TRIPS = 8


def _place(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    """A destination or hotel location, shaped for the location tools.

    `address` is preserved when present and omitted when not, rather than substituted with the
    name: `find_nearby` decides between address and name itself, and a name masquerading as an
    address would make that choice silently wrong.
    """
    if not raw:
        return None
    place: dict[str, Any] = {"name": raw.get("name"), "city": raw.get("city")}
    if address := raw.get("address"):
        place["address"] = address
    if country := raw.get("country"):
        place["country"] = country
    return place


def _segments(trip: dict[str, Any]) -> list[dict[str, str]]:
    """Air and hotel segments as short labels for the card.

    Labels rather than nested structures: the card shows "what is in this trip" at a glance, and a
    user who wants the flight number asks a follow-up. The full detail stays in `facts` for the
    model, so nothing is lost — it just is not on the tile.
    """
    segments: list[dict[str, str]] = []
    for air in trip.get("air_segments") or []:
        segments.append(
            {
                "type": "air",
                # **No carrier prefix: `flight_number` already carries it.** The generator builds
                # it as `f"{code}{number}"` (`backend/generator/flights.py`) and the fixtures
                # follow, so prefixing produced `UAUA928` on every trip tile.
                "label": (
                    f"{air.get('flight_number', '')} "
                    f"{air.get('depart_airport', '')}→{air.get('arrive_airport', '')}"
                ).strip(),
            }
        )
    for hotel in trip.get("hotel_segments") or []:
        nights = hotel.get("nights")
        label = hotel.get("property_name") or "Hotel"
        if nights:
            label = f"{label} · {nights} night{'s' if nights != 1 else ''}"
        segments.append({"type": "hotel", "label": label})
    return segments


def _trip_card(trip: dict[str, Any]) -> dict[str, Any]:
    trip_id = trip.get("trip_id") or ""
    return card(
        CardType.TRIP,
        trip_id,
        {
            "trip_id": trip_id,
            "label": trip.get("label"),
            "status": trip.get("status"),
            "destination": _place(trip.get("destination")),
            "start_date": trip.get("starts_on"),
            "end_date": trip.get("ends_on"),
            "segments": _segments(trip),
        },
        [action(Action.VIEW_TRIP, "View trip", trip_id=trip_id)],
    )


def _hotel_facts(trip: dict[str, Any]) -> list[dict[str, Any]]:
    """Hotel stays with their addresses — the handoff the location tools consume."""
    stays = []
    for hotel in trip.get("hotel_segments") or []:
        stay: dict[str, Any] = {
            "property_name": hotel.get("property_name"),
            "check_in": hotel.get("check_in"),
            "check_out": hotel.get("check_out"),
        }
        if location := _place(hotel.get("location")):
            stay["location"] = location
        # **The handoff that makes cancelling reachable.** No tool lists reservations, so this
        # is the
        # only place the model can learn a booking reference — without it, "cancel my hotel
        # reservation" could fetch the itinerary and go no further. Omitted when absent rather than
        # sent as null, so a segment nobody booked here does not look cancellable.
        if booking_ref := hotel.get("booking_ref"):
            stay["booking_ref"] = booking_ref
        stays.append(stay)
    return stays


def get_trips(arguments: dict[str, Any], context: RequestContext) -> dict[str, Any]:
    """A traveller's trips, defaulting to the caller.

    Acting for someone else passes through both authorization halves: the name is resolved inside
    the caller's authorised scope, then `can_book_for` is re-checked against the backend. The
    resolution already scoped it — the second check is because a client-held reference is
    re-validated rather than trusted.
    """
    window = (arguments.get("window") or "").strip().lower() or None
    if window and window not in WINDOWS:
        # Refuse rather than silently ignore: a model that asked for "current" and got everything
        # would narrate the wrong trip with full confidence.
        raise ToolError(
            f"I don't recognise the trip window {window!r}. "
            f"Use one of: {', '.join(WINDOWS)}, or omit it for all trips."
        )

    traveler_id, _ = resolve_target_traveler(context, arguments.get("traveler_name"))
    ensure_can_act_for(context, traveler_id)

    params = {"traveler": traveler_id}
    if window:
        params["status"] = window
    raw = get(backend_url(), "/v1/trips", context, params=params)
    trips = raw if isinstance(raw, list) else []

    if not trips:
        return tool_response(
            message=(
                "I couldn't find any trips"
                + (f" that are {window.replace('_', ' ')}" if window else "")
                + " for that traveller."
            ),
            provenance={
                "source": "trips",
                "tenant_id": context.tenant_id,
                "traveler_id": traveler_id,
            },
        )

    shown = trips[:MAX_TRIPS]
    cards = [_trip_card(trip) for trip in shown]

    facts: dict[str, Any] = {
        "trip_count": len(trips),
        "trips": [
            {
                "trip_id": trip.get("trip_id"),
                "label": trip.get("label"),
                "status": trip.get("status"),
                "starts_on": trip.get("starts_on"),
                "ends_on": trip.get("ends_on"),
                "destination": _place(trip.get("destination")),
                "hotels": _hotel_facts(trip),
                "international": any(
                    air.get("is_international") for air in (trip.get("air_segments") or [])
                ),
            }
            for trip in shown
        ],
    }
    if len(trips) > len(shown):
        # Said explicitly, because a model that believes it has the full list will answer "how many
        # trips have I taken?" from a truncated one.
        facts["truncated"] = f"showing {len(shown)} of {len(trips)}"

    log_decision(
        "listed trips",
        target_traveler_id=traveler_id,
        acting_for_self=traveler_id == context.traveler_id,
        window=window,
        returned=len(trips),
        shown=len(shown),
    )

    return tool_response(
        cards=cards,
        facts=facts,
        provenance={
            "source": "trips",
            "tenant_id": context.tenant_id,
            "traveler_id": traveler_id,
            "window": window or "all",
        },
    )


TOOLS = {GET_TRIPS: get_trips}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Gateway target entry point. All the shared work lives in `dispatch`."""
    return dispatch(event, context, TOOLS)
