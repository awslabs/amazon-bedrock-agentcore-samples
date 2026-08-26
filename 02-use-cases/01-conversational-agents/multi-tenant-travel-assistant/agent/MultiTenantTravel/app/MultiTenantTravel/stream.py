"""The typed stream envelope.

Strands emits far more than text — `ToolUseStreamEvent`, `ToolResultEvent`,
`EventLoopStopEvent` with `EventLoopMetrics`, and a `Usage` carrying cache counters. The
scaffolded entrypoint kept `event["data"]` and discarded all of it.

That discard is why this module exists at all: information dropped at the source cannot be
recovered by the frontend later. **One stream, three consumers** — the UI's tool-status
indicator, the cost ledger, and the trajectory trace.

Deliberately not streamed:
- **tool arguments** — they can carry a traveller's name, and names do not belong in logs
  or in a channel the frontend may persist;
- **reasoning text** — available, and dropped: exposing chain-of-thought is a product
  decision this sample need not take, and it bloats the stored transcript;
- **tool result prose** — `message`, `facts` and `provenance` are the *model's* inputs. It
  narrates from them, so forwarding them too would give the UI two sources for one fact and
  let the tile and the sentence disagree.

**Cards are the exception, and they have to be.** They travel in the tool's response — a
channel that terminates at the model — so a card that is not forwarded reaches nothing that
can draw it. An earlier note here said cards "travel in the tool response" as a reason *not*
to stream them; that was true of the transport and wrong about the destination, and the
symptom was a UI that rendered prose and never a tile.

So `cards` events carry the `cards` array out of each tool result and nothing else from it.
The model still receives the whole envelope, unchanged.
"""

from __future__ import annotations

import json
from typing import Any

# Loaded from the generated file so a label is never duplicated. Falls back to a
# best-effort prettifier: a missing label should degrade the pill's wording, never break
# the turn.
_LABELS: dict[str, str] = {}


def load_labels(path: str | None = None) -> dict[str, str]:
    """Read `tools/tool-labels.json`, exported from the tool schemas."""
    global _LABELS
    if _LABELS:
        return _LABELS
    if path:
        try:
            with open(path) as handle:
                _LABELS = json.load(handle)
        except (OSError, json.JSONDecodeError):
            _LABELS = {}
    return _LABELS


def label_for(tool_name: str) -> str:
    """Human-readable status for a tool.

    Server-authored, never model-authored: a model asked to narrate its own routing will
    eventually narrate it wrongly, and `get_travel_policy` in a status pill reads as an
    implementation leak.
    """
    if labelled := load_labels().get(tool_name):
        return labelled
    # `search_hotels` -> "Search hotels". Not as good as a written label, but it never
    # shows a raw identifier to a user.
    return tool_name.replace("_", " ").capitalize()


def text(chunk: str) -> dict[str, Any]:
    return {"type": "text", "text": chunk}


def tool_start(tool_name: str, use_id: str | None = None) -> dict[str, Any]:
    return {
        "type": "tool_start",
        "tool": tool_name,
        "label": label_for(tool_name),
        # Correlates with `tool_end` so the UI resolves the right pending pill when two
        # tools run in one step, rather than guessing.
        "id": use_id,
    }


def tool_end(tool_name: str, use_id: str | None = None, *, ok: bool = True) -> dict[str, Any]:
    # `ok` rather than an error string: a failed tool already returns a clean `{message}`
    # in its response, and duplicating the text here would give the UI two sources.
    return {"type": "tool_end", "tool": tool_name, "id": use_id, "ok": ok}


def cards(built: list[dict[str, Any]]) -> dict[str, Any]:
    """The cards a tool returned, forwarded for rendering.

    Only the `cards` array — never `message`, `facts` or `provenance`, which are the model's
    inputs to narrate from. Sending those as well is how a tile and the sentence beside it
    come to disagree.
    """
    return {"type": "cards", "cards": built}


def payloads_in(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Parsed tool-response envelopes from one result block.

    The tool's `{cards, facts, message, provenance}` envelope arrives JSON-encoded inside a
    `{"text": ...}` content block — that is how the MCP client maps text content, so the JSON
    has to be parsed back out rather than read as a field.

    Never raises: an unparseable tool result should cost structured handling, not the turn.
    """
    found: list[dict[str, Any]] = []
    for block in result.get("content") or []:
        text = block.get("text") if isinstance(block, dict) else None
        if not text:
            continue
        try:
            payload = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(payload, dict):
            found.append(payload)
    return found


def cards_in(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Cards from one tool result block, or an empty list."""
    found: list[dict[str, Any]] = []
    for payload in payloads_in(result):
        if isinstance(payload.get("cards"), list):
            found.extend(card for card in payload["cards"] if isinstance(card, dict))
    return found


def guardrail(categories: list[str]) -> dict[str, Any]:
    """A content guardrail intervened on this turn.

    Sent so the UI can say *why* an answer stopped instead of showing a reply that trails
    off. The categories travel with it because "blocked" alone leaves a user unable to tell a
    safety filter from a broken connection, and those call for different reactions.
    """
    return {"type": "guardrail", "categories": categories}


def done(
    usage: dict[str, Any] | None = None,
    *,
    steps: int | None = None,
    outcome: str | None = None,
) -> dict[str, Any]:
    """The turn is settled, and here is what it took.

    **`steps` and `outcome` ride along so the eval harness needs nothing but the stream.** Token
    counts were already here; these are the same category of fact — this turn's own accounting — and
    without them the runner would have to read the ledger out of CloudWatch per task to check a step
    threshold, which turns an offline gate into one that needs log-read permissions and a wait.

    Cost deliberately does **not** travel. A client can be told how much work its own turn took; a
    dollar figure is the tenant's commercial data, and the runner can price these counts itself from
    the same rate card the agent used.
    """
    settled: dict[str, Any] = {"type": "done", "usage": usage or {}}
    if steps is not None:
        settled["steps"] = steps
    if outcome is not None:
        settled["outcome"] = outcome
    return settled


def strip_target_prefix(tool_name: str) -> str:
    """`policy___get_travel_policy` -> `get_travel_policy`.

    The Gateway prefixes tool names with the target name. Users must never see it, and the
    label lookup is keyed on the bare name.
    """
    _, _, bare = tool_name.rpartition("___")
    return bare or tool_name
