"""Tool schema for the entry-requirements family — the single source of truth.

One input: where they are going. **The passport country is deliberately absent** — it is read
server-side from the traveller's profile, because it is PII the model has no need to handle and
because a caller who could supply it could get an answer for the wrong document.
"""

from typing import Any

CHECK_ENTRY_REQUIREMENTS = "check_entry_requirements"

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": CHECK_ENTRY_REQUIREMENTS,
        "label": "Checking entry requirements",
        "description": (
            "Check whether the traveller needs a visa to enter a country, based on the passport on "
            "their profile. Use for 'do I need a visa for…', 'can I just fly to…', and before "
            "recommending an international trip. The answer always carries a disclaimer, and if "
            "there are no rules on file it says so — treat that as *unknown*, never as "
            "'no visa needed'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "destination_country": {
                    "type": "string",
                    "description": (
                        "The destination country as a two-letter ISO code, e.g. 'IN' for India, "
                        "'GB' for the United Kingdom. Convert a country name to its code before "
                        "calling."
                    ),
                },
                "traveler_name": {
                    "type": "string",
                    "description": (
                        "Only when checking for someone else — the name as the user said it. Omit "
                        "for the caller."
                    ),
                },
            },
            "required": ["destination_country"],
        },
    }
]
