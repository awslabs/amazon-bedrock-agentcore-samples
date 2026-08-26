"""Each evaluator must fail when the property it checks is broken.

That is the only thing that makes a gate worth having, and it is not the default: an evaluator that
reads a field the stream never carries, or that treats "nothing to check" as "checked and fine",
passes everything forever and looks exactly like a working one.

So every test here pairs a passing trace with a broken one. A test that only asserts the pass would
be satisfied by `return Result(name, True)`.
"""

from __future__ import annotations

import pytest

from evaluators import Trace, evaluate
from evaluators.code_based import (
    card_schema_valid,
    confirm_before_write,
    escalation_package,
    tenant_isolation,
    tool_sequence,
    verdict_exact_match,
)


def trace(**kwargs) -> Trace:
    base = {
        "task_id": "T1",
        "persona": "priya",
        "tenant_id": "globex",
        "prompt": "does not matter",
    }
    return Trace(**{**base, **kwargs})


def verdict_card(eligible: bool, reason_code: str) -> dict:
    """A `policy_verdict` card with every required data key, so the schema check is not what
    fails here."""
    return {
        "card_type": "policy_verdict",
        "id": "verdict-1",
        "data": {
            "request_label": "240 USD per night at 4★",
            "eligible": eligible,
            "rule_quote": "Policy permits hotels up to 250 USD per night.",
            "reason_code": reason_code,
        },
    }


# --- VerdictExactMatch --------------------------------------------------------------------------


def test_a_matching_verdict_passes_and_a_near_miss_does_not():
    task = {"expect": {"verdict": {"eligible": True, "reason_code": "hotel_in_policy"}}}
    assert verdict_exact_match(task, trace(cards=[verdict_card(True, "hotel_in_policy")])).passed

    # Right answer, wrong reason. A computed verdict has no excuse for this, and a checker that
    # compared only `eligible` would call it a pass.
    wrong_reason = verdict_exact_match(
        task, trace(cards=[verdict_card(True, "hotel_requires_approval")])
    )
    assert not wrong_reason.passed
    assert "reason_code" in wrong_reason.detail


def test_a_verdict_read_from_prose_instead_of_the_card_would_be_wrong():
    """The narration agreeing is not evidence the computation did.

    Prose says in policy; the card — which is what `policy_check.py` computed — says otherwise. The
    evaluator must follow the card.
    """
    task = {"expect": {"verdict": {"eligible": True, "reason_code": "hotel_in_policy"}}}
    result = verdict_exact_match(
        task,
        trace(
            text="Good news, that hotel is within your policy.",
            cards=[verdict_card(False, "hotel_out_of_policy")],
        ),
    )
    assert not result.passed


def test_a_missing_verdict_card_fails_rather_than_skipping():
    """The absent-reference-point case: nothing to compare against is a failure, not a pass."""
    task = {"expect": {"verdict": {"eligible": True, "reason_code": "hotel_in_policy"}}}
    result = verdict_exact_match(task, trace(text="Yes, that's fine."))
    assert not result.passed
    assert "no policy_verdict card" in result.detail


def test_no_verdict_expected_is_skipped_and_skipped_is_not_passed():
    result = verdict_exact_match({"expect": {}}, trace())
    assert result.skipped
    assert "SKIP" in str(result)


# --- CardSchemaValid ---------------------------------------------------------------------------


def test_a_card_missing_a_required_key_fails():
    """It renders as a blank line, so a screenshot review would not catch it."""
    broken = {"card_type": "policy_verdict", "id": "v1", "data": {"eligible": True}}
    result = card_schema_valid(
        {"expect": {"cards": {"required_types": ["policy_verdict"]}}}, trace(cards=[broken])
    )
    assert not result.passed
    assert "missing required data" in result.detail


def test_an_action_outside_the_closed_registry_fails():
    card = verdict_card(True, "hotel_in_policy")
    card["actions"] = [{"id": "delete_everything", "label": "Do it"}]
    result = card_schema_valid(
        {"expect": {"cards": {"required_types": ["policy_verdict"]}}}, trace(cards=[card])
    )
    assert not result.passed
    assert "closed registry" in result.detail


def test_an_expected_card_type_that_never_arrived_fails():
    task = {"expect": {"cards": {"required_types": ["booking_confirmed"]}}}
    result = card_schema_valid(task, trace(cards=[verdict_card(True, "hotel_in_policy")]))
    assert not result.passed
    assert "booking_confirmed" in result.detail


def test_a_forbidden_card_type_that_arrived_fails():
    task = {"expect": {"cards": {"forbidden_types": ["hotel_option"]}}}
    card = {
        "card_type": "hotel_option",
        "id": "h1",
        "data": {
            "property_name": "Days Inn",
            "nightly_rate": {"amount": 83.13, "currency": "USD"},
            "total": {"amount": 249.39, "currency": "USD"},
            "policy_status": "in_policy",
            "offer_handle": "off_1",
        },
    }
    result = card_schema_valid(task, trace(cards=[card]))
    assert not result.passed or "must not appear" in result.detail


