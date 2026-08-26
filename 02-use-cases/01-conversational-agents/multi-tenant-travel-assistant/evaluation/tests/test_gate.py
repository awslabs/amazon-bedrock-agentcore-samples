"""The merge decision, tested offline.

The arithmetic that decides whether a change ships is the last thing that should need a deployment
to exercise, so all of it is pure and all of it is checked here.

The failures worth guarding are not arithmetic slips. They are the readings that turn a gate into
decoration: a row with nothing measured reading as a pass, an aborted run reporting green, and a
cost figure divided by a resolved count of zero.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

from runner.gate import Aggregate, Score, aggregate, decide, percentile, rows

GATE = yaml.safe_load((pathlib.Path(__file__).resolve().parents[1] / "gate.yaml").read_text())


def _run(**kwargs) -> dict:
    """A passing run of one task, overridable per test."""
    base = {
        "task_id": "A1",
        "results": [
            {"evaluator": "tool_sequence", "passed": True},
            {"evaluator": "tenant_isolation", "passed": True},
        ],
        "usage": {"input": 1085, "cache_read": 11802, "output": 119},
        "steps": 2,
        "usd": 0.008581,
        "reflection_steps": 0,
        "resolved": True,
    }
    return {**base, **kwargs}


# --- the readings that would make the gate decoration ------------------------------------------


def test_a_row_with_nothing_measured_fails_rather_than_passes():
    """The defect this repo keeps finding, in the place it would matter most.

    No task exercised `verdict_exact_match`, so there is no rate to compare. Treating that as
    satisfying a `min: 1.00` would let a gate go green on a run that measured nothing.
    """
    agg = aggregate([_run()])
    built = {r.name: r for r in rows(GATE, agg)}

    assert built["verdict_exact_match"].observed is None
    assert not built["verdict_exact_match"].passed
    assert "nothing measured" in str(built["verdict_exact_match"])


def test_a_score_with_nothing_judged_has_no_rate_rather_than_a_perfect_one():
    assert Score(passed=0, judged=0).rate is None
    assert Score(passed=2, judged=2).rate == 1.0


def _fully_scored_runs(n: int = 20) -> list[dict]:
    """Runs that exercise every free-tier row and pass all of them.

    Needed because a run that leaves rows unmeasured already fails for that reason — so asserting a
    property *about a failing decision* proves nothing about the property. This is the baseline a
    test of "otherwise-green" has to start from.
    """
    every_free_evaluator = [
        {"evaluator": name, "passed": True}
        for name in (
            "verdict_exact_match",
            "card_schema_valid",
            "tenant_isolation",
            "confirm_before_write",
            "tool_sequence",
            "escalation_package",
        )
    ]
    return [_run(results=every_free_evaluator) for _ in range(n)]


def test_the_baseline_used_by_the_abort_test_is_genuinely_green():
    """Guards the test below from passing for the wrong reason.

    Without this, removing the abort check would leave `test_an_aborted_run...` still green — which
    is exactly what happened when it was first written, and how a vacuous assertion survives.
    """
    decision = decide(GATE, aggregate(_fully_scored_runs()))
    assert decision.passed, (
        f"baseline is not green, so the abort test would prove nothing:\n{decision.report()}"
    )


def test_an_aborted_run_never_passes_however_good_the_rows_look():
    """Otherwise the spend ceiling becomes a way to buy a passing gate cheaply."""
    agg = aggregate(_fully_scored_runs())
    decision = decide(GATE, agg, stopped="spend ceiling of $8.00 reached after 12 runs")

    assert not decision.failures, "the rows themselves must be green, or this proves nothing"
    assert not decision.passed
    assert "STOPPED" in decision.report()
    assert "proven nothing" in decision.report()


def test_nothing_resolved_gives_no_cost_per_resolved_task():
    """Dividing spend by zero resolved tasks is not a cheap run."""
    agg = aggregate([_run(resolved=False)])
    assert agg.usd_per_resolved is None
    assert agg.spend > 0

    built = {r.name: r for r in rows(GATE, agg)}
    assert not built["usd_per_resolved"].passed, "an unmeasurable cost row must not pass"


def test_a_gate_with_no_applicable_rows_gives_no_verdict():
    """An empty threshold set is not a pass."""
    decision = decide({}, aggregate([_run()]))
    assert decision.rows == []
    assert not decision.passed
    assert "no verdict" in decision.report()


# --- every declared row is computable -----------------------------------------------------------


def test_every_gate_row_has_an_evaluator_behind_it():
    """**No row may be declared that nothing can measure.**

    This replaced a pair of tier tests, and the defect it exists to prevent is the one those tests
    described rather than caught. Four rows — `correctness`, `grounded_narration`, `safety` and
    `escalation_timing` — were declared behind a `tier: full` flag with nothing computing them.
    Since `Row.passed` treats unmeasured as failure (correctly), `--tier full` could not succeed on
    any run, however healthy. The old tests asserted the tier *split*, and stayed green throughout.

    So the property worth testing is not how rows are grouped, it is that each one is reachable: a
    fully-scored run must leave no row unmeasured. Add a row to `gate.yaml` with no evaluator behind
    it and this fails at once, which is exactly what the pair it replaced did not do.
    """
    decision = decide(GATE, aggregate(_fully_scored_runs()))
    unmeasured = [r.name for r in decision.rows if r.observed is None]
    assert unmeasured == [], (
        f"gate rows with no evaluator producing them: {unmeasured}. Either wire an evaluator or "
        "remove the row — a row nothing measures makes the gate permanently red."
    )


# --- the cost arithmetic ------------------------------------------------------------------------


def test_cost_per_resolved_divides_spend_by_resolved_not_by_runs():
    """An escalated handoff is resolved; a failed turn is not. The denominator is the point."""
    runs = [
        _run(usd=0.02, resolved=True),
        _run(usd=0.02, resolved=True),
        _run(usd=0.02, resolved=False),
    ]
    agg = aggregate(runs)
    assert agg.spend == 0.06
    assert agg.resolved == 2
    assert agg.usd_per_resolved == 0.03, "0.06 over 2 resolved, not over 3 runs"


def test_the_cache_hit_rate_is_observed_from_both_counters():
    agg = aggregate([_run(usage={"input": 1085, "cache_read": 11802, "output": 119})])
    # 11802 / (11802 + 1085)
    assert agg.cache_hit_rate == pytest.approx(0.9158, abs=1e-4)
    assert rows(GATE, agg)[0] is not None
    assert {r.name: r.passed for r in rows(GATE, agg)}["cache_hit_rate"]


def test_a_broken_cache_prefix_trips_the_cache_row():
    """The failure this row exists for: context re-sent fresh every turn."""
    agg = aggregate([_run(usage={"input": 12000, "cache_read": 0, "output": 119})])
    assert agg.cache_hit_rate == 0.0
    assert not {r.name: r.passed for r in rows(GATE, agg)}["cache_hit_rate"]


def test_unpriced_runs_are_counted_and_reported_rather_than_averaged_over():
    """A missing rate card leaves a hole in the cost figure, and the report has to say so."""
    agg = aggregate([_run(usd=None), _run(usd=0.01)])
    assert agg.unpriced_runs == 1
    assert agg.spend == 0.01, "the unpriced run contributes nothing rather than zero-as-a-value"
    assert "unpriced" in decide(GATE, agg).report()


def test_reflection_rate_is_reflections_over_steps():
    agg = aggregate([_run(steps=4, reflection_steps=1), _run(steps=2, reflection_steps=0)])
    assert agg.reflection_step_rate == pytest.approx(1 / 6, abs=1e-4)


def test_the_measured_baseline_passes_every_cost_row():
    """Calibration check: the thresholds must not fire on the deployment as measured.

    A gate that fails on a healthy baseline gets disabled within a week, so this asserts the
    published numbers are actually achievable — using the real warm trajectory, repeated.
    """
    agg = aggregate([_run() for _ in range(20)])
    cost_rows = {r.name: r for r in rows(GATE, agg) if r.name in (GATE.get("cost") or {})}
    failed = [str(r) for r in cost_rows.values() if not r.passed]
    assert not failed, f"the measured baseline fails its own thresholds: {failed}"


# --- percentiles --------------------------------------------------------------------------------


def test_percentiles_of_nothing_are_none_rather_than_zero():
    assert percentile([], 0.95) is None
    assert percentile([], 0.5) is None


def test_percentiles_land_on_real_observations():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert percentile(values, 0.0) == 1.0
    assert percentile(values, 0.5) == 3.0
    assert percentile(values, 1.0) == 5.0
    # Nearest-rank, so every answer is a number that actually occurred and can be found in the run
    # list by hand.
    assert percentile(values, 0.95) in values


# --- skipped tasks ------------------------------------------------------------------------------


def test_skipped_tasks_are_reported_with_their_reason_and_scored_as_nothing():
    """Suite G's tasks wait on seeded backend scenarios. They must not read as passes."""
    runs = [_run(), {"task_id": "G1", "skipped": "needs simulate_price_drift in the mock backend"}]
    agg = aggregate(runs)

    assert agg.skipped_tasks == {"G1": "needs simulate_price_drift in the mock backend"}
    assert agg.resolved == 1, "the skipped task counts as neither resolved nor unresolved"
    assert agg.unresolved == 0

    report = decide(GATE, agg).report()
    assert "1 task(s) skipped" in report
    assert "simulate_price_drift" in report


