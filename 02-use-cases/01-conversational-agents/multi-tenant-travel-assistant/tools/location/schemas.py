"""Tool schemas for the location family — the single source of truth.
**Ported from a working implementation** (`tripp/tools/location`) rather than written fresh, because
its behaviour was verified live against Amazon Location Service and its failure modes are documented
rather than guessed. What changed in the port is this sample's conventions: the `{cards, facts,
message, provenance}` envelope, `tools/common` for dispatch and identity, and the shared card
constructor.

**Nothing here is tenant-scoped, and that is worth stating.** A coffee shop near a hotel is the same
coffee shop for every customer. These tools take a *place name* — and when the traveller means
"my hotel", the trip resolution happens in `get_trips` and the agent passes the resolved address
here. Tools stay single-purpose; a `find_near_my_booking` composite would be the model's reasoning
job done twice.

**No `enum`.** Closed sets ride in descriptions, and an off-list category degrades to free-text
search rather than to a guessed category id.
"""

from typing import Any

FIND_NEARBY = "find_nearby"
GET_ROUTE = "get_route"

# Plain words the model may use -> Amazon Location Service category ids. Closed on purpose: an
# unknown word degrades to a text search, never to an invented category id.
CATEGORY_MAP = {
    "ev_charger": "ev_charging_station",
    "restaurant": "restaurant",
    "coffee": "coffee_shop",
    "pharmacy": "pharmacy",
    "atm": "atm_bank_exchange",
    "hospital": "hospital",
    "train_station": "railway_station",
    "parking": "parking",
    "supermarket": "grocery",
    "gym": "gym_health_club",
}

TRAVEL_MODES = {"car": "Car", "walk": "Pedestrian", "truck": "Truck"}

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": FIND_NEARBY,
        "label": "Finding places nearby",
        "description": (
            "Find places near a location: coffee, restaurants, pharmacies, EV chargers, parking, "
            "train stations, gyms. Use when the traveller asks what is near somewhere — 'coffee "
            "near my hotel', 'a pharmacy close to the office'. Give the location as a **place name "
            "or address**, never coordinates: if they mean their hotel, get the trip first "
            "and pass "
            "the hotel's address from it, which resolves far more reliably than a property name."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "near": {
                    "type": "string",
                    "description": (
                        "The place to search around — an address is best, a place name works. "
                        "For 'near my hotel', pass the hotel address from the trips tool."
                    ),
                },
                "what": {
                    "type": "string",
                    "description": (
                        "What to look for. Known categories, which give the most precise results: "
                        "ev_charger, restaurant, coffee, pharmacy, atm, hospital, train_station, "
                        "parking, supermarket, gym. Anything else is searched as free text."
                    ),
                },
                "radius_m": {
                    "type": "number",
                    "description": (
                        "Search radius in metres. Defaults to 3000 (about a 35-minute walk)."
                    ),
                },
                "limit": {
                    "type": "number",
                    "description": "How many results to return. Defaults to 5.",
                },
            },
            "required": ["near", "what"],
        },
    },
    {
        "name": GET_ROUTE,
        "label": "Working out the journey",
        "description": (
            "Travel time and distance between two places — traffic-aware when a departure time is "
            "given. Use for 'how do I get from the airport to the hotel', 'how long will that "
            "take'. Give places as names or addresses, never coordinates. If two places resolve "
            "implausibly far apart the tool says so rather than returning a nonsense route, so "
            "relay that as a request to be more specific."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "Starting place name or address."},
                "destination": {
                    "type": "string",
                    "description": "Destination place name or address.",
                },
                "mode": {
                    "type": "string",
                    "description": "How they are travelling: 'car' (default), 'walk', or 'truck'.",
                },
                "departure_time": {
                    "type": "string",
                    "description": (
                        "Optional ISO-8601 departure time for a traffic-aware estimate, e.g. "
                        "'2026-11-10T13:00:00Z'. Supply it whenever the traveller mentions "
                        "a time — without it the estimate ignores traffic. If they give a "
                        "time of day with no date, use the date of the trip in question, or "
                        "today's date for a trip already under way. Never ask for a date "
                        "instead of answering: a route without traffic is a useful answer, "
                        "and a question in its place is not."
                    ),
                },
            },
            "required": ["origin", "destination"],
        },
    },
]