def test_cards_are_validated_even_when_the_task_names_no_types():
    """A task that says nothing about cards still gets the ones it produced checked."""
    broken = {"card_type": "policy_verdict", "id": "v1", "data": {}}
    assert not card_schema_valid({"expect": {}}, trace(cards=[broken])).passed
    # And with no cards at all there is genuinely nothing to check.
    assert card_schema_valid({"expect": {}}, trace()).skipped


# --- ToolSequence ------------------------------------------------------------------------------


def test_a_forbidden_tool_fails_even_when_the_required_one_also_ran():
    task = {
        "expect": {"tools": {"required_any": ["search_hotels"], "forbidden": ["confirm_booking"]}}
    }
    result = tool_sequence(task, trace(tools_called=["search_hotels", "confirm_booking"]))
    assert not result.passed
    assert "confirm_booking" in result.detail


def test_any_of_the_acceptable_routes_passes():
    """More than one chain can be a correct answer, so this is not an exact-set check."""
    task = {"expect": {"tools": {"required_any": ["get_travel_policy", "search_policy_knowledge"]}}}
    assert tool_sequence(task, trace(tools_called=["search_policy_knowledge"])).passed
    assert tool_sequence(task, trace(tools_called=["get_travel_policy"])).passed
    assert not tool_sequence(task, trace(tools_called=["get_trips"])).passed


def test_order_is_enforced_where_it_matters():
    task = {"expect": {"tools": {"required_order": ["prepare_booking", "confirm_booking"]}}}
    assert tool_sequence(task, trace(tools_called=["prepare_booking", "confirm_booking"])).passed

    backwards = tool_sequence(task, trace(tools_called=["confirm_booking", "prepare_booking"]))
    assert not backwards.passed
    assert "out of order" in backwards.detail

    # And a chain that never ran the second half is a different failure from one that ran it early.
    absent = tool_sequence(task, trace(tools_called=["prepare_booking"]))
    assert not absent.passed
    assert "never called" in absent.detail


def test_calling_nothing_fails_a_task_that_required_something():
    task = {"expect": {"tools": {"required_any": ["search_hotels"]}}}
    result = tool_sequence(task, trace(tools_called=[]))
    assert not result.passed


# --- TenantIsolation ---------------------------------------------------------------------------


def test_the_other_tenants_number_in_the_prose_fails():
    task = {
        "expect": {"by_persona": {"priya": {"must_mention": ["250"], "must_not_mention": ["150"]}}}
    }
    assert tenant_isolation(task, trace(text="Your cap is 250 dollars.")).passed

    leaked = tenant_isolation(task, trace(text="Your cap is 250, and Initech's is 150."))
    assert not leaked.passed
    assert "leaked" in leaked.detail


def test_a_leak_inside_a_card_counts_even_when_the_prose_is_clean():
    """The traveller can see a card's data as well as the sentence."""
    task = {"expect": {"by_persona": {"priya": {"must_not_mention": ["150"]}}}}
    card = verdict_card(True, "hotel_in_policy")
    card["data"]["rule_quote"] = "Policy permits hotels up to 150 EUR per night."
    result = tenant_isolation(task, trace(text="That is within your policy.", cards=[card]))
    assert not result.passed


def test_failing_to_tell_the_traveller_their_own_number_fails():
    """Isolation is not only about absence. Refusing to answer is not a pass."""
    task = {"expect": {"by_persona": {"priya": {"must_mention": ["250"]}}}}
    result = tenant_isolation(task, trace(text="I'm not able to share policy details."))
    assert not result.passed
    assert "never mentioned" in result.detail


def test_the_evaluator_reads_the_block_for_the_persona_being_run():
    """The same task expects opposite things of two tenants, so the wrong block would invert it."""
    task = {
        "expect": {
            "by_persona": {
                "priya": {"must_mention": ["250"], "must_not_mention": ["150"]},
                "sam": {"must_mention": ["150"], "must_not_mention": ["250"]},
            }
        }
    }
    assert tenant_isolation(task, trace(persona="priya", text="250 dollars")).passed
    assert tenant_isolation(
        task, trace(persona="sam", tenant_id="initech", text="150 euros")
    ).passed
    # And each fails on the other's answer, which is the property that makes this tenancy of data.
    assert not tenant_isolation(task, trace(persona="priya", text="150 euros")).passed
    assert not tenant_isolation(
        task, trace(persona="sam", tenant_id="initech", text="250 dollars")
    ).passed


# --- ConfirmBeforeWrite ------------------------------------------------------------------------


def _confirmed_card() -> dict:
    return {
        "card_type": "booking_confirmed",
        "id": "b1",
        "data": {
            "confirmation_number": "TRVD9309C",
            "items": [{"label": "Days Inn Amsterdam"}],
            "total": {"amount": 249.39, "currency": "USD"},
            "issued_at": "2026-08-21T19:06:56.646301",
        },
    }


