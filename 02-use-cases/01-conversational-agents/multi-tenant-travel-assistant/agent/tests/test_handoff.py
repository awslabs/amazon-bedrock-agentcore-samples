"""The budget handoff — the path that only runs when something has already gone wrong.

Which is exactly why it is tested rather than inspected: nobody exercises it in a browser, so a
break here would be found by a traveller being told they are being transferred to a queue that does
not exist.

Three outcomes have to be distinguishable, and two of them are failures the tool reports *without*
raising:

  * the queue exists  -> the traveller is told they are being handed over, and gets the card
  * no support queue  -> the tool returns a message and no card; the traveller must be told the
    honest version instead of "I'm connecting you"
  * the gateway is unreachable -> an exception, and still no false promise
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parents[1] / "MultiTenantTravel" / "app" / "MultiTenantTravel"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

import handoff  # noqa: E402
import pricing  # noqa: E402
from ledger import Trajectory  # noqa: E402

SONNET = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"


def _overrun() -> Trajectory:
    """A trajectory that has done real work and cost real money."""
    trajectory = Trajectory(
        tenant_id="globex",
        traveler_id="trv_1",
        session_id="sess_abc",
        model_id=SONNET,
        prompt_version="abc123",
        pricer=pricing.price,
    )
    trajectory.record_tool("get_travel_policy")
    trajectory.record_usage({"inputTokens": 4_000, "outputTokens": 500})
    trajectory.start_step()
    trajectory.record_tool("search_flights")
    trajectory.record_usage({"inputTokens": 6_000, "outputTokens": 700})
    trajectory.outcome = "escalated_budget"
    return trajectory


class _Client:
    """Records the call, and answers however the test asks it to."""

    def __init__(self, *, result=None, raises: Exception | None = None):
        self.result = result
        self.raises = raises
        self.calls: list[dict] = []

    async def call_tool_async(self, *, tool_use_id, name, arguments):
        self.calls.append({"tool_use_id": tool_use_id, "name": name, "arguments": arguments})
        if self.raises:
            raise self.raises
        return self.result


def _escalation_result(*, with_card: bool) -> dict:
    """What the escalation tool really returns, in the envelope the MCP client delivers.

    The tool JSON-encodes `{cards, facts, message, provenance}` into a text content block, which is
    why `stream.payloads_in` parses rather than reads it.
    """
    payload: dict = {
        "facts": {"escalated": with_card, "queue": "globex-travel-desk" if with_card else None},
        "provenance": {"source": "escalation"},
    }
    if with_card:
        payload["cards"] = [
            {
                "card_type": "escalation",
                "card_id": "escalation-sess_abc",
                "data": {"status": "queued", "reason_label": "budget"},
            }
        ]
    else:
        payload["message"] = "your company hasn't set up a travel desk queue"
    return {"status": "success", "content": [{"text": json.dumps(payload)}]}


def _drain(client, trajectory, breach="step budget reached: 15 steps, limit 15") -> list[dict]:
    async def run():
        return [event async for event in handoff.escalate_over_budget(client, trajectory, breach)]

    return asyncio.run(run())


def test_a_successful_handoff_tells_the_traveller_and_renders_the_card():
    client = _Client(result=_escalation_result(with_card=True))
    events = _drain(client, _overrun())

    assert [e["type"] for e in events] == ["text", "cards"]
    assert events[0]["text"] == handoff.OVER_BUDGET_MESSAGE
    assert events[1]["cards"][0]["card_type"] == "escalation"


def test_the_reason_carries_what_was_tried_and_what_it_cost():
    """A human agent's first two questions, answered from the ledger rather than by the model."""
    client = _Client(result=_escalation_result(with_card=True))
    _drain(client, _overrun())

    reason = client.calls[0]["arguments"]["reason"]
    assert "get_travel_policy" in reason and "search_flights" in reason
    assert "2 step" in reason
    # 10,000 input at $3/M + 1,200 output at $15/M = $0.048.
    assert "$0.0480" in reason
    assert "step budget reached" in reason


def test_it_calls_the_ordinary_escalation_tool_not_a_private_path():
    """One escalation path, so the tenant queue lookup and refusal rules cannot diverge."""
    client = _Client(result=_escalation_result(with_card=True))
    _drain(client, _overrun())
    assert client.calls[0]["name"] == handoff.ESCALATION_TOOL
    assert client.calls[0]["name"].endswith("escalate_to_human")
    assert client.calls[0]["tool_use_id"] == "budget-sess_abc"


def test_a_tenant_with_no_queue_is_never_told_it_is_being_transferred():
    """The tool refuses by returning a message and no card — not by raising.

    So an implementation that keyed off exceptions would promise a transfer into a void, which is
    the one outcome the escalation tool's own docstring says it must never produce.
    """
    client = _Client(result=_escalation_result(with_card=False))
    events = _drain(client, _overrun())

    assert [e["type"] for e in events] == ["text"], "no card, so nothing to render"
    assert events[0]["text"] == handoff.OVER_BUDGET_NO_HANDOFF
    assert "travel desk" in events[0]["text"]
    assert "handing this" not in events[0]["text"], "must not claim a handover happened"


def test_an_unreachable_gateway_still_leaves_the_traveller_something_true():
    client = _Client(raises=RuntimeError("gateway timeout"))
    events = _drain(client, _overrun())

    assert [e["type"] for e in events] == ["text"]
    assert events[0]["text"] == handoff.OVER_BUDGET_NO_HANDOFF


def test_a_garbled_tool_result_is_treated_as_no_handoff():
    """Neither a card nor an exception. Absent structure must fail closed, not silently succeed."""
    for garbled in ({"status": "success", "content": [{"text": "not json"}]}, {}, None):
        events = _drain(_Client(result=garbled), _overrun())
        assert [e["type"] for e in events] == ["text"]
        assert events[0]["text"] == handoff.OVER_BUDGET_NO_HANDOFF


def test_an_unpriced_trajectory_still_produces_a_usable_reason():
    """No rate card must not put a Python `None` in front of a human agent."""
    trajectory = _overrun()
    trajectory.pricer = None
    _drain(client := _Client(result=_escalation_result(with_card=True)), trajectory)
    reason = client.calls[0]["arguments"]["reason"]
    assert "unpriced" in reason
    assert "None" not in reason
