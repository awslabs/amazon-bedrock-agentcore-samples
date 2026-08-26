"""Tool schemas for the search family — the single source of truth.

**Two tools, not five.** `search_hotels` takes filters as *parameters* — breakfast, gym,
workspace, chain, star limit — rather than spawning `search_hotels_with_breakfast` and friends.
Variation rides in arguments; it never becomes a new tool. That is the sizing rule doing real work:
five near-identical tools would dilute selection (the model picking between them is a coin flip)
for zero new capability.

**No `enum`.** The Gateway's `inlinePayload` supports only
`type`/`properties`/`required`/`items`/`description`, so closed sets ride in descriptions and the
tool enforces them itself.

**No tenant, no traveller id.** The policy that decides `in_policy` comes from verified claims, so
the model cannot search against another company's cap.
"""

from typing import Any

SEARCH_FLIGHTS = "search_flights"
SEARCH_HOTELS = "search_hotels"

# Closed sets, enforced in code. Named here so handler and description cannot drift.
CABINS = ("economy", "premium_economy", "business", "first")
SORTS = ("price", "duration", "departure")

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": SEARCH_FLIGHTS,
        "label": "Searching flights",
        "description": (
            "Search flights between two places on a date, annotated with whether each option is "
            "within the caller's travel policy. Origin and destination may be city names, airport "
            "names or IATA codes — the tool resolves them, so pass what the user said. Returns "
            "options as cards the user can select, plus counts and the policy cap as facts. Do not "
            "judge policy compliance yourself: each option already carries it."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "origin": {
                    "type": "string",
                    "description": (
                        "Where the traveller departs from — a city, airport name, or IATA code. "
                        "Omit only if the user clearly means their home airport, which the tool "
                        "reads from their profile."
                    ),
                },
                "destination": {
                    "type": "string",
                    "description": "Where they are going — a city, airport name, or IATA code.",
                },
                "depart_on": {
                    "type": "string",
                    "description": "Departure date, as YYYY-MM-DD.",
                },
                "return_on": {
                    "type": "string",
                    "description": (
                        "Return date as YYYY-MM-DD, for a round trip. Omit for one way."
                    ),
                },
                "cabin": {
                    "type": "string",
                    "description": (
                        "Restrict to one cabin: 'economy', 'premium_economy', 'business', 'first'. "
                        "Omit to see everything — prefer omitting, because the policy annotation "
                        "then shows the traveller what they may and may not book."
                    ),
                },
                "sort": {
                    "type": "string",
                    "description": (
                        "Order results by 'price' (default), 'duration', or 'departure' time."
                    ),
                },
                "traveler_name": {
                    "type": "string",
                    "description": (
                        "Only when searching on someone else's behalf — the name as the user said "
                        "it. Omit for the caller. Affects whose policy history applies to "
                        "entitlement-based cabin rules."
                    ),
                },
            },
            "required": ["destination", "depart_on"],
        },
    },
    {
        "name": SEARCH_HOTELS,
        "label": "Searching hotels",
        "description": (
            "Search hotels in a city for a date range, annotated with whether each is within the "
            "caller's nightly cap and star limit. Amenity requirements ride as filters — ask for "
            "breakfast or a gym here rather than filtering the results yourself. Returns options "
            "as selectable cards plus counts and the cap as facts."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "destination": {
                    "type": "string",
                    "description": "City or place name to search in.",
                },
                "check_in": {"type": "string", "description": "Check-in date, as YYYY-MM-DD."},
                "check_out": {"type": "string", "description": "Check-out date, as YYYY-MM-DD."},
                "breakfast_included": {
                    "type": "boolean",
                    "description": (
                        "Only properties including breakfast. Omit if it does not matter."
                    ),
                },
                "gym": {
                    "type": "boolean",
                    "description": "Only properties with a gym. Omit if it does not matter.",
                },
                "workspace": {
                    "type": "boolean",
                    "description": (
                        "Only properties with a desk or work area. Omit if it does not matter."
                    ),
                },
                "chain": {
                    "type": "string",
                    "description": (
                        "Restrict to one hotel chain, e.g. 'Marriott'. Use when the traveller "
                        "states a preference; their saved preference is in their profile."
                    ),
                },
                "max_star_rating": {
                    "type": "number",
                    "description": (
                        "Cap the star rating, 1 to 5. Rarely needed — the tenant's own star limit "
                        "is applied automatically."
                    ),
                },
                "sort": {
                    "type": "string",
                    "description": "Order by 'price' (default) or 'duration'.",
                },
                "traveler_name": {
                    "type": "string",
                    "description": (
                        "Only when searching on someone else's behalf — the name as the user said "
                        "it. Omit for the caller."
                    ),
                },
            },
            "required": ["destination", "check_in", "check_out"],
        },
    },
]
