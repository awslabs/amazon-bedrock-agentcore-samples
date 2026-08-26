"""Tool schemas for the profile family — the single source of truth.

`traveler_name` is the first argument in the catalog that lets a caller act on **someone
else's** behalf, which is why two authorization layers converge on this tool:

- **Cedar** (`policies/arranger.cedar`) refuses the argument outright unless the caller's
  `custom:role` claim is `arranger`. Static, declarative, and evaluated before the Lambda
  runs.
- **The tool** resolves the name within the caller's authorised scope and re-checks
  `can_book_for` against the backend. Dynamic, because the answer changes without a deploy.

Neither is redundant: Cedar cannot query DynamoDB, and the backend cannot see a JWT claim.
"""

from typing import Any

GET_TRAVELER_PROFILE = "get_traveler_profile"

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": GET_TRAVELER_PROFILE,
        "label": "Looking up traveller details",
        "description": (
            "Get a traveller's saved travel details: home airport, seat and cabin "
            "preferences, preferred hotel chains, loyalty programme names and tiers, "
            "passport issuing country, and which payment method is on file. Returns the "
            "caller's own profile by default. Never returns passport numbers, loyalty "
            "numbers or card numbers — those are not available to you at all."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "traveler_name": {
                    "type": "string",
                    "description": (
                        "Only when looking up someone else's profile on their behalf — "
                        "the name as the user said it, full or partial. Omit for the "
                        "caller's own profile. If more than one person matches, the tool "
                        "returns the candidates so you can ask which; never guess."
                    ),
                }
            },
            "required": [],
        },
    }
]
