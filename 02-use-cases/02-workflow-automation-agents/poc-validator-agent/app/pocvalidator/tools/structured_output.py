"""Structured output tools.

Adapted from event-driven-claims-agent/app/claimsagent/tools/structured_output.py.

Agents submit results as typed tool calls rather than emitting text the
orchestrator has to parse with regex. Two things follow from that: the shape is
enforced at the tool boundary, and a malformed result is a missing tool call
rather than a silently mis-parsed one.

Concurrency note, carried over from the reference sample: state is module-level
and reset per invocation via ``reset_state()``. That assumes a single in-flight
invocation per process, which is the AgentCore Runtime model. It is NOT safe for
concurrent invocations sharing one container.
"""

import json

from strands import tool

_last_extraction: dict = {}
_last_sow_bands: dict = {}


def get_last_extraction() -> dict:
    """What the vision agent reported seeing on the uploaded diagram."""
    return dict(_last_extraction)


def get_last_sow_bands() -> dict:
    """Criterion id -> {band, justification} from the SOW classifier."""
    return dict(_last_sow_bands)


def reset_state() -> None:
    """Reset captured state between invocations."""
    global _last_extraction, _last_sow_bands
    _last_extraction = {}
    _last_sow_bands = {}


def record_extraction(services, edges, notes: str = "") -> str:
    """Plain implementation, separated from the @tool wrapper so it can be
    unit-tested without constructing an Agent. Strands wraps decorated tools in
    a DecoratedFunctionTool that does not expose the underlying callable."""
    global _last_extraction

    def _parse(raw, fallback):
        if isinstance(raw, (list, dict)):
            return raw
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return fallback

    _last_extraction = {
        "services": _parse(services, []),
        "edges": _parse(edges, []),
        "notes": notes,
    }
    count = len(_last_extraction["services"])
    return f"Extraction recorded: {count} services, {len(_last_extraction['edges'])} edges."


def record_sow_assessment(assessments) -> str:
    """Plain implementation behind the submit_sow_assessment tool."""
    global _last_sow_bands

    payload = assessments
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            return "Could not parse assessments — expected a JSON array."

    if not isinstance(payload, list):
        return "Could not parse assessments — expected a JSON array."

    captured = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        criterion_id = item.get("id")
        band = item.get("band")
        # Reject rather than clamp. A band of 9 means the model misunderstood
        # the scale, and silently rewriting it to 4 would hide that.
        if not criterion_id or not isinstance(band, int) or not 0 <= band <= 4:
            continue
        captured[str(criterion_id)] = {
            "band": band,
            "justification": str(item.get("justification", "")),
        }

    _last_sow_bands = captured
    return f"Recorded bands for {len(captured)} criteria."


@tool
def submit_extraction(services: str, edges: str, notes: str = "") -> str:
    """Submit the AWS services and connections you identified in the diagram.

    Call this ONCE after examining the uploaded architecture diagram.

    Report only what you can actually see. If a box is unlabelled or you cannot
    tell which AWS service it represents, include your best reading of its label
    in `services` anyway — an unmatched label is shown to the user for
    correction, which is far more useful than a confident wrong guess or a
    silent omission.

    Args:
        services: JSON array of service names as they appear on the diagram,
            e.g. ["CloudFront", "Application Load Balancer", "RDS PostgreSQL"].
        edges: JSON array of connections, each {"from": "...", "to": "..."},
            using the same names as `services`. Direction follows the arrow on
            the diagram, or the data flow where arrows are absent.
        notes: Anything ambiguous — unreadable labels, boxes without arrows,
            annotations you could not interpret.
    """
    return record_extraction(services, edges, notes)


@tool
def submit_sow_assessment(assessments: str) -> str:
    """Submit your band for each Scope of Work criterion.

    Band each criterion 0-4 and justify it in one sentence quoting or
    paraphrasing the document. Do NOT compute a total score — the weighted
    roll-up is done deterministically outside the model, so a total you produce
    would be discarded.

    Args:
        assessments: JSON array of objects, each
            {"id": "SOW-03", "band": 0-4, "justification": "..."}.
            Bands: 0 Absent, 1 Mentioned, 2 Partial, 3 Adequate, 4 Strong.
    """
    return record_sow_assessment(assessments)
