"""Tool schemas for the trips family — the single source of truth.

Two constraints shape everything here, and both are load-bearing rather than stylistic:

**No tenant, no traveller id.** Identity is injected from verified claims, so it never appears as an
input. `traveler_name` exists because an *arranger* legitimately acts for someone else — but it is a
name the user said, resolved server-side within the caller's authorised scope, never an id the model
chose.

**No `enum`.** The Gateway's `inlinePayload` supports only
`type`/`properties`/`required`/`items`/`description`, so a closed set rides in the description and
the tool refuses unknown values itself. Declaring an `enum` here fails at target registration, not
at synth.
"""

from typing import Any

GET_TRIPS = "get_trips"

# Closed set, enforced in code rather than by the schema. Named here so the handler and the
# description cannot drift apart.
WINDOWS = ("past", "upcoming", "in_progress")

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": GET_TRIPS,
        "label": "Looking up your trips",
        "description": (
            "Get a traveller's trips — past, upcoming, or the one currently in progress — with "
            "destination, dates, flights and hotels. Use this for any question that depends on "
            "where someone is or has been: 'which hotel am I in?', 'when do I fly home?', 'how "
            "many international trips have I taken?'. Also call it first when a request refers to "
            "somewhere the traveller already is or is going, because it returns the addresses the "
            "nearby-places and directions tools need."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "window": {
                    "type": "string",
                    "description": (
                        "Which trips to return. One of: 'past' (completed), 'upcoming' (not "
                        "started), 'in_progress' (happening now). Omit for all of them — do that "
                        "when the question is open-ended, and prefer 'in_progress' for 'where am "
                        "I staying?' style questions. **Omit it when the traveller names a "
                        "particular trip, city or hotel**: a trip that is happening right now is "
                        "neither upcoming nor past, so filtering makes an existing trip look "
                        "missing. Never conclude a trip does not exist from a filtered result — "
                        "call again with no window before saying you cannot find it."
                    ),
                },
                "traveler_name": {
                    "type": "string",
                    "description": (
                        "Only when looking up someone else's trips on their behalf — the name as "
                        "the user said it, full or partial. Omit for the caller's own trips. If "
                        "more than one person matches, the tool returns the candidates so you can "
                        "ask which; never guess."
                    ),
                },
            },
            # Nothing required: "what are my trips?" is the commonest phrasing, and forcing a
            # window would make the model invent one.
            "required": [],
        },
    }
]