# --- the config itself --------------------------------------------------------------------------


def test_a_threshold_with_neither_a_min_nor_a_max_is_an_error():
    """A row that enforces nothing while looking like it does."""
    with pytest.raises(ValueError, match="enforces nothing"):
        rows({"quality": {"something": {"target": 0.9}}}, Aggregate())


def test_the_correctness_rows_are_absolute():
    """Isolation, safety, verdicts, schemas and confirm-before-write are correctness, not quality.

    Pinned so a failing run cannot be made green by relaxing the row instead of fixing the agent.
    """
    for name in (
        "verdict_exact_match",
        "card_schema_valid",
        "tenant_isolation",
        "confirm_before_write",
    ):
        assert GATE["quality"][name]["min"] == 1.00, f"{name} must be absolute"
    assert GATE["escalation"]["escalation_package"]["min"] == 1.00


def test_the_run_has_a_spend_ceiling():
    """The failure mode is run count, not per-run cost: 270 unattended runs, as reported."""
    assert GATE["limits"]["max_usd_per_run"] > 0


# --- the runner's own wiring, checked without spending anything --------------------------------


def test_the_runners_model_id_matches_the_agents():
    """Two literals for one value, so a test has to hold them together.

    `agent_client.py` cannot import `model/load.py` — that pulls in Strands, which this package does
    not depend on — so the id is stated in both places. If they drift, every trajectory in a run is
    priced against a rate card for a model that did not answer it.
    """
    import re

    client_source = (
        pathlib.Path(__file__).resolve().parents[1] / "runner" / "agent_client.py"
    ).read_text()
    agent_source = (
        pathlib.Path(__file__).resolve().parents[2]
        / "agent"
        / "MultiTenantTravel"
        / "app"
        / "MultiTenantTravel"
        / "model"
        / "load.py"
    ).read_text()

    runner_id = re.search(r'^MODEL_ID = "([^"]+)"', client_source, re.M)
    agent_id = re.search(r'^MODEL_ID = "([^"]+)"', agent_source, re.M)
    assert runner_id and agent_id, "could not find MODEL_ID in one of the two files"
    assert runner_id.group(1) == agent_id.group(1)


