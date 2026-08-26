"""`find_nearby` and `get_route` — Amazon Location Service, with the sequences in code.
**Ported from a verified implementation**, and the four gotchas below were paid for there rather
than rediscovered here. They are the reason this file is longer than "call the API".

**The composite rule in practice.** `geocode → search` and `geocode → geocode → route` are
*sequences*, and they live here. The model supplies a place name and an intent in plain words; it
never handles coordinates and never chains API calls. That is the whole difference between a tool
and
an API wrapper.

**Coordinates never reach the model.** They are an implementation detail of the provider, they are
useless to a language model, and putting them in context invites it to do arithmetic on them.

**Not tenant-scoped, on purpose.** A pharmacy near an address is the same pharmacy for every
customer. When the traveller means "my hotel", `get_trips` resolves it and the agent passes the
address — which is also why that tool's `address` field is load-bearing.
"""

from __future__ import annotations

import os
from typing import Any

import boto3
from shared.cards import Action, CardType, action, card
from tools.common import (
    RequestContext,
    ToolError,
    dispatch,
    log_decision,
    log_refusal,
    tool_response,
)

from .schemas import CATEGORY_MAP, FIND_NEARBY, GET_ROUTE, TRAVEL_MODES

REGION = os.environ.get("LOCATION_REGION", os.environ.get("AWS_REGION", "us-east-1"))

# Standalone namespaces — no place index or route calculator resource to provision, which is why
# this needs IAM permissions but no CDK resources of its own.
_places = None
_routes = None

DEFAULT_RADIUS_M = 3000
MAX_RESULTS = 5


def _places_client():
    """Lazily built so import works without AWS, and reused across invocations."""
    global _places
    if _places is None:
        _places = boto3.client("geo-places", region_name=REGION)
    return _places


def _routes_client():
    global _routes
    if _routes is None:
        _routes = boto3.client("geo-routes", region_name=REGION)
    return _routes


def _geocode(text: str) -> tuple[list[float], str] | None:
    """Place text -> (position, resolved label), or None.
    **Two candidates, scored by query-token overlap — and neither API is reliable alone.** `Geocode`
    mis-resolves some named POIs ("Union Station Chicago" resolved to a nearby gym); biased
    `SearchText` is better for named places but sometimes drifts to an adjacent business. The right
    candidate always echoes more of the query's own words, so that is the tie-break.

    Verified behaviour, not a guess — and the reason this is not a one-line call.
    """
    places = _places_client()
    geocoded = places.geocode(QueryText=text, MaxResults=1)
    items = geocoded.get("ResultItems") or []
    if not items:
        return None

    candidates: list[tuple[list[float], str]] = [
        (items[0]["Position"], items[0].get("Title", text))
    ]
    try:
        # `BiasPosition` is **required** for SearchText, which is why it runs second — the geocode
        # result supplies the bias.
        searched = places.search_text(QueryText=text, BiasPosition=candidates[0][0], MaxResults=1)
        for item in searched.get("ResultItems") or []:
            candidates.append((item["Position"], item.get("Title", text)))
    except Exception:  # noqa: BLE001 - a failed second opinion still leaves the first
        pass

    query_tokens = {t for t in text.lower().replace(",", " ").split() if len(t) > 2}

    def overlap(candidate: tuple[list[float], str]) -> int:
        return len(query_tokens & set(candidate[1].lower().split()))

    return max(candidates, key=overlap)


def _search(position: list[float], what: str, radius_m: int, limit: int) -> tuple[Any, str]:
    """Find places, via the most precise route available. Returns (response, how).
    **Three tiers, and the tier is recorded** so a surprising result can be explained rather than
    guessed at:

    1. A known category -> `SearchNearby` with an exact category id. Most precise.
    2. Otherwise ask `Suggest`; if it recognises the word as a *category*, use the provider's own
       interpretation via `SearchText(QueryId=…)`. This fixed a real mismatch — "supermarket" as
       free text had matched an attorney's office.
    3. Neither -> biased free-text search, best effort.

    Never a guessed category id: an invented one returns confidently empty results.
    """
    places = _places_client()
    category = CATEGORY_MAP.get(what.strip().lower().replace(" ", "_"))

    if category:
        response = places.search_nearby(
            QueryPosition=position,
            QueryRadius=radius_m,
            MaxResults=min(limit, 20),
            AdditionalFeatures=["Contact"],
            Filter={"IncludeCategories": [category]},
        )
        return response, f"category:{category}"

    query_id = None
    try:
        suggested = places.suggest(QueryText=what, BiasPosition=position, MaxResults=3)
        query_id = next(
            (
                item["Query"]["QueryId"]
                for item in suggested.get("ResultItems") or []
                if item.get("SuggestResultItemType") == "Query"
                and (item.get("Query") or {}).get("QueryType") == "Category"
            ),
            None,
        )
    except Exception:  # noqa: BLE001 - Suggest is an optimisation, not a requirement
        pass

    if query_id:
        # **API quirk:** `QueryId` is mutually exclusive with every other parameter — not even
        # `MaxResults` may accompany it. Verified; passing one is a validation error.
        return places.search_text(QueryId=query_id), "suggest-category"

    return (
        places.search_text(QueryText=what, BiasPosition=position, MaxResults=min(limit, 20)),
        f"text:{what}",
    )