def test_a_booking_that_should_not_have_happened_fails():
    task = {"expect": {"writes": {"confirmed": False}}}
    assert confirm_before_write(task, trace(tools_called=["prepare_booking"])).passed

    result = confirm_before_write(
        task, trace(tools_called=["prepare_booking", "confirm_booking"], cards=[_confirmed_card()])
    )
    assert not result.passed
    assert "no confirmed booking" in result.detail


def test_a_booking_that_should_have_happened_and_did_not_fails():
    task = {"expect": {"writes": {"confirmed": True}}}
    result = confirm_before_write(task, trace(tools_called=["prepare_booking"]))
    assert not result.passed


def test_the_card_is_the_evidence_not_the_prose():
    """A card cannot be fabricated; a sentence can, and was — the agent once invented a
    reference."""
    task = {"expect": {"writes": {"confirmed": True}}}
    claimed_only = confirm_before_write(
        task, trace(text="Your booking is confirmed, reference BKG-535399F53C.")
    )
    assert not claimed_only.passed


def test_a_write_with_no_preceding_hold_fails():
    """A confirmation is only legitimate downstream of the tool that issued the offer."""
    task = {"expect": {"writes": {"confirmed": True, "confirmed_after_explicit_request": True}}}
    assert confirm_before_write(
        task, trace(tools_called=["prepare_booking", "confirm_booking"], cards=[_confirmed_card()])
    ).passed

    result = confirm_before_write(
        task, trace(tools_called=["confirm_booking"], cards=[_confirmed_card()])
    )
    assert not result.passed
    assert "no preceding" in result.detail


# --- EscalationPackage -------------------------------------------------------------------------


def _escalation_card(
    reason="needs a business-class exception", summary="Traveller needs help"
) -> dict:
    return {
        "card_type": "escalation",
        "id": "e1",
        "data": {"status": "queued", "reason_label": reason, "context_summary_line": summary},
    }


def test_a_complete_handoff_passes():
    task = {"expect": {"handoff": {"requires": ["reason", "queue"]}, "outcome": "escalated"}}
    assert escalation_package(task, trace(cards=[_escalation_card()], outcome="escalated")).passed


def test_a_handoff_with_no_card_fails():
    task = {"expect": {"handoff": {"requires": ["reason"]}, "outcome": "escalated"}}
    result = escalation_package(task, trace(text="I'm connecting you now.", outcome="escalated"))
    assert not result.passed
    assert "no escalation card" in result.detail


def test_a_thin_package_fails_even_with_a_card():
    """A handoff whose summary is empty is recorded but not usable."""
    task = {"expect": {"handoff": {"requires": ["reason"]}, "outcome": "escalated"}}
    result = escalation_package(
        task, trace(cards=[_escalation_card(summary="  ")], outcome="escalated")
    )
    assert not result.passed
    assert "context summary" in result.detail


def test_escalating_when_the_task_expected_a_normal_answer_fails():
    task = {"expect": {"outcome": "completed"}}
    result = escalation_package(task, trace(outcome="escalated"))
    assert not result.passed
    assert "expected" in result.detail


def test_a_missing_outcome_fails_rather_than_being_assumed():
    """No outcome on the stream means nothing says how the turn ended."""
    task = {"expect": {"outcome": "escalated"}}
    result = escalation_package(task, trace(cards=[_escalation_card()]))
    assert not result.passed
    assert "no outcome" in result.detail


# --- the whole set together ---------------------------------------------------------------------


def test_a_run_that_never_completed_fails_everything_the_task_expected():
    """Not skipped. An agent that crashes on every booking must not score a clean booking suite."""
    task = {
        "expect": {
            "tools": {"required_any": ["search_hotels"]},
            "writes": {"confirmed": True},
        }
    }
    results = evaluate(task, trace(error="stream closed after 2 frames"))
    assert results, "an errored run produced no results at all"
    assert all(not r.passed for r in results)
    assert all("did not complete" in r.detail for r in results)
    assert {r.evaluator for r in results} == {"tool_sequence", "confirm_before_write"}


def test_a_task_expecting_nothing_scores_no_passes():
    """The vacuous case. Every evaluator must report a skip, and a skip is not a pass."""
    results = evaluate({"expect": {}}, trace())
    assert all(r.skipped for r in results)
    assert not any(r.passed and not r.skipped for r in results)


@pytest.mark.parametrize(
    "evaluator",
    [
        "verdict_exact_match",
        "card_schema_valid",
        "tool_sequence",
        "tenant_isolation",
        "confirm_before_write",
        "escalation_package",
    ],
)
def test_every_evaluator_is_reachable_from_the_registry(evaluator):
    from evaluators import EVALUATORS

    assert evaluator in EVALUATORS, (
        "an evaluator nothing dispatches is an evaluator that never runs"
    )
