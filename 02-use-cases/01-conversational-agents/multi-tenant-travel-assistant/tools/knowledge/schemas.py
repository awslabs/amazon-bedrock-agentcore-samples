"""Tool schema for the knowledge family — the single source of truth.

**Notably absent: any filter argument.** The tenant filter is built server-side from verified
context, because a retrieval filter the model can name is not a filter at all — a
prompt-injected model would simply ask for another tenant's documents. Verified against the
live index: the same query filtered to `initech` returns Initech's prose, so the *only* thing
preventing cross-tenant retrieval is who chooses the filter.
"""

from typing import Any

SEARCH_POLICY_KNOWLEDGE = "search_policy_knowledge"

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": SEARCH_POLICY_KNOWLEDGE,
        "label": "Searching your policy documents",
        "description": (
            "Search the company's written travel policy documents for guidance that is not "
            "in the structured policy: exceptions, approval chains, what to do in unusual "
            "situations, and the reasoning behind a rule. Use this for open questions like "
            "'can I expense breakfast?', 'what if every hotel is over the cap?' or 'who "
            "approves an upgrade for a medical reason?'. For fixed figures — nightly caps, "
            "star limits, cabin rules — use the travel policy tool instead, which returns "
            "them exactly. Answers here are quoted passages with citations; state what the "
            "documents say and cite them, and never fill a gap with your own assumption."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": (
                        "The user's question in their own words. Retrieval is semantic, so a "
                        "natural phrasing works better than keywords."
                    ),
                }
            },
            "required": ["question"],
        },
    }
]