def _route_totals(route: dict[str, Any]) -> tuple[int, float] | None:
    """`(minutes, km)` for a route, whichever shape the provider used.
    **The shapes differ by travel mode, and assuming one crashes the other.** A `Car` route
    carries a
    top-level `Summary` with `Distance`/`Duration`; a `Pedestrian` route has **no top-level
    `Summary` at all** — the totals live at
    `Legs[].{Mode}LegDetails.Summary.Overview`. Reading `route["Summary"]` unconditionally raised
    `KeyError: 'Summary'` on every walking route, which surfaced as a generic tool failure rather
    than as anything pointing at travel mode.

    So: prefer the top-level summary, otherwise sum the legs. Summing is also the correct answer
    for a
    multi-leg route, which the top-level figure would only coincidentally match.
    """
    summary = route.get("Summary") or {}
    if summary.get("Duration") is not None and summary.get("Distance") is not None:
        return round(summary["Duration"] / 60), round(summary["Distance"] / 1000, 1)

    seconds = 0.0
    metres = 0.0
    for leg in route.get("Legs") or []:
        # `PedestrianLegDetails`, `VehicleLegDetails`, `FerryLegDetails` — keyed by mode, so match
        # on
        # the suffix rather than enumerating them and breaking on the next one the service adds.
        for key, details in leg.items():
            if not key.endswith("LegDetails") or not isinstance(details, dict):
                continue
            overview = (details.get("Summary") or {}).get("Overview") or {}
            seconds += overview.get("Duration") or 0
            metres += overview.get("Distance") or 0

    if not seconds and not metres:
        return None
    return round(seconds / 60), round(metres / 1000, 1)


def _place_card(item: dict[str, Any]) -> dict[str, Any]:
    hours = item.get("OpeningHours") or []
    name = item.get("Title", "")
    address = (item.get("Address") or {}).get("Label", "")
    data: dict[str, Any] = {
        "name": name,
        "address": address,
        "distance_m": item.get("Distance"),
        # Two at most: a tile listing six categories tells the user nothing more than two do.
        "categories": [c["Name"] for c in (item.get("Categories") or [])[:2]],
    }
    if hours and hours[0].get("OpenNow") is not None:
        data["open_now"] = hours[0]["OpenNow"]
    return card(
        CardType.PLACE,
        # Address-derived rather than a provider id: stable enough to reference, and it does not
        # leak an internal identifier into a channel the user can see.
        f"place-{abs(hash(name + address)) % 10**10}",
        data,
        [action(Action.GET_DIRECTIONS, "Directions", name=name, address=address)],
    )


def find_nearby(arguments: dict[str, Any], context: RequestContext) -> dict[str, Any]:
    """Places near a named location."""
    near = (arguments.get("near") or "").strip()
    what = (arguments.get("what") or "").strip()
    if not near or not what:
        raise ToolError(
            "I need both a place to search around and what to look for — for example a hotel "
            "address and 'coffee'."
        )

    radius_m = int(arguments.get("radius_m") or DEFAULT_RADIUS_M)
    limit = int(arguments.get("limit") or MAX_RESULTS)

    geo = _geocode(near)
    if geo is None:
        log_refusal("could not geocode a place", query_kind="near")
        return tool_response(
            message=(
                f"I couldn't find {near!r} on the map. A street address usually resolves better "
                "than a building name."
            ),
            provenance={"source": "amazon_location_places", "step": "geocode"},
        )
    position, resolved = geo

    try:
        response, resolved_via = _search(position, what, radius_m, limit)
    except Exception as error:  # noqa: BLE001 - a provider failure must not become an invented list
        log_refusal("place search failed", error=type(error).__name__)
        return tool_response(
            message="I couldn't search for places just now, so I'd rather not guess.",
            provenance={"source": "amazon_location_places", "step": "search"},
        )

    items = (response.get("ResultItems") or [])[:limit]
    what_label = what.replace("_", " ")

    if not items:
        return tool_response(
            message=(
                f"I didn't find any {what_label} within {radius_m // 1000 or 1} km of {resolved}."
            ),
            provenance={
                "source": "amazon_location_places",
                "resolved_near": resolved,
                "resolved_via": resolved_via,
            },
        )

    log_decision(
        "found nearby places",
        what=what,
        resolved_via=resolved_via,
        radius_m=radius_m,
        returned=len(items),
    )

    return tool_response(
        cards=[_place_card(item) for item in items],
        facts={
            "count": len(items),
            "what": what_label,
            "radius_m": radius_m,
            # The resolved label, so the model can say *which* hotel it searched around — the
            # commonest cause of a confusing answer is a place that resolved elsewhere.
            "searched_around": resolved,
        },
        provenance={
            "source": "amazon_location_places",
            "resolved_near": resolved,
            # Which tier answered. Records why a surprising result looks the way it does.
            "resolved_via": resolved_via,
        },
    )


