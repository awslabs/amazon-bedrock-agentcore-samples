"""The fixtures are data, so nothing checks them until something runs them.

Which is the problem: a task with a misspelled persona, a `by_persona` block naming a traveller the
task never runs as, or an expectation block that is silently empty all *look* fine in YAML and
produce a pass. These are the checks a reader cannot perform by eye across fifty tasks.

Runs in seconds with no AWS account, so it belongs in `test.sh` rather than behind the deployed
suites.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

TASKS = pathlib.Path(__file__).resolve().parents[1] / "tasks"

# Resolved from `backend/seed/travelers.py`. A persona is how a task names a tenant, so a typo here
# would run the wrong tenant's policy against the right tenant's expectations.
PERSONAS = {"priya": "globex", "adaeze": "globex", "sam": "initech"}

# Every block a fixture may declare, each owned by exactly one evaluator. An unknown key is almost
# always a typo, and a typo in an expectation block is an assertion that never runs.
EXPECT_KEYS = {"tools", "verdict", "cards", "writes", "handoff", "outcome", "by_persona"}
PERSONA_KEYS = {"must_mention", "must_not_mention", "reason_must_mention"}


def _suites() -> list[tuple[pathlib.Path, dict]]:
    files = sorted(TASKS.glob("*.yaml"))
    assert files, "no task fixtures found"
    return [(f, yaml.safe_load(f.read_text())) for f in files]


def _tasks() -> list[tuple[str, dict, dict]]:
    """`(suite_letter, suite, task)` for every task across every file."""
    return [(s["suite"], s, t) for _, s in _suites() for t in s["tasks"]]


@pytest.mark.parametrize("path,suite", _suites(), ids=lambda v: getattr(v, "name", ""))
def test_every_suite_says_what_resolved_means(path, suite):
    """`resolved_when` is the denominator of cost per resolved task.

    Without it per-suite, "resolved" is whatever the runner happens to count, and the cost figure
    inherits that vagueness.
    """
    assert suite.get("suite"), f"{path.name}: no suite letter"
    assert suite.get("title"), f"{path.name}: no title"
    assert (suite.get("resolved_when") or "").strip(), f"{path.name}: does not define resolved"


def test_the_full_set_covers_every_suite_the_spec_settled():
    letters = {s["suite"] for _, s in _suites()}
    assert letters == set("ABCDEFG"), f"missing or unexpected suites: {letters}"


def test_task_ids_are_unique_across_the_whole_set():
    ids = [t["id"] for _, _, t in _tasks()]
    duplicates = {i for i in ids if ids.count(i) > 1}
    assert not duplicates, f"duplicate task ids: {duplicates}"


def test_every_task_names_a_real_persona():
    """A misspelled persona would run the wrong tenant's policy against these expectations."""
    for _, _, task in _tasks():
        personas = task.get("personas") or []
        assert personas, f"{task['id']}: runs as nobody"
        unknown = set(personas) - set(PERSONAS)
        assert not unknown, f"{task['id']}: unknown persona(s) {unknown}"


def test_every_task_asserts_something():
    """An empty expectation block is a task that always passes."""
    for _, _, task in _tasks():
        expect = task.get("expect") or {}
        assert expect, f"{task['id']}: no expectations at all"
        meaningful = {k: v for k, v in expect.items() if v}
        assert meaningful, f"{task['id']}: every expectation block is empty"


def test_expectation_blocks_use_known_keys_only():
    """A typo like `tool:` for `tools:` is an assertion that silently never runs."""
    for _, _, task in _tasks():
        unknown = set(task["expect"]) - EXPECT_KEYS
        assert not unknown, f"{task['id']}: unknown expectation key(s) {unknown}"
        for persona, block in (task["expect"].get("by_persona") or {}).items():
            bad = set(block) - PERSONA_KEYS
            assert not bad, f"{task['id']}/{persona}: unknown key(s) {bad}"


def test_by_persona_only_names_personas_the_task_runs_as():
    """The quietest failure in the set.

    A `by_persona` block for a traveller the task never runs as is an expectation that is never
    evaluated — and the task still reports green, so the missing coverage is invisible.
    """
    for _, _, task in _tasks():
        declared = set(task.get("personas") or [])
        for persona in task["expect"].get("by_persona") or {}:
            assert persona in declared, (
                f"{task['id']}: by_persona names {persona!r} but the task runs as "
                f"{sorted(declared)} — that block would never be evaluated"
            )