def test_the_priced_model_has_a_rate_card():
    """A run whose every trajectory is unpriced would report no cost rows at all."""
    import importlib.util

    root = pathlib.Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "agent_pricing",
        root / "agent" / "MultiTenantTravel" / "app" / "MultiTenantTravel" / "pricing.py",
    )
    pricing = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pricing)

    from runner.agent_client import MODEL_ID

    assert MODEL_ID in pricing.FALLBACK_RATES, "the model the runner prices with has no rates"


def test_sampling_is_deterministic_so_a_regression_is_not_a_reshuffle():
    """`--sample` takes the first n, not a random n.

    A gate that judges a different subset each run cannot distinguish a regression from a different
    draw, which is worse than not sampling.
    """
    from runner.run import load_tasks

    first = [t["id"] for _, t in load_tasks(sample=3)]
    again = [t["id"] for _, t in load_tasks(sample=3)]
    assert first == again
    assert len(first) == 3 * 7, "three tasks from each of the seven suites"


def test_suite_filtering_narrows_the_run():
    from runner.run import load_tasks

    only_b = load_tasks(suites=["B"])
    assert only_b, "no tasks came back for suite B"
    assert {s["suite"] for s, _ in only_b} == {"B"}
    assert len(only_b) < len(load_tasks())


def test_a_task_whose_expectations_were_all_skipped_is_not_resolved():
    """The denominator of cost per resolved task must not count runs nobody judged."""
    from evaluators import Result, Trace
    from runner.run import resolved

    trace = Trace(task_id="X", persona="priya", tenant_id="globex", prompt="hi")
    all_skipped = [Result("tool_sequence", True, skipped=True)]
    assert not resolved({}, all_skipped, trace)

    judged = [Result("tool_sequence", True)]
    assert resolved({}, judged, trace)


