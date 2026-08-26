"""What one task run produced, in the shape an evaluator reads.

Built entirely from the SSE stream the agent already emits, so scoring needs no log-read
permissions and no wait for CloudWatch to catch up. That matters more than it sounds: an offline
gate that depends on log ingestion is a gate that fails intermittently for reasons unrelated to the
change being judged, and a flaky gate gets bypassed.

**A trace records what was observed, never a judgement about it.** The evaluators decide; this only
carries evidence. Same separation as the ledger and the pricer — a structure that mixes the two
makes a failing score impossible to argue with, because the thing being judged and the judgement
live in the same field.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Result:
    """One evaluator's verdict on one trace."""

    evaluator: str
    passed: bool
    detail: str = ""

    # Set when the evaluator had nothing to judge — a task that declares no expectation for it.
    # **Distinct from passing.** Counting a skip as a pass is how a suite reports a clean sheet for
    # assertions that never ran, which is the defect this repo keeps finding in its own checks.
    skipped: bool = False

    def __str__(self) -> str:
        mark = "SKIP" if self.skipped else ("PASS" if self.passed else "FAIL")
        return f"{mark} {self.evaluator}" + (f" — {self.detail}" if self.detail else "")


@dataclass
class Trace:
    """One task, run as one persona.

    `tools_called` is in call order with the gateway's target prefix already stripped, because a
    fixture names `search_hotels` rather than `search___search_hotels` — the prefix is a deployment
    detail and a fixture that encoded it would break when a target was renamed.
    """

    task_id: str
    persona: str
    tenant_id: str
    prompt: str

    text: str = ""
    tools_called: list[str] = field(default_factory=list)
    cards: list[dict[str, Any]] = field(default_factory=list)

    # From the `done` event. `steps` and `outcome` are optional because a run that died mid-stream
    # never sent one, and a missing value must not read as zero steps.
    usage: dict[str, int] = field(default_factory=dict)
    steps: int | None = None
    outcome: str | None = None

    # Set when the turn never completed. Kept rather than raised so a broken run is scored as a
    # failure of the task instead of taking the whole suite down with it.
    error: str | None = None

    @property
    def card_types(self) -> list[str]:
        return [str(c.get("card_type")) for c in self.cards]

    def card_data(self, card_type: str) -> dict[str, Any] | None:
        """The `data` of the first card of this type, or `None`.

        **Where a verdict is read from, rather than from the prose.** A tool's `facts` never reach
        the client — `main.py` forwards only the `cards` array — but `policy_verdict` carries
        `eligible` and `reason_code` as *required* data keys, so the card is the computed verdict
        rather than the model's account of it. Reading the prose instead would score the narration
        and the computation as one thing, and the whole point of a computed verdict is that those
        two can be checked against each other.
        """
        for card in self.cards:
            if str(card.get("card_type")) == card_type:
                data = card.get("data")
                return data if isinstance(data, dict) else {}
        return None

    @classmethod
    def from_events(
        cls,
        *,
        task_id: str,
        persona: str,
        tenant_id: str,
        prompt: str,
        events: list[dict[str, Any]],
    ) -> Trace:
        """Fold the typed event stream into a trace.

        Tolerant of unknown event types on purpose: the envelope gains events over time, and a
        harness that raised on one it did not recognise would fail on the day the agent got a new
        capability rather than on the day it got worse.
        """
        trace = cls(task_id=task_id, persona=persona, tenant_id=tenant_id, prompt=prompt)
        chunks: list[str] = []
        for event in events:
            kind = event.get("type")
            if kind == "text":
                chunks.append(str(event.get("text") or ""))
            elif kind == "tool_start":
                name = str(event.get("tool") or "")
                if name:
                    trace.tools_called.append(name)
            elif kind == "cards":
                trace.cards.extend(c for c in (event.get("cards") or []) if isinstance(c, dict))
            elif kind == "done":
                trace.usage = event.get("usage") or {}
                trace.steps = event.get("steps")
                trace.outcome = event.get("outcome")
            elif kind == "error":
                trace.error = str(event.get("message") or "stream error")
        trace.text = "".join(chunks)
        return trace
