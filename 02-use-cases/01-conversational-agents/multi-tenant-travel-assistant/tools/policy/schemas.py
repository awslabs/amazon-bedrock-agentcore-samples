"""Tool schemas for the policy family — the single source of truth.

Two constraints shape everything here:

**No tenant, no traveller.** Identity is injected from verified claims, so it never
appears as an input. If a tenant field ever shows up in this file, the isolation
story is already broken — the model would be choosing whose policy to read.

**No `enum`.** The Gateway's `inlinePayload` supports only
`type`/`properties`/`required`/`items`/`description`, so a closed set rides in the
description and the tool refuses unknown values itself. Declaring an `enum` here
fails at target registration, not at synth.
"""

from typing import Any

GET_TRAVEL_POLICY = "get_travel_policy"
CHECK_POLICY_ELIGIBILITY = "check_policy_eligibility"

# Closed set, enforced in code rather than by the schema. Named here so the handler
# and the description cannot drift apart.
TOPICS = ("air", "hotel", "general")

# The three eligibility questions the backend can decide. Closed set, enforced in code.
CHECKS = ("air", "hotel", "advance_purchase")
CABINS = ("economy", "premium_economy", "business", "first")

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": GET_TRAVEL_POLICY,
        # Human-readable status for the UI's "working on it" pill. Lives here rather than
        # in a separate registry so one file owns everything about a tool, and is
        # **stripped before the Gateway sees it** (`export_schemas.py`) because
        # inlinePayload rejects unknown keys.
        #
        # Present continuous, and phrased as a person would: `get_travel_policy` in a
        # status pill reads as an implementation leak. Never model-authored — a model
        # asked to narrate its own routing eventually narrates it wrongly.
        "label": "Checking your travel policy",
        "description": (
            "Get the caller's own company travel policy: hotel nightly cap, star "
            "rating limit, cabin-class rules, advance-purchase requirements, and "
            "any additional written rules. Returns the policy as facts to state, "
            "never a computed verdict — to ask whether a specific booking is "
            "allowed, use the eligibility tool instead. Call this before quoting "
            "any policy figure; never state a cap or rule this tool did not return."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": (
                        "Which part of the policy to read. One of: 'air' (cabin "
                        "class, advance purchase, refundability), 'hotel' (nightly "
                        "cap, star rating), 'general' (everything else). Omit to "
                        "get all topics — do that when the question is broad or "
                        "the right topic is unclear."
                    ),
                }
            },
            # Nothing is required: "what's my hotel cap?" and "what's our travel
            # policy?" are both legitimate, and forcing a topic would make the
            # model guess one.
            "required": [],
        },
    },
    {
        "name": CHECK_POLICY_ELIGIBILITY,
        "label": "Checking what your policy allows",
        "description": (
            "Decide whether something specific is allowed under the caller's travel policy, and "
            "get the reasoning. Use this for any 'am I allowed…', 'can I book…', 'is this within "
            "policy?' question — it returns a **decided verdict** with the arithmetic shown, "
            "which you should state rather than recompute. Do not compare figures yourself: ask "
            "this tool. For the rules as written (caps, thresholds) without a verdict, use the "
            "travel policy tool instead."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "check": {
                    "type": "string",
                    "description": (
                        "What to decide. One of: 'air' (is this cabin allowed on this flight?), "
                        "'hotel' (is this nightly rate and star rating allowed?), "
                        "'advance_purchase' (is this booked far enough ahead?)."
                    ),
                },
                "cabin": {
                    "type": "string",
                    "description": (
                        "For an 'air' check: the cabin being asked about. One of 'economy', "
                        "'premium_economy', 'business', 'first'."
                    ),
                },
                "flight_hours": {
                    "type": "number",
                    "description": (
                        "For an 'air' check: how long the flight is, in hours. Supply this or "
                        "trip_id — prefer trip_id when the question is about a real trip, because "
                        "the tool then uses the trip's own longest flight."
                    ),
                },
                "trip_id": {
                    "type": "string",
                    "description": (
                        "For an 'air' check about an existing trip: its id, from the trips tool. "
                        "The trip does not count as its own prior history."
                    ),
                },
                "nightly_rate_amount": {
                    "type": "number",
                    "description": "For a 'hotel' check: the nightly rate as a number.",
                },
                "nightly_rate_currency": {
                    "type": "string",
                    "description": (
                        "For a 'hotel' check: the three-letter currency of the rate, e.g. 'USD'. "
                        "Omit to use the caller's own policy currency."
                    ),
                },
                "star_rating": {
                    "type": "number",
                    "description": "For a 'hotel' check: the property's star rating, 1 to 5.",
                },
                "depart_on": {
                    "type": "string",
                    "description": (
                        "For an 'advance_purchase' check: the departure date, as YYYY-MM-DD."
                    ),
                },
            },
            # Only the kind of question is required: each check needs different inputs, and the
            # tool refuses an incomplete combination rather than assuming a value. An assumed
            # threshold produces a confident answer to a question nobody asked.
            "required": ["check"],
        },
    },
]