def test_an_errored_run_is_never_resolved():
    from evaluators import Result, Trace
    from runner.run import resolved

    broken = Trace(
        task_id="X", persona="priya", tenant_id="globex", prompt="hi", error="stream closed"
    )
    assert not resolved({}, [Result("tool_sequence", True)], broken)


# --- the execute loop, driven by a fake client ---------------------------------------------------
#
# Proves the orchestration without a deployment: that the ceiling stops the run, that a blocked task
# is skipped with its reason rather than invoked, and that one task blowing up does not end the run.


class _FakeClient:
    """Answers every turn with the same canned stream."""

    model_id = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"

    def __init__(self, *, per_turn_tokens: int = 1000, raises_on: str | None = None):
        self.per_turn_tokens = per_turn_tokens
        self.raises_on = raises_on
        self.prompts: list[str] = []
        self.armed: list[tuple[str, set[str] | None]] = []

    def turn(
        self,
        *,
        persona: str,
        prompt: str,
        scenarios: set[str] | None = None,
        tenant_id: str | None = None,
    ) -> list[dict]:
        # Recorded so a test can assert a suite-G task arms its scenario, and accepted at all
        # so the fake keeps the real client's signature — one that drifts proves nothing.
        self.prompts.append(prompt)
        self.armed.append((prompt, scenarios))
        if self.raises_on and self.raises_on in prompt:
            raise RuntimeError("gateway timeout")
        return [
            {"type": "tool_start", "tool": "get_travel_policy", "id": "t1"},
            {"type": "text", "text": "Your cap is 250 dollars."},
            {
                "type": "done",
                "usage": {"input": self.per_turn_tokens, "output": 100, "cache_read": 5000},
                "steps": 2,
                "outcome": "completed",
            },
        ]


def test_the_ceiling_stops_the_run_and_the_stop_is_reported():
    """The guard against the real failure mode, which is run count rather than per-run cost."""
    from runner.run import execute, load_tasks

    client = _FakeClient(per_turn_tokens=2_000_000)  # ~$6 a turn, so the ceiling trips fast
    runs, stopped = execute(
        client, load_tasks(suites=["A"]), model_id=client.model_id, ceiling=8.00
    )

    assert stopped is not None
    assert "ceiling" in stopped
    assert len(runs) < 14, "the run should have stopped well before suite A finished"
    decision = decide(GATE, aggregate(runs), stopped=stopped)
    assert not decision.passed


def test_a_blocked_task_is_skipped_without_being_invoked():
    """E4 waits on a per-task budget override, so it must not reach the client.

    **The mechanism, not the specific task.** Suite G was the example here until its scenarios were
    built; asserting on whichever task happens to be blocked today is what made this test need
    rewriting. What must keep holding is that a declared block costs nothing and is reported.
    """
    from runner.run import execute, load_tasks

    client = _FakeClient()
    runs, stopped = execute(client, load_tasks(suites=["E"]), model_id=client.model_id, ceiling=8.0)

    assert stopped is None
    skipped = [r for r in runs if r.get("skipped")]
    assert [r["task_id"] for r in skipped] == ["E4"]
    assert not any("Frankfurt to Amsterdam" in prompt for prompt in client.prompts), (
        "a blocked task must not spend money"
    )

    report = decide(GATE, aggregate(runs)).report()
    assert "1 task(s) skipped" in report
    assert "operator action" in report, "the skip must carry the measured reason, not a vague one"