def test_a_blocked_task_says_what_it_is_waiting_for():
    """Skipping is honest; skipping silently is not.

    The reason has to be specific enough to act on, so it is required to be prose rather than a
    boolean flag.
    """
    for _, suite, task in _tasks():
        reason = task.get("blocked_on") or suite.get("blocked_on")
        if reason is not None:
            assert len(str(reason).strip()) > 20, f"{task['id']}: blocked_on is not a real reason"


def test_the_set_leans_on_tasks_whose_answer_differs_by_tenant():
    """Enough tasks must expect genuinely *different* things of the two tenants.

    Not every cross-tenant task: `A7` asks about parental leave, which is outside both knowledge
    bases, so both tenants share the same correct refusal — identical expectations are right there.
    The property worth enforcing is that the set contains a real body of tasks that an agent with no
    tenant isolation would fail, rather than that every pair happens to differ.
    """
    contrasting = []
    for _, _, task in _tasks():
        by_persona = task["expect"].get("by_persona") or {}
        if len({PERSONAS[p] for p in by_persona}) < 2:
            continue
        blocks = {
            (frozenset(b.get("must_mention") or []), frozenset(b.get("must_not_mention") or []))
            for b in by_persona.values()
        }
        if len(blocks) > 1:
            contrasting.append(task["id"])

    assert len(contrasting) >= 5, (
        f"only {len(contrasting)} tasks expect different things of the two tenants "
        f"({contrasting}) — an agent with no isolation would pass most of this set"
    )


def test_a_string_a_tenant_must_mention_is_never_one_it_must_not():
    """An unsatisfiable task fails forever and gets muted rather than fixed."""
    for _, _, task in _tasks():
        for persona, block in (task["expect"].get("by_persona") or {}).items():
            both = set(block.get("must_mention") or []) & set(block.get("must_not_mention") or [])
            assert not both, f"{task['id']}/{persona}: {both} is required and forbidden"


def test_no_task_requires_a_write_tool_it_also_forbids():
    for _, _, task in _tasks():
        tools = task["expect"].get("tools") or {}
        both = set(tools.get("required_any") or []) & set(tools.get("forbidden") or [])
        assert not both, f"{task['id']}: {both} is both required and forbidden"


def test_the_money_path_is_covered_in_both_directions():
    """A suite that only ever forbids `confirm_booking` proves nothing about booking.

    "Closed" and "broken shut" are indistinguishable without a task that expects a write to
    succeed — the same argument the conversation-API suite makes for its accepted click.
    """
    confirms = [
        t
        for _, _, t in _tasks()
        if "confirm_booking" in ((t["expect"].get("tools") or {}).get("required_any") or [])
    ]
    refuses = [
        t
        for _, _, t in _tasks()
        if "confirm_booking" in ((t["expect"].get("tools") or {}).get("forbidden") or [])
    ]
    assert confirms, "no task expects a booking to complete"
    assert refuses, "no task expects a booking to be refused"


# --- where the fixtures meet the evaluators ----------------------------------------------------
#
# The two halves are useless apart: a task no evaluator applies to always passes, and an evaluator
# no task exercises has never been run against anything real. Neither shows up in either suite
# alone, which is why these live here rather than with the evaluator unit tests.


def test_every_runnable_task_is_scored_by_at_least_one_evaluator():
    """A task nothing scores is a task that always passes."""
    from evaluators.code_based import DECLARED_BY, applies_to

    unscored = [
        task["id"]
        for _, suite, task in _tasks()
        if not (task.get("blocked_on") or suite.get("blocked_on"))
        and not any(applies_to(task, name) for name in DECLARED_BY)
    ]
    assert not unscored, f"no evaluator would score: {unscored}"


def test_every_evaluator_is_exercised_by_a_real_fixture():
    """An evaluator no task reaches has only ever been run against its own unit tests.

    Which is where a wrong assumption about the trace shape survives: the evaluator agrees with the
    fixture the test author invented, and meets real data for the first time in CI.
    """
    from evaluators.code_based import DECLARED_BY, applies_to

    runnable = [
        task
        for _, suite, task in _tasks()
        if not (task.get("blocked_on") or suite.get("blocked_on"))
    ]
    never_used = [name for name in DECLARED_BY if not any(applies_to(t, name) for t in runnable)]
    assert not never_used, f"no runnable fixture exercises: {never_used}"
