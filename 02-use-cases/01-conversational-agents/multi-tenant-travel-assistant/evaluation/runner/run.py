"""Run the task set against a deployment, score it, and decide whether it may merge.

    ./run-evals.sh                      # the six code-based evaluators; no model spend beyond turns
    ./run-evals.sh --suite B --suite F  # one or two suites while iterating
    ./run-evals.sh --sample 5           # five tasks per suite

**The spend ceiling is the important flag, and it defaults on.** Per-run cost is not the risk —
one team reports a $3,900 overnight bill from a suite with no ceiling after a bot opened 41 pull
requests and the merge queue re-ran everything on every push — roughly 270 unattended runs, at a
per-run cost nobody would have questioned. This prices each trajectory as it finishes and stops
when the ceiling is reached, and a stopped run gives no verdict at all.

Everything that decides anything lives in `gate.py` and is tested offline. This module is the part
that needs a deployment, kept as thin as that split allows.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys
import time
from typing import Any

import yaml

HERE = pathlib.Path(__file__).resolve().parent
EVALUATION = HERE.parent
REPO_ROOT = EVALUATION.parent
for path in (str(EVALUATION), str(REPO_ROOT / "scripts")):
    if path not in sys.path:
        sys.path.insert(0, path)

from evaluators import Trace, evaluate  # noqa: E402
from runner.gate import aggregate, decide  # noqa: E402

# The agent's own pricer, loaded by path. **Not reimplemented**: a second rate table is how a cost
# report and a bill come to disagree, and the agent does not bundle `shared/` so there is no package
# boundary to import across. Same technique the conversation-API suite uses for the BFF's crypto.
_pricing_spec = importlib.util.spec_from_file_location(
    "agent_pricing",
    REPO_ROOT / "agent" / "MultiTenantTravel" / "app" / "MultiTenantTravel" / "pricing.py",
)
pricing = importlib.util.module_from_spec(_pricing_spec)
_pricing_spec.loader.exec_module(pricing)

# Resolved from `backend/seed/travelers.py`. A persona is how a fixture names a tenant.
PERSONA_TENANTS = {"priya": "globex", "adaeze": "globex", "sam": "initech"}


def load_tasks(
    *, suites: list[str] | None = None, sample: int | None = None
) -> list[tuple[dict, dict]]:
    """`(suite, task)` pairs, filtered and sampled.

    Sampling takes the **first** n of a suite rather than a random n: a gate that judges a different
    subset on every run cannot tell a regression from a reshuffle, and the point of a sample is to
    iterate quickly, not to explore.
    """
    pairs: list[tuple[dict, dict]] = []
    for path in sorted((EVALUATION / "tasks").glob("*.yaml")):
        suite = yaml.safe_load(path.read_text())
        if suites and suite["suite"] not in suites:
            continue
        tasks = suite["tasks"][:sample] if sample else suite["tasks"]
        pairs += [(suite, task) for task in tasks]
    return pairs


def price_trace(trace: Trace, model_id: str) -> float | None:
    """What this run cost, from the token counts the stream reported."""
    usage = trace.usage or {}
    priced = pricing.price(
        model_id=model_id,
        input_tokens=int(usage.get("input") or 0),
        output_tokens=int(usage.get("output") or 0),
        cache_read_tokens=int(usage.get("cache_read") or 0),
        cache_write_tokens=int(usage.get("cache_write") or 0),
    )
    return priced.get("usd")


def resolved(task: dict, results: list[Any], trace: Trace) -> bool:
    """Whether this run counts in the denominator of cost per resolved task.

    **An escalation is resolved**, which `evaluation/tasks/e-escalation.yaml` states as that suite's
    definition of resolved. The reason is that a metric which scored a clean handoff as a failure
    would reward an agent that flails on over one that gives up well.

    Everything the task asserted had to hold. A run with an unmeasured expectation is not resolved:
    it is a run whose outcome nobody established.
    """
    if trace.error:
        return False
    judged = [r for r in results if not r.skipped]
    return bool(judged) and all(r.passed for r in judged)


# **The fixture's scenario name is narrative; the backend's is mechanical.** A task says
# `price_drift_upward` because that is what a reader needs to know is being tested, while the
# backend knows `price_drift` — direction is not a separate mode. Mapped rather than renamed on
# either side: the fixtures are documentation for a reader who never opens the generator, and the
# generator should not carry a name that describes an eval.
#
# `replayed_stale_reference` maps to nothing on purpose. Replaying a handle that never existed needs
# no simulation — the ordinary path already refuses it, and that is the point of the task.
SCENARIO_NAMES = {
    "price_drift_upward": "price_drift",
    "hold_expired": "expired_offer",
    "zero_availability": "no_availability",
    "backend_timeout": "timeout",
    "policy_cap_lowered_midsession": "policy_cap_lowered",
    "replayed_stale_reference": None,
}


def scenarios_for(task: dict) -> set[str] | None:
    """Backend scenario names for a task, or `None` when it needs no simulation.

    An unrecognised name is an error rather than a silent no-op: a task that believes it is testing
    drift while the backend behaves normally would pass for the wrong reason, which is worse than a
    task that fails.
    """
    name = task.get("scenario")
    if not name:
        return None
    if name not in SCENARIO_NAMES:
        raise SystemExit(
            f"task {task['id']} names an unknown scenario {name!r}. "
            f"Known: {', '.join(sorted(SCENARIO_NAMES))}"
        )
    mapped = SCENARIO_NAMES[name]
    return {mapped} if mapped else None


def run_task(
    client: Any, suite: dict, task: dict, persona: str, *, model_id: str
) -> dict[str, Any]:
    """One task, one persona: invoke, fold into a trace, score, price."""
    tenant = PERSONA_TENANTS[persona]
    try:
        events = client.turn(
            persona=persona,
            prompt=task["prompt"],
            scenarios=scenarios_for(task),
            tenant_id=tenant,
        )
    except Exception as error:  # noqa: BLE001 - one broken task must not end the run
        events = [{"type": "error", "message": f"{type(error).__name__}: {error}"}]

    trace = Trace.from_events(
        task_id=task["id"],
        persona=persona,
        tenant_id=tenant,
        prompt=task["prompt"],
        events=events,
    )
    results = evaluate(task, trace)
    return {
        "task_id": f"{task['id']}/{persona}",
        "suite": suite["suite"],
        "results": [
            {"evaluator": r.evaluator, "passed": r.passed, "skipped": r.skipped, "detail": r.detail}
            for r in results
        ],
        "usage": trace.usage,
        "steps": trace.steps,
        "usd": price_trace(trace, model_id),
        "reflection_steps": 0,  # not on the stream; the ledger owns it, and the gate reads 0 rather
        # than guessing — see the note in `report()` about partial cost data
        "resolved": resolved(task, results, trace),
        "outcome": trace.outcome,
        "error": trace.error,
        # **The evidence, not just the verdict.** Without the answer and the tool calls in the
        # record, a failing row can only be diagnosed by paying for the turn again — and the first
        # real run of this suite produced failures that were impossible to attribute without them.
        # Truncated because a full transcript per task turns the record into something nobody opens.
        "text": trace.text[:1200],
        "tools_called": trace.tools_called,
        "card_types": trace.card_types,
    }


def execute(
    client: Any, pairs: list[tuple[dict, dict]], *, model_id: str, ceiling: float
) -> tuple[list[dict], str | None]:
    """Run every task, stopping if the ceiling is reached.

    The ceiling is checked **after** each run rather than predicted before it: an estimate would
    either stop early on a cautious guess or overshoot on an optimistic one, and the actual cost of
    the run just finished is a fact.
    """
    runs: list[dict] = []
    spend = 0.0
    for suite, task in pairs:
        reason = task.get("blocked_on") or suite.get("blocked_on")
        if reason:
            runs.append({"task_id": task["id"], "suite": suite["suite"], "skipped": reason})
            print(f"  SKIP {task['id']}: {str(reason).strip().splitlines()[0]}")
            continue

        for persona in task.get("personas") or []:
            started = time.monotonic()
            record = run_task(client, suite, task, persona, model_id=model_id)
            runs.append(record)
            spend += record["usd"] or 0.0

            failures = [r for r in record["results"] if not r["passed"] and not r["skipped"]]
            mark = "ok  " if not failures else "FAIL"
            cost = f"${record['usd']:.4f}" if record["usd"] is not None else "unpriced"
            print(
                f"  {mark} {record['task_id']:14} {cost:>10}  {time.monotonic() - started:5.1f}s"
                + (
                    f"  {failures[0]['evaluator']}: {failures[0]['detail'][:90]}"
                    if failures
                    else ""
                )
            )

            if spend >= ceiling:
                return runs, (
                    f"spend ceiling of ${ceiling:.2f} reached after {len(runs)} run(s) "
                    f"(${spend:.4f}). Raise --max-usd deliberately, or narrow the run with "
                    "--suite/--sample."
                )
    return runs, None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", action="append", help="limit to a suite letter; repeatable")
    parser.add_argument("--sample", type=int, help="first n tasks of each suite")
    parser.add_argument(
        "--max-usd",
        type=float,
        help="spend ceiling for this run; defaults to gate.yaml's limits.max_usd_per_run",
    )
    parser.add_argument("--json", type=pathlib.Path, help="write the full run record here")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list what would run, and what it is estimated to cost, without invoking anything",
    )
    args = parser.parse_args()

    config = yaml.safe_load((EVALUATION / "gate.yaml").read_text())
    ceiling = args.max_usd or float((config.get("limits") or {}).get("max_usd_per_run", 5.0))
    pairs = load_tasks(suites=args.suite, sample=args.sample)

    runnable = [(s, t) for s, t in pairs if not (t.get("blocked_on") or s.get("blocked_on"))]
    turns = sum(len(t.get("personas") or []) for _, t in runnable)

    print(f"{len(pairs)} task(s), {len(runnable)} runnable, {turns} turn(s)")
    print(f"ceiling ${ceiling:.2f}\n")

    if args.dry_run:
        # A measured warm turn, so the estimate is anchored to something rather than invented.
        print(
            f"dry run — nothing invoked. At $0.0086-$0.04 a turn, {turns} turns is roughly "
            f"${turns * 0.0086:.2f}-${turns * 0.04:.2f}."
        )
        for _suite, task in runnable:
            for persona in task.get("personas") or []:
                print(f"  would run {task['id']}/{persona}: {task['prompt'][:70]}")
        return 0

    from runner.agent_client import AgentClient  # noqa: PLC0415 - needs AWS; keep --dry-run offline

    client = AgentClient()
    runs, stopped = execute(client, pairs, model_id=client.model_id, ceiling=ceiling)

    narrowed = [
        flag
        for flag in (
            f"--suite {' '.join(args.suite)}" if args.suite else "",
            f"--sample {args.sample}" if args.sample else "",
        )
        if flag
    ]
    decision = decide(
        config,
        aggregate(runs),
        stopped=stopped,
        partial=" and ".join(narrowed) or None,
    )
    print("\n" + decision.report())

    if args.json:
        args.json.write_text(json.dumps({"runs": runs, "stopped": stopped}, indent=2))
        print(f"\nwrote {args.json}")

    return 0 if decision.passed else 1


if __name__ == "__main__":
    sys.exit(main())
