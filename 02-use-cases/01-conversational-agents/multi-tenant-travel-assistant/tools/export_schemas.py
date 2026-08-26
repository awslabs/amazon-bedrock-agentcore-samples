"""Export tool schemas to the JSON files the Gateway target registration reads.

    uv run python -m tools.export_schemas

**Generated, never hand-edited.** `schemas.py` in each family is the single source of
truth: the Python handler validates against it and the Gateway advertises it, so two
hand-maintained copies would drift — and the drift is invisible until the model calls a
tool with an argument the handler does not accept.

`agentcore.json`'s `lambdaFunctionArn` target takes a `toolSchemaFile` path, which is why
these files have to exist on disk rather than being passed inline.

The `label` is stripped on the way out. It is a **UI** concern (the frontend's status
pill) that lives beside the description so one file owns everything about a tool, but the
Gateway's `inlinePayload` accepts only `type`/`properties`/`required`/`items`/
`description` — an unexpected key fails at target registration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.booking.schemas import TOOL_DEFINITIONS as BOOKING_TOOLS
from tools.entry.schemas import TOOL_DEFINITIONS as ENTRY_TOOLS
from tools.escalation.schemas import TOOL_DEFINITIONS as ESCALATION_TOOLS
from tools.knowledge.schemas import TOOL_DEFINITIONS as KNOWLEDGE_TOOLS
from tools.location.schemas import TOOL_DEFINITIONS as LOCATION_TOOLS
from tools.policy.schemas import TOOL_DEFINITIONS as POLICY_TOOLS
from tools.profile.schemas import TOOL_DEFINITIONS as PROFILE_TOOLS
from tools.search.schemas import TOOL_DEFINITIONS as SEARCH_TOOLS
from tools.trips.schemas import TOOL_DEFINITIONS as TRIPS_TOOLS

TOOLS_DIR = Path(__file__).parent

# family → the definitions that family's Lambda serves.
FAMILIES: dict[str, list[dict[str, Any]]] = {
    "policy": POLICY_TOOLS,
    "profile": PROFILE_TOOLS,
    "knowledge": KNOWLEDGE_TOOLS,
    "trips": TRIPS_TOOLS,
    "search": SEARCH_TOOLS,
    "booking": BOOKING_TOOLS,
    "entry": ENTRY_TOOLS,
    "location": LOCATION_TOOLS,
    "escalation": ESCALATION_TOOLS,
}

# Keys the Gateway accepts on a tool definition. Anything else is ours and is stripped.
GATEWAY_KEYS = {"name", "description", "inputSchema", "outputSchema"}


def gateway_definition(tool: dict[str, Any]) -> dict[str, Any]:
    """Strip our own metadata, keeping only what the Gateway understands."""
    return {k: v for k, v in tool.items() if k in GATEWAY_KEYS}


def export() -> list[Path]:
    written = []
    for family, tools in FAMILIES.items():
        path = TOOLS_DIR / family / "tool-schema.json"
        payload = [gateway_definition(tool) for tool in tools]
        path.write_text(json.dumps(payload, indent=2) + "\n")
        written.append(path)
        print(f"  {path.relative_to(TOOLS_DIR.parent)} — {len(payload)} tool(s)")
    return written


def labels() -> dict[str, str]:
    """Tool name → human-readable status label, for the frontend and the ledger.

    Exported separately because it is a different contract with a different consumer:
    the Gateway must not see it, and the UI must never fall back to a raw tool name.
    """
    return {
        tool["name"]: tool["label"]
        for tools in FAMILIES.values()
        for tool in tools
        if tool.get("label")
    }


def export_labels() -> Path:
    path = TOOLS_DIR / "tool-labels.json"
    path.write_text(json.dumps(labels(), indent=2, sort_keys=True) + "\n")
    print(f"  {path.relative_to(TOOLS_DIR.parent)} — {len(labels())} label(s)")
    return path


if __name__ == "__main__":
    print("Exporting Gateway tool schemas...")
    export()
    export_labels()
