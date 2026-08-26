"""Turn a pile of results into a merge decision.

Pure functions over already-collected data, deliberately: the arithmetic that decides whether a
change ships is the last thing that should need a deployment to exercise. Everything here is tested
offline, and the part that spends money is a thin client elsewhere.

**Cost per resolved task is computed here, not recorded in the ledger.** Phase 7's design left that
open and leaned towards Athena. It belongs wherever "resolved" is decided, and that is
here — the ledger records facts, and whether a task was resolved is a judgement made by evaluators.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Rows whose threshold is a floor rather than a ceiling are written `min:`; the rest are `max:`.
# Kept as data so a new row needs no code change, and so a row with neither is an error rather than
# a silently unenforced line.


@dataclass
class Score:
    """One quality row: how many runs the evaluator passed, out of how many it judged."""

    passed: int = 0
    judged: int = 0

    @property
    def rate(self) -> float | None:
        """`None` when nothing was judged, which is not the same as 1.0.

        A row nothing exercised cannot be compared against a threshold, and treating it as a perfect
        score is how a gate reports green for an evaluator that never ran.
        """
        return self.passed / self.judged if self.judged else None


@dataclass
class Aggregate:
    """Everything the gate compares, gathered from the run."""

    scores: dict[str, Score] = field(default_factory=dict)
    trajectory_usd: list[float] = field(default_factory=list)
    steps: list[int] = field(default_factory=list)
    cache_read_tokens: int = 0
    fresh_input_tokens: int = 0
    reflection_steps: int = 0
    total_steps: int = 0
    resolved: int = 0
    unresolved: int = 0
    skipped_tasks: dict[str, str] = field(default_factory=dict)
    unpriced_runs: int = 0

    @property
    def spend(self) -> float:
        return round(sum(self.trajectory_usd), 6)

    @property
    def usd_per_resolved(self) -> float | None:
        """The headline. `None` when nothing resolved — dividing by zero is not a cheap run."""
        return round(self.spend / self.resolved, 6) if self.resolved else None

    @property
    def cache_hit_rate(self) -> float | None:
        """Cached input as a share of all input tokens.

        Both counters come from the SDK, so this is observed rather than inferred — an inferred hit
        rate is exactly the number a cost story cannot afford to get wrong.
        """
        total = self.cache_read_tokens + self.fresh_input_tokens
        return round(self.cache_read_tokens / total, 4) if total else None

    @property
    def reflection_step_rate(self) -> float | None:
        return round(self.reflection_steps / self.total_steps, 4) if self.total_steps else None


def percentile(values: list[float], p: float) -> float | None:
    """Nearest-rank percentile, or `None` for an empty list.

    Nearest-rank rather than interpolated: with 58 runs the difference is noise, and an integer
    index into sorted observations is a number someone can check against the printed run list.
    """
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(p * (len(ordered) - 1))))
    return ordered[index]


def aggregate(runs: list[dict[str, Any]]) -> Aggregate:
    """Fold per-run records into the shape the gate reads.

    A run record is `{results: [Result-like], usage, steps, usd, reflection_steps, resolved}`.
    Deliberately plain dicts: the runner builds them, the tests build them, and neither needs to
    import the other.
    """
    agg = Aggregate()
    for run in runs:
        if reason := run.get("skipped"):
            agg.skipped_tasks[run["task_id"]] = reason
            continue

        for result in run.get("results", []):
            if result.get("skipped"):
                continue
            score = agg.scores.setdefault(result["evaluator"], Score())
            score.judged += 1
            score.passed += 1 if result.get("passed") else 0

        usd = run.get("usd")
        if usd is None:
            # An unpriced run is a hole in the cost figure. Counted so the gate can refuse to
            # publish a cost verdict computed from partial data, rather than quietly averaging over
            # the runs that happened to have a rate card.
            agg.unpriced_runs += 1
        else:
            agg.trajectory_usd.append(usd)

        usage = run.get("usage") or {}
        agg.cache_read_tokens += int(usage.get("cache_read") or 0)
        agg.fresh_input_tokens += int(usage.get("input") or 0)

        if (steps := run.get("steps")) is not None:
            agg.steps.append(int(steps))
            agg.total_steps += int(steps)
        agg.reflection_steps += int(run.get("reflection_steps") or 0)

        if run.get("resolved"):
            agg.resolved += 1
        else:
            agg.unresolved += 1
    return agg


@dataclass
class Row:
    """One threshold, and what the run actually measured against it."""

    name: str
    threshold: float
    bound: str  # "min" or "max"
    observed: float | None

    @property
    def passed(self) -> bool:
        """**A row with nothing observed does not pass.**

        This is the whole reason the gate is not a dict comprehension. `None` means the run produced
        no measurement for this row — no task exercised the evaluator, or nothing resolved so there
        is no cost per resolved task. Comparing `None` as though it were a satisfying value is how a
        gate goes green on a run that measured nothing, and every instance of that defect found in
        this repo looked exactly this innocent.
        """
        if self.observed is None:
            return False
        return (
            self.observed >= self.threshold
            if self.bound == "min"
            else self.observed <= self.threshold
        )

    def __str__(self) -> str:
        if self.observed is None:
            return f"  FAIL  {self.name}: nothing measured (needs {self.bound} {self.threshold})"
        mark = "PASS" if self.passed else "FAIL"
        return f"  {mark}  {self.name}: {self.observed} ({self.bound} {self.threshold})"


def rows(config: dict[str, Any], agg: Aggregate) -> list[Row]:
    """Every threshold in the config, paired with what the run observed against it.

    **There used to be a tier mechanism here**, so four LLM-judged rows could be declared but only
    evaluated under `--tier full`. Nothing computed those four, so `--tier full` reported them as
    unmeasured — correctly, per `Row.passed` — which left the flag unable to succeed on any run.
    Rows, flag and mechanism are gone; `gate.yaml` records what bringing them back would take.
    """
    observed: dict[str, float | None] = {
        "usd_per_resolved": agg.usd_per_resolved,
        "p95_usd_trajectory": percentile(agg.trajectory_usd, 0.95),
        "p50_steps": percentile([float(s) for s in agg.steps], 0.50),
        "p95_steps": percentile([float(s) for s in agg.steps], 0.95),
        "cache_hit_rate": agg.cache_hit_rate,
        "reflection_step_rate": agg.reflection_step_rate,
    }

    built: list[Row] = []
    for section in ("quality", "escalation", "cost"):
        for name, spec in (config.get(section) or {}).items():
            if not isinstance(spec, dict):
                continue
            bound = "min" if "min" in spec else "max"
            if bound not in spec:
                raise ValueError(
                    f"gate row {name!r} has neither a min nor a max, so it enforces nothing"
                )
            value = observed[name] if name in observed else _score_rate(agg, name)
            built.append(
                Row(
                    name=name,
                    threshold=float(spec[bound]),
                    bound=bound,
                    observed=value,
                )
            )
    return built


def _score_rate(agg: Aggregate, name: str) -> float | None:
    score = agg.scores.get(name)
    return score.rate if score else None


@dataclass
class Decision:
    rows: list[Row]
    aggregate: Aggregate
    stopped: str | None = None

    # Set when `--suite` or `--sample` narrowed the run. **A subset gives no merge verdict**, for
    # the same reason a stopped run does not: rows the subset could not exercise are unmeasured, and
    # reporting those as failures buries the real result in noise while reporting them as passes
    # would make `--sample 1` the cheapest way to a green gate.
    partial: str | None = None

    @property
    def failures(self) -> list[Row]:
        return [r for r in self.rows if not r.passed]

    @property
    def passed(self) -> bool:
        """**A stopped or partial run never passes**, whatever the rows say.

        Hitting the spend ceiling aborts partway through, so the results describe a subset nobody
        chose. Letting that report green would make the ceiling a way to get a passing gate cheaply,
        and `--sample 1` an even cheaper one.
        """
        return not self.stopped and not self.partial and not self.failures and bool(self.rows)

    def report(self) -> str:
        agg = self.aggregate
        lines = ["Gate"]
        for row in self.rows:
            # In a partial run an unmeasured row means "this subset did not cover it", which is a
            # different statement from "the full set measured nothing" and should not read as a
            # failure of the agent.
            if self.partial and row.observed is None:
                lines.append(f"  n/a   {row.name}: not covered by this subset")
            else:
                lines.append(str(row))

        lines.append("")
        lines.append(
            f"resolved {agg.resolved}/{agg.resolved + agg.unresolved} · spend ${agg.spend:.4f}"
            + (
                f" · ${agg.usd_per_resolved:.4f} per resolved task"
                if agg.usd_per_resolved is not None
                else " · no cost per resolved task (nothing resolved)"
            )
        )
        if agg.unpriced_runs:
            lines.append(
                f"  {agg.unpriced_runs} run(s) were unpriced, so the cost rows above cover only "
                "the priced ones"
            )
        if agg.skipped_tasks:
            lines.append(f"  {len(agg.skipped_tasks)} task(s) skipped, and why:")
            lines += [
                f"    {task}: {why.strip()}" for task, why in sorted(agg.skipped_tasks.items())
            ]
        if self.stopped:
            lines.append(f"\nSTOPPED: {self.stopped}")
            lines.append("  No verdict — an aborted run has proven nothing about quality.")
        elif self.partial:
            lines.append(f"\nPARTIAL: {self.partial}")
            lines.append("  No merge verdict from a subset. Run the whole set to gate.")
        elif not self.rows:
            lines.append("\nNo thresholds applied, so there is no verdict to give.")
        return "\n".join(lines)


def decide(
    config: dict[str, Any],
    agg: Aggregate,
    *,
    stopped: str | None = None,
    partial: str | None = None,
) -> Decision:
    return Decision(
        rows=rows(config, agg),
        aggregate=agg,
        stopped=stopped,
        partial=partial,
    )