def get_route(arguments: dict[str, Any], context: RequestContext) -> dict[str, Any]:
    """Travel time and distance between two named places."""
    origin = (arguments.get("origin") or "").strip()
    destination = (arguments.get("destination") or "").strip()
    if not origin or not destination:
        raise ToolError("I need both a starting point and a destination to work out a journey.")

    mode = (arguments.get("mode") or "car").strip().lower()
    if mode not in TRAVEL_MODES:
        raise ToolError(f"I can't route by {mode!r}. I can do: {', '.join(TRAVEL_MODES)}.")
    departure_time = (arguments.get("departure_time") or "").strip() or None

    start = _geocode(origin)
    end = _geocode(destination)
    if start is None or end is None:
        missing = origin if start is None else destination
        log_refusal("could not geocode a place", query_kind="route")
        return tool_response(
            message=f"I couldn't find {missing!r} on the map. An address resolves more reliably.",
            provenance={"source": "amazon_location_routes", "step": "geocode"},
        )

    kwargs: dict[str, Any] = {
        "Origin": start[0],
        "Destination": end[0],
        "TravelMode": TRAVEL_MODES[mode],
    }
    if departure_time:
        # What makes the estimate traffic-aware. Without it the answer is a free-flow duration,
        # which is optimistic in exactly the situations a traveller cares about.
        kwargs["DepartureTime"] = departure_time

    routes = _routes_client()
    try:
        response = routes.calculate_routes(**kwargs)
    except routes.exceptions.ValidationException:
        # **The failure that looks like the wrong thing.** Pedestrian routes are range-limited, so
        # an
        # ambiguous geocode ("Marriott Dublin" -> Dublin, *Ohio*) surfaces here as a routing
        # validation error rather than as a geocode failure. Surfacing *what each side resolved to*
        # is what lets the agent ask a useful question instead of apologising vaguely.
        log_refusal(
            "route rejected as implausible",
            resolved_origin=start[1],
            resolved_destination=end[1],
        )
        return tool_response(
            message=(
                f"Those two places resolved a long way apart — {start[1]} and {end[1]}. "
                "Could you add the city or country so I pick the right ones?"
            ),
            provenance={
                "source": "amazon_location_routes",
                "resolved_origin": start[1],
                "resolved_destination": end[1],
                "error": "geocode_ambiguity_or_range",
            },
        )
    except Exception as error:  # noqa: BLE001
        log_refusal("route calculation failed", error=type(error).__name__)
        return tool_response(
            message="I couldn't work out that journey just now, so I'd rather not guess.",
            provenance={"source": "amazon_location_routes", "step": "route"},
        )

    found = response.get("Routes") or []
    if not found:
        return tool_response(
            message=f"I couldn't find a {mode} route from {start[1]} to {end[1]}.",
            provenance={"source": "amazon_location_routes"},
        )

    totals = _route_totals(found[0])
    if totals is None:
        log_refusal("route returned no distance or duration", mode=mode)
        return tool_response(
            message="I got a route back but couldn't read its length, so I'd rather not guess.",
            provenance={"source": "amazon_location_routes", "step": "summary"},
        )
    minutes, km = totals

    log_decision(
        "calculated a route",
        mode=mode,
        duration_min=minutes,
        distance_km=km,
        traffic_aware=bool(departure_time),
    )

    return tool_response(
        cards=[
            card(
                CardType.ROUTE,
                f"route-{abs(hash(start[1] + end[1] + mode)) % 10**10}",
                {
                    "origin": start[1],
                    "destination": end[1],
                    "mode": mode,
                    "duration_min": minutes,
                    "distance_km": km,
                    "traffic_aware": bool(departure_time),
                },
            )
        ],
        facts={
            "duration_min": minutes,
            "distance_km": km,
            "mode": mode,
            # Stated so the model does not present a free-flow estimate as a rush-hour one.
            "traffic_aware": bool(departure_time),
            "resolved_origin": start[1],
            "resolved_destination": end[1],
        },
        provenance={
            "source": "amazon_location_routes",
            "departure_time": departure_time,
        },
    )


TOOLS = {FIND_NEARBY: find_nearby, GET_ROUTE: get_route}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Gateway target entry point. All the shared work lives in `dispatch`."""
    return dispatch(event, context, TOOLS)
