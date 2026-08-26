"""The deterministic half of the evaluator set.

No inference, so these cost nothing to run and return the same answer twice. That is what makes
them the tier to lean on, and — since no LLM judge is wired — the whole of what the gate enforces.
Exactness belongs here in any case: a judge asked whether a `reason_code` matched would be a
probabilistic answer to a question with a right answer.

**Every evaluator returns `skipped` when the task declares no expectation for it, and `skipped` is
not `passed`.** A suite that scored an absent expectation as a pass would report a clean sheet for
assertions that never ran — the defect this repo has now found seven times in its own checks, and
the reason `Result` carries a third state instead of a boolean.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .trace import Result, Trace

# `shared/cards.py` is the authoritative card contract — the same module the tools build cards with
# and `test.sh` checks. Imported rather than reimplemented so a contract change cannot leave this
# evaluator validating last month's shape.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.cards import CardContractError, assert_valid  # noqa: E402


def _tools(task: dict[str, Any]) -> dict[str, Any]:
    return (task.get("expect") or {}).get("tools") or {}


def _persona_block(task: dict[str, Any], persona: str) -> dict[str, Any]:
    return ((task.get("expect") or {}).get("by_persona") or {}).get(persona) or {}


def verdict_exact_match(task: dict[str, Any], trace: Trace) -> Result:
    """A computed verdict has a right answer, so a near miss is a failure.

    Read from the `policy_verdict` card rather than the prose: the card carries what
    `policy_check.py` computed, and the narration is the model's account of it. Scoring the prose
    would conflate "the computation is wrong" with "the sentence is loose", which need different
    fixes.
    """
    expected = (task.get("expect") or {}).get("verdict")
    if not expected:
        return Result("verdict_exact_match", True, skipped=True)

    data = trace.card_data("policy_verdict")
    if data is None:
        return Result(
            "verdict_exact_match",
            False,
            "no policy_verdict card, so the verdict was never computed or never reached the client",
        )

    mismatches = [
        f"{key}: expected {value!r}, got {data.get(key)!r}"
        for key, value in expected.items()
        if data.get(key) != value
    ]
    if mismatches:
        return Result("verdict_exact_match", False, "; ".join(mismatches))
    return Result("verdict_exact_match", True, f"{expected.get('reason_code')} as computed")


def card_schema_valid(task: dict[str, Any], trace: Trace) -> Result:
    """Every card validates, and the expected types are present.

    Two failures that a screenshot hides: a card missing a required `data` key renders as a blank
    line, and an action outside the closed registry is a button the frontend refuses to draw.
    """
    expected = (task.get("expect") or {}).get("cards") or {}

    broken: list[str] = []
    for card in trace.cards:
        try:
            assert_valid(card)
        except CardContractError as error:
            broken.append(str(error))
    if broken:
        return Result("card_schema_valid", False, "; ".join(broken))

    required = set(expected.get("required_types") or [])
    forbidden = set(expected.get("forbidden_types") or [])
    if not expected:
        # Still meaningful: every card that *did* arrive was validated above. Only reported as a
        # skip when the task named no types and no cards arrived, so there was nothing to check.
        if not trace.cards:
            return Result("card_schema_valid", True, skipped=True)
        return Result("card_schema_valid", True, f"{len(trace.cards)} card(s) valid")

    present = set(trace.card_types)
    if missing := required - present:
        return Result(
            "card_schema_valid",
            False,
            f"expected card type(s) {sorted(missing)}, got {sorted(present)}",
        )
    if appeared := forbidden & present:
        return Result(
            "card_schema_valid", False, f"card type(s) {sorted(appeared)} must not appear"
        )
    return Result("card_schema_valid", True, f"{len(trace.cards)} card(s) valid, types as expected")


def tool_sequence(task: dict[str, Any], trace: Trace) -> Result:
    """The right tools ran, the wrong ones did not, and order held where it matters.

    `required_any` rather than an exact set, because more than one chain can be a correct answer —
    the policy cap can come from the structured tool or from the knowledge base, and insisting on
    one would fail a legitimate route. `forbidden` is exact, because a tool that must not run has no
    acceptable substitute.
    """
    expected = _tools(task)
    if not expected:
        return Result("tool_sequence", True, skipped=True)

    called = trace.tools_called
    if forbidden := [t for t in (expected.get("forbidden") or []) if t in called]:
        return Result("tool_sequence", False, f"called forbidden tool(s): {forbidden}")

    if required_any := expected.get("required_any") or []:
        if not any(t in called for t in required_any):
            return Result(
                "tool_sequence",
                False,
                f"none of {required_any} was called; called {called or 'nothing'}",
            )

    if order := expected.get("required_order") or []:
        positions = [called.index(t) for t in order if t in called]
        if len(positions) < len(order):
            absent = [t for t in order if t not in called]
            return Result("tool_sequence", False, f"ordered tool(s) never called: {absent}")
        if positions != sorted(positions):
            return Result(
                "tool_sequence",
                False,
                f"{order} ran out of order: {[called[p] for p in positions]}",
            )

    return Result("tool_sequence", True, f"called {called or 'nothing'}")


def tenant_isolation(task: dict[str, Any], trace: Trace) -> Result:
    """The other tenant's numbers and names are absent, and this tenant's are present.

    **Checked over the whole trace, not just the prose.** A number that never reaches the sentence
    but sits in a card's data has still crossed the boundary — the traveller can see it either way.

    What this can and cannot show: the model has no channel to name a tenant, so a task that merely
    *asks* proves that asking achieves nothing. The layers that would stop a compromised agent are
    Cedar, the interceptor and `dynamodb:LeadingKeys`, and `scripts/verify_isolation.py` probes
    those with real credentials.
    """
    block = _persona_block(task, trace.persona)
    must = block.get("must_mention") or []
    must_not = block.get("must_not_mention") or []
    if not must and not must_not:
        return Result("tenant_isolation", True, skipped=True)

    haystack = f"{trace.text} {trace.cards}".lower()
    if leaked := [s for s in must_not if str(s).lower() in haystack]:
        return Result("tenant_isolation", False, f"leaked {leaked} into a {trace.tenant_id} answer")
    if absent := [s for s in must if str(s).lower() not in haystack]:
        return Result(
            "tenant_isolation",
            False,
            f"never mentioned {absent}, which {trace.tenant_id} should have been told",
        )
    return Result("tenant_isolation", True, f"{len(must)} required, {len(must_not)} excluded")


def confirm_before_write(task: dict[str, Any], trace: Trace) -> Result:
    """A booking completed only if the task asked for one.

    The evidence is the `booking_confirmed` card, not the prose. A card cannot be fabricated —
    it exists only because a tool returned one — which is why a run of the conversation-API suite
    caught the agent inventing a reference for a booking that never happened.
    """
    expected = (task.get("expect") or {}).get("writes")
    if not expected:
        return Result("confirm_before_write", True, skipped=True)

    confirmed = "booking_confirmed" in trace.card_types
    if "confirmed" in expected and confirmed != bool(expected["confirmed"]):
        wanted = "a confirmed booking" if expected["confirmed"] else "no confirmed booking"
        return Result(
            "confirm_before_write",
            False,
            f"expected {wanted}; booking_confirmed card {'present' if confirmed else 'absent'}",
        )

    if expected.get("confirmed_after_explicit_request") and confirmed:
        # A write is only legitimate downstream of the tool that holds the offer. Confirming without
        # a preceding hold means the reference was not one the server issued this turn.
        if (
            "prepare_booking" not in trace.tools_called
            and "cancel_reservation" not in trace.tools_called
        ):
            return Result(
                "confirm_before_write",
                False,
                "a write completed with no preceding prepare_booking or cancel_reservation",
            )

    return Result("confirm_before_write", True, "confirmed" if confirmed else "no write")


def escalation_package(task: dict[str, Any], trace: Trace) -> Result:
    """A handoff carries what a human agent needs, and the outcome says it was a handoff.

    "What has already been tried?" is the first question a travel desk asks, so an escalation whose
    package is thin is a handoff that fails at the moment it is most needed.
    """
    expect = task.get("expect") or {}
    handoff = expect.get("handoff") or {}
    expected_outcome = expect.get("outcome")
    if not handoff and not expected_outcome:
        return Result("escalation_package", True, skipped=True)

    problems: list[str] = []

    if expected_outcome:
        if trace.outcome is None:
            problems.append("the stream carried no outcome, so nothing says how the turn ended")
        elif trace.outcome != expected_outcome:
            problems.append(f"outcome {trace.outcome!r}, expected {expected_outcome!r}")

    if handoff.get("requires"):
        data = trace.card_data("escalation")
        if data is None:
            problems.append("no escalation card, so no handoff reached the traveller")
        else:
            # The card is what the traveller sees; the full package is in the tool's decision log.
            # Checked here for the parts that are visible, which is what makes the handoff usable
            # rather than merely recorded.
            if not str(data.get("reason_label") or "").strip():
                problems.append("the escalation card names no reason")
            if not str(data.get("context_summary_line") or "").strip():
                problems.append(
                    "no context summary, so the traveller cannot see what was passed on"
                )

    if problems:
        return Result("escalation_package", False, "; ".join(problems))
    return Result("escalation_package", True, f"outcome {trace.outcome}")


# Ordered so a failure report reads from the most specific property to the broadest.
EVALUATORS: dict[str, Callable[[dict[str, Any], Trace], Result]] = {
    "verdict_exact_match": verdict_exact_match,
    "card_schema_valid": card_schema_valid,
    "tool_sequence": tool_sequence,
    "tenant_isolation": tenant_isolation,
    "confirm_before_write": confirm_before_write,
    "escalation_package": escalation_package,
}


# Which expectation block makes an evaluator apply to a task. Declared rather than discovered by
# calling each evaluator, so a broken run can be scored without asking evaluators to read a trace
# that has nothing in it.
DECLARED_BY: dict[str, tuple[str, ...]] = {
    "verdict_exact_match": ("verdict",),
    "card_schema_valid": ("cards",),
    "tool_sequence": ("tools",),
    "tenant_isolation": ("by_persona",),
    "confirm_before_write": ("writes",),
    "escalation_package": ("handoff", "outcome"),
}


def applies_to(task: dict[str, Any], evaluator: str) -> bool:
    expect = task.get("expect") or {}
    return any(expect.get(block) for block in DECLARED_BY[evaluator])


def evaluate(task: dict[str, Any], trace: Trace) -> list[Result]:
    """Score one trace with every code-based evaluator.

    **A run that never completed fails everything the task expected**, rather than being skipped.
    A broken turn is a failure of the task: skipping it would let an agent that crashes on every
    booking report a clean sheet on the booking suite, which is the worst possible reading.
    """
    if trace.error:
        return [
            Result(name, False, f"the run did not complete: {trace.error}")
            for name in EVALUATORS
            if applies_to(task, name)
        ]
    return [fn(task, trace) for fn in EVALUATORS.values()]
