"""Ledger v0 — capture the numbers, not the cost.

Cost arithmetic (rates, CPRT, budgets) happens downstream. What happens *here* is the part
that **cannot be added later**: attribution. A log line without `tenant_id` is a line no
future query can rescue, so the dimensions have to be right from the first trajectory
rather than from the first invoice.

Token counts come from Strands' own `Usage`, which already carries
`cacheReadInputTokens` / `cacheWriteInputTokens` — so cache hit rate is *observed*
rather than inferred. An inferred hit rate is exactly the number a cost story cannot
afford to get wrong.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Step:
    """One model call within a trajectory."""

    index: int
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    latency_ms: int = 0
    tools_called: list[str] = field(default_factory=list)
    # Which cache TTL Bedrock actually applied, when it says so (`cacheDetails[].ttl`). Recorded
    # because the write rate depends on it — 1.25x input at five minutes, 2x at an hour — so
    # reading it back beats trusting the config to still say what it said at deploy time.
    cache_ttl: str | None = None

    @property
    def acquired_nothing(self) -> bool:
        """No tool called, so no external data entered the context on this step.

        The raw fact. Whether it counts as a wasted *reflection* depends on where the step sits
        in the trajectory, which a step cannot know about itself — see `Trajectory._reflections`.
        """
        return not self.tools_called

    def as_dict(self, *, reflection: bool | None = None) -> dict[str, Any]:
        return {
            "index": self.index,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "latency_ms": self.latency_ms,
            "tools_called": self.tools_called,
            "reflection": self.acquired_nothing if reflection is None else reflection,
            "cache_ttl": self.cache_ttl,
        }


class Trajectory:
    """Accumulates one turn's steps and emits a single structured line at the end.

    One line per trajectory rather than per step: a trajectory is the unit a business
    question is asked about ("what did this task cost?"), and per-step lines would have
    to be re-joined by anyone querying it. The steps ride along as a nested list.
    """

    def __init__(
        self,
        *,
        tenant_id: str | None,
        traveler_id: str | None,
        session_id: str | None,
        model_id: str,
        prompt_version: str,
        guardrail_id: str | None = None,
        pricer: Any = None,
    ) -> None:
        # **Injected rather than imported, so this file still knows nothing about rates.** The
        # ledger's job is facts that cannot be reconstructed later; a rate card is neither a fact
        # about the turn nor irrecoverable. Passing the pricer keeps `pricing.py` the only place a
        # dollar figure is computed, and lets these tests run without a rate table at all.
        self.pricer = pricer
        self.tenant_id = tenant_id
        self.traveler_id = traveler_id
        self.session_id = session_id
        self.model_id = model_id
        self.prompt_version = prompt_version
        # Which guardrail was in force, alongside which prompt version was in force. Both
        # answer the same question about a past turn — "what rules was it operating under?" —
        # and neither can be reconstructed after the fact.
        self.guardrail_id = guardrail_id
        self.steps: list[Step] = []
        # Categories a guardrail blocked on this turn, e.g. `["PROMPT_ATTACK"]`. Recorded
        # because "the assistant declined" and "a filter fired" look identical to a user and
        # must not look identical to us: otherwise the only evidence the control worked is
        # the absence of an answer, which is indistinguishable from the model declining on
        # its own — and an unobservable control cannot be shown to fail when removed.
        self.guardrail_blocked: list[str] = []
        # How the turn ended. **`escalated` is a resolved outcome, not a failure** — it is the
        # denominator half of cost-per-resolved-task, and treating a clean handoff as a failure
        # would make the metric reward an agent that flails on instead of one that gives up well.
        # Recorded here because a reader of one ledger line should not have to infer it from the
        # absence of something.
        self.outcome: str = "completed"
        self._started = time.perf_counter()
        self._step_started = self._started

    def start_step(self) -> Step:
        step = Step(index=len(self.steps) + 1)
        self.steps.append(step)
        self._step_started = time.perf_counter()
        return step

    @property
    def current(self) -> Step:
        """The open step, starting one if the model streamed before we saw a start."""
        return self.steps[-1] if self.steps else self.start_step()

    def record_tool(self, name: str) -> None:
        if name not in self.current.tools_called:
            self.current.tools_called.append(name)

    def record_guardrail(self, trace: dict[str, Any]) -> None:
        """Note which guardrail categories blocked, from the response trace.

        The trace nests differently per policy type (`contentPolicy.filters[]`,
        `sensitiveInformationPolicy.piiEntities[]`, `topicPolicy.topics[]`, each under
        `inputAssessment[guardrailId]` or `outputAssessments[guardrailId][]`), so rather than
        walk every documented shape — and silently miss the one that changes — this searches
        recursively for the marker Bedrock uses consistently: a dict carrying
        `action: "BLOCKED"`. The same predicate Strands itself uses to decide a turn was
        blocked, so what we log cannot disagree with how it behaved.
        """

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                if node.get("action") in ("BLOCKED", "ANONYMIZED"):
                    # `type` for a content filter or PII entity, `name` for a denied topic.
                    category = node.get("type") or node.get("name")
                    label = f"{node['action']}:{category}" if category else str(node["action"])
                    if label not in self.guardrail_blocked:
                        self.guardrail_blocked.append(label)
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(trace)

    def record_usage(self, usage: dict[str, Any] | Any) -> None:
        """Fold Strands' `Usage` into the open step.

        Accepts a dict or an object: Strands' event payloads have varied between shapes,
        and a ledger that raises on an unexpected type would take the whole turn down —
        losing the answer to save the accounting, which is the wrong trade.
        """

        def read(*names: str) -> int:
            for name in names:
                value = usage.get(name) if isinstance(usage, dict) else getattr(usage, name, None)
                if isinstance(value, int | float):
                    return int(value)
            return 0

        step = self.current
        step.input_tokens = read("inputTokens", "input_tokens")
        step.output_tokens = read("outputTokens", "output_tokens")
        step.cache_read_tokens = read("cacheReadInputTokens", "cache_read_input_tokens")
        step.cache_write_tokens = read("cacheWriteInputTokens", "cache_write_input_tokens")
        step.latency_ms = int((time.perf_counter() - self._step_started) * 1000)

        # `cacheDetails` is present on a write and absent otherwise, and Strands may not surface it
        # at all. Read opportunistically: pricing already defaults an unknown TTL to the cheaper
        # five-minute rate, so a missing field costs a slightly conservative figure, not a wrong one.
        details = usage.get("cacheDetails") if isinstance(usage, dict) else None
        if isinstance(details, list):
            for entry in details:
                if isinstance(entry, dict) and entry.get("ttl"):
                    step.cache_ttl = str(entry["ttl"])
                    break

    def _real_steps(self) -> list[Step]:
        """Steps that actually ran a model call.

        A step is opened after each usage event to receive the *next* one, so the last is
        normally empty. Counting it would inflate `reflection_steps` — reporting 2
        reflections for a clean one-tool answer — and that is the metric Ep5 leads with,
        so an off-by-one here is a wrong number in the cost story rather than a cosmetic
        bug.
        """
        return [s for s in self.steps if s.input_tokens or s.output_tokens]

    @property
    def steps_taken(self) -> int:
        """Model calls made so far. Public because the budget check needs it mid-turn."""
        return len(self._real_steps())

    @property
    def tools_tried(self) -> list[str]:
        """Every tool called this turn, in order, first occurrence only.

        Read by the handoff so a human agent is told what was already attempted, rather than the
        model's account of what was already attempted.
        """
        return list(dict.fromkeys(name for s in self._real_steps() for name in s.tools_called))

    def _reflections(self, steps: list[Step]) -> list[bool]:
        """Which steps were wasted reasoning — never the last one.

        **The last step is the answer, not a reflection.** Every turn ends with the model writing
        its reply, and writing a reply calls no tool, so a "no tool means reflection" rule counted
        the answer as waste on *every* trajectory. Two real turns from the deployment both reported
        1 reflection out of 2 steps: a 50% reflection rate for a clean one-tool answer, against a
        gate threshold of 15%. The threshold was unmeetable and the metric Ep5 leads with was
        measuring the wrong thing — it would have been read as a reflection loop that was not there.

        A genuine reflection is a step that acquired nothing *and* was followed by more work, which
        is a fact about position, so it cannot live on `Step`.
        """
        if not steps:
            return []
        return [
            step.acquired_nothing and index < len(steps) - 1 for index, step in enumerate(steps)
        ]

    def cost(self) -> dict[str, Any]:
        """The trajectory's cost, or an empty dict when no pricer was supplied.

        **Priced from the trajectory's totals rather than by summing per-step costs.** Both give
        the same answer here, but rounding each step and then adding accumulates the rounding into
        the figure the gate compares against a threshold. One rounding, at the end.
        """
        if self.pricer is None:
            return {}
        steps = self._real_steps()
        ttl = next((s.cache_ttl for s in steps if s.cache_ttl), None)
        return self.pricer(
            model_id=self.model_id,
            input_tokens=sum(s.input_tokens for s in steps),
            output_tokens=sum(s.output_tokens for s in steps),
            cache_read_tokens=sum(s.cache_read_tokens for s in steps),
            cache_write_tokens=sum(s.cache_write_tokens for s in steps),
            cache_ttl=ttl,
        )

    def as_dict(self) -> dict[str, Any]:
        steps = self._real_steps()
        reflections = self._reflections(steps)
        return {
            "event": "trajectory",
            # The attribution dimensions. Same set the audit trail and the CPRT
            # dashboard use, so one instrumentation layer serves governance, cost and
            # debugging — the throughline of the blog series.
            "tenant_id": self.tenant_id,
            "traveler_id": self.traveler_id,
            "session_id": self.session_id,
            "model_id": self.model_id,
            "prompt_version": self.prompt_version,
            "guardrail_id": self.guardrail_id,
            # Empty on a normal turn. Non-empty is the audit record that a content control
            # fired, and which one — the difference between "it refused" and "we stopped it".
            "guardrail_blocked": self.guardrail_blocked,
            "outcome": self.outcome,
            "steps": len(steps),
            "input_tokens": sum(s.input_tokens for s in steps),
            "output_tokens": sum(s.output_tokens for s in steps),
            "cache_read_tokens": sum(s.cache_read_tokens for s in steps),
            "cache_write_tokens": sum(s.cache_write_tokens for s in steps),
            "tools_called": [name for s in steps for name in s.tools_called],
            "reflection_steps": sum(reflections),
            "duration_ms": int((time.perf_counter() - self._started) * 1000),
            # Cost sits beside the tokens it was derived from, with the rate card that produced
            # it, so a figure in a report can always be traced back to both.
            **self.cost(),
            "step_detail": [
                s.as_dict(reflection=flag) for s, flag in zip(steps, reflections, strict=True)
            ],
        }

    def emit(self, log: Any) -> dict[str, Any]:
        """Write the line. Never raises — accounting must not break a conversation."""
        payload = self.as_dict()
        try:
            log.info(json.dumps(payload))
        except Exception:  # noqa: BLE001 - a failed ledger write must not fail the turn
            pass
        return payload