def test_suite_g_arms_a_scenario_for_every_task_that_needs_one():
    """The drift suite runs now, and each task carries the condition it is testing.

    **Asserted because a scenario that fails to arm is invisible.** The backend behaves normally,
    the agent answers correctly, and the task passes — while testing nothing. That is the failure
    this suite exists to prevent, so it must not be the failure the suite has.
    """
    from runner.run import execute, load_tasks, scenarios_for

    client = _FakeClient()
    runs, stopped = execute(client, load_tasks(suites=["G"]), model_id=client.model_id, ceiling=8.0)

    assert stopped is None
    assert not any(r.get("skipped") for r in runs), "suite G is no longer blocked"
    assert len(client.prompts) == 6

    armed = {prompt: scenarios for prompt, scenarios in client.armed}
    assert armed, "no scenario reached the client"
    # Five of six need a simulated condition; replaying a dead handle needs none, because the
    # ordinary path already refuses it.
    assert sum(1 for scenarios in armed.values() if scenarios) == 5

    _, g6 = next((suite, task) for suite, task in load_tasks(suites=["G"]) if task["id"] == "G6")
    assert scenarios_for(g6) is None


def test_an_unknown_scenario_name_is_refused_rather_than_ignored():
    """A task believing it tests drift while the backend behaves normally passes for the wrong
    reason, which is worse than a task that fails."""
    from runner.run import scenarios_for

    with pytest.raises(SystemExit, match="unknown scenario"):
        scenarios_for({"id": "X1", "scenario": "gravity_reversed"})


def test_one_broken_task_does_not_end_the_run():
    """A client exception is scored as that task failing, not as the suite aborting."""
    from runner.run import execute, load_tasks

    client = _FakeClient(raises_on="star rating")
    runs, stopped = execute(client, load_tasks(suites=["A"]), model_id=client.model_id, ceiling=8.0)

    assert stopped is None
    errored = [r for r in runs if r.get("error")]
    assert errored, "the raising task produced no error record"
    assert all("gateway timeout" in r["error"] for r in errored)
    # And the rest still ran.
    assert len([r for r in runs if not r.get("error") and not r.get("skipped")]) > 5


def test_a_run_is_priced_from_the_streams_own_token_counts():
    from runner.run import execute, load_tasks

    client = _FakeClient()
    runs, _ = execute(
        client, load_tasks(suites=["A"], sample=1), model_id=client.model_id, ceiling=8.0
    )
    priced = [r for r in runs if r.get("usd") is not None]
    assert priced, "nothing was priced"
    # 1000 input at $3/M + 100 output at $15/M + 5000 cache read at $0.30/M
    assert priced[0]["usd"] == pytest.approx(0.003 + 0.0015 + 0.0015, abs=1e-6)


def test_the_runner_derives_the_same_session_id_as_the_conversation_api():
    """Arming a scenario depends on this hash matching, and a mismatch is silent.

    **The failure mode is a passing test that tests nothing.** Keyed on the conversation id rather
    than the runtime session id, every row was written successfully, no request matched one, and all
    six drift tasks passed by behaving completely normally. Nothing errors, nothing warns, and the
    suite reports a clean sheet for the conditions it was built to check.

    So the derivation is asserted against the conversation API's own source. The two cannot be
    imported into one process — the API is a separate service with its own dependencies — which is
    the same reason `MODEL_ID` is compared textually above.
    """
    import hashlib
    import pathlib
    import re

    api_source = (
        pathlib.Path(__file__).resolve().parents[2] / "conversation-api" / "app" / "main.py"
    ).read_text()
    derivation = re.search(
        r'hashlib\.sha256\(f"\{(\w+)\}:\{(\w+)\}:\{(\w+)\}"\.encode\(\)\)\.hexdigest\(\)',
        api_source,
    )
    assert derivation, "could not find the session-id derivation in the conversation API"
    assert derivation.group(1) == "tenant", derivation.group(1)
    assert derivation.group(2) == "traveler", derivation.group(2)
    assert derivation.group(3) == "conversation_id", derivation.group(3)

    from runner.agent_client import AgentClient

    # The traveller id is read from `/auth/session` at run time, so it is stubbed here: what this
    # asserts is the *derivation*, which is the half that can silently disagree with the API.
    client = AgentClient.__new__(AgentClient)
    client._travelers = {"priya": "trv_31d81fa59772"}
    client._tenants = {"priya": "globex"}
    conversation_id = "0" * 32 + "aaa"
    assert (
        client._runtime_session_id("priya", conversation_id)
        == hashlib.sha256(f"globex:trv_31d81fa59772:{conversation_id}".encode()).hexdigest()
    )
