"""Budget caps, and the ways a circuit breaker fails to be one.

Three failure modes worth asserting, none of which raises anything:

  * **a cap set at the gate's thresholds**, which trips on healthy turns until somebody raises it
    to a number that never trips at all;
  * **an unpriced trajectory reading as under budget**, which removes the money guard on precisely
    the deployment whose spend nobody is tracking; and
  * **a breach that stops nothing**, because it is noticed after the loop that did the spending.
"""

from __future__ import annotations

import sys
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parents[1] / "MultiTenantTravel" / "app" / "MultiTenantTravel"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

import budget as budget_module  # noqa: E402
import pricing  # noqa: E402
from budget import Budget  # noqa: E402
from ledger import Trajectory  # noqa: E402

SONNET = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"

# The thresholds `evaluation/gate.yaml` sets for the eval gate. The caps must sit above these, or
# the breaker trips on turns the gate calls healthy.
GATE_P95_USD = 0.60
GATE_P95_STEPS = 10

# A measured warm turn from the deployment, for scale.
MEASURED_TURN_USD = 0.008581
MEASURED_TURN_STEPS = 2


def test_the_caps_sit_above_the_gate_thresholds():
    """A runtime breaker and an offline quality gate are different instruments.

    If the cap equalled the gate's p95, every turn at the edge of acceptable would be escalated to
    a human — and the fix a team reaches for is raising the cap until it stops complaining, which
    ends with a breaker that never fires.
    """
    caps = Budget()
    assert caps.max_usd > GATE_P95_USD
    assert caps.max_steps > GATE_P95_STEPS
    # And far enough above a normal turn to only mean "runaway".
    assert caps.max_usd > MEASURED_TURN_USD * 50
    assert caps.max_steps > MEASURED_TURN_STEPS * 3


def test_a_normal_turn_is_not_a_breach():
    assert Budget().breach(steps=MEASURED_TURN_STEPS, usd=MEASURED_TURN_USD) is None


def test_the_step_cap_catches_a_loop_that_spends_little():
    """A reflection loop burns steps with small token counts, so spend alone would miss it."""
    breach = Budget(max_usd=1.0, max_steps=15).breach(steps=15, usd=0.02)
    assert breach is not None
    assert "step budget" in breach
    assert "15" in breach


def test_the_spend_cap_catches_one_enormous_step():
    """And one huge context burns dollars without burning steps, so steps alone would miss it.

    Both caps exist for this reason — it is the question phase-7 DESIGN left open.
    """
    breach = Budget(max_usd=1.0, max_steps=15).breach(steps=2, usd=1.4)
    assert breach is not None
    assert "spend budget" in breach
    assert "1.40" in breach


def test_an_unpriced_trajectory_keeps_the_step_cap_and_says_the_spend_cap_is_off(caplog):
    """`usd is None` means no rate card — it must not read as "under budget".

    Silently passing would strip the money guard from the one deployment whose spend is already
    unmeasured, which is the opposite of what a missing rate card should cost.
    """
    caps = Budget(max_usd=1.0, max_steps=15)
    with caplog.at_level("WARNING"):
        assert caps.breach(steps=3, usd=None) is None
    assert any("cannot be enforced" in r.getMessage() for r in caplog.records)
    # The step cap is untouched by the gap.
    assert caps.breach(steps=15, usd=None) is not None


def test_the_breach_reason_is_prose_a_travel_desk_can_act_on():
    breach = Budget(max_usd=1.0, max_steps=15).breach(steps=15, usd=0.4)
    reason = budget_module.reason_for_handoff(
        breach, steps=15, usd=0.4, tools=["get_travel_policy", "search_flights"]
    )
    assert "15 step" in reason
    assert "$0.4000" in reason
    assert "get_travel_policy" in reason and "search_flights" in reason
    assert "has not been helped" in reason, "the human needs to know nothing was resolved"


def test_the_handoff_reason_reports_unpriced_spend_honestly():
    reason = budget_module.reason_for_handoff("step budget reached", steps=15, usd=None, tools=[])
    assert "unpriced" in reason
    assert "None" not in reason, "a human agent should never read a Python None"


def test_a_malformed_published_budget_falls_back_loudly(monkeypatch, caplog):
    monkeypatch.setattr(budget_module, "_cached", None)
    monkeypatch.setenv(budget_module.BUDGET_VAR, "{nope")
    with caplog.at_level("WARNING"):
        caps = budget_module.budget()
    assert caps == Budget()
    assert any("unusable" in r.getMessage() for r in caplog.records)


def test_a_published_budget_takes_effect(monkeypatch):
    monkeypatch.setattr(budget_module, "_cached", None)
    monkeypatch.setenv(budget_module.BUDGET_VAR, '{"max_usd": 0.05, "max_steps": 4}')
    caps = budget_module.budget()
    assert caps.max_usd == 0.05
    assert caps.max_steps == 4
    assert caps.breach(steps=2, usd=0.06) is not None


# --- what the ledger contributes to a handoff -------------------------------------------------


def _turn_with(tool_names: list[str]) -> Trajectory:
    trajectory = Trajectory(
        tenant_id="globex",
        traveler_id="trv_1",
        session_id="sess_1",
        model_id=SONNET,
        prompt_version="abc123",
        pricer=pricing.price,
    )
    for name in tool_names:
        trajectory.record_tool(name)
    trajectory.record_usage({"inputTokens": 400, "outputTokens": 60})
    return trajectory


def test_the_ledger_supplies_what_was_tried_rather_than_the_model():
    """ "What has already been tried?" is a human agent's first question.

    Taken from the recorded tool calls, because the model is the thing that just overran and would
    be an unreliable narrator of its own loop.
    """
    trajectory = _turn_with(["get_travel_policy", "search_flights", "get_travel_policy"])
    assert trajectory.tools_tried == ["get_travel_policy", "search_flights"], "deduped, in order"
    assert trajectory.steps_taken == 1


def test_an_escalated_turn_is_recorded_as_a_resolved_outcome_not_a_failure():
    """CPRT's denominator counts a clean handoff as resolved.

    Otherwise the metric rewards an agent that flails on over one that gives up well.
    """
    trajectory = _turn_with(["get_travel_policy"])
    assert trajectory.as_dict()["outcome"] == "completed"
    trajectory.outcome = "escalated_budget"
    line = trajectory.as_dict()
    assert line["outcome"] == "escalated_budget"
    # The spend that triggered it stays on the same line, so the handoff is joinable to its cost.
    assert line["usd"] is not None
    assert line["session_id"] == "sess_1"
