"""Pricing a trajectory, and the two ways a cost report goes quietly wrong.

The failures worth testing here are not arithmetic slips — those show up immediately. They are:

  * **an unrecognised model pricing to zero**, which makes spend appear to vanish exactly when
    someone upgrades a model, and
  * **cache tokens counted on the wrong side of `inputTokens`**, which is a live risk because
    both conventions exist on Bedrock: additive for Anthropic (measured below), inclusive for
    OpenAI per AWS's own guidance.

Both produce a plausible smaller number and no error.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

AGENT_DIR = Path(__file__).resolve().parents[1] / "MultiTenantTravel" / "app" / "MultiTenantTravel"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

import pricing  # noqa: E402
from ledger import Trajectory  # noqa: E402

SONNET = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"


@pytest.fixture(autouse=True)
def _built_in_rates(monkeypatch):
    """Price against the built-in table, never against whatever SSM happens to hold.

    Without this the suite's numbers would depend on a deployment, so a rate change in a
    parameter store would fail tests that are asserting arithmetic, not configuration.
    """
    monkeypatch.delenv(pricing.RATES_VAR, raising=False)
    monkeypatch.setattr(pricing, "_rates", pricing.FALLBACK_RATES)
    monkeypatch.setattr(pricing, "_rate_version", pricing.RATE_VERSION)


def test_the_published_rates_are_the_ones_the_vendor_lists():
    # Pinned so a well-meaning edit cannot quietly move every cost figure in the blog series.
    # Anthropic list prices for Sonnet 4.5, USD per million tokens.
    rates = pricing.FALLBACK_RATES[SONNET]
    assert rates["input"] == 3.00
    assert rates["output"] == 15.00
    assert rates["cache_read"] == 0.30  # 0.1x input
    assert rates["cache_write_5m"] == 3.75  # 1.25x input
    assert rates["cache_write_1h"] == 6.00  # 2x input


def test_a_plain_turn_costs_its_tokens():
    # 1,000 input at $3/M = $0.003; 500 output at $15/M = $0.0075.
    priced = pricing.price(model_id=SONNET, input_tokens=1_000, output_tokens=500)
    assert priced["usd_detail"]["input"] == 0.003
    assert priced["usd_detail"]["output"] == 0.0075
    assert priced["usd"] == 0.0105
    assert priced["rate_version"] == pricing.RATE_VERSION


def test_cache_tokens_are_priced_on_top_of_input_not_inside_it():
    """The measured identity: `total = input + cacheRead + cacheWrite + output`.

    Measured with two real `converse` calls sharing a cached prefix — first reported
    `inputTokens=9, cacheWrite=1081`, second `inputTokens=10, cacheRead=1081`, both totalling
    1095. So a cached turn's *input* count is small and the cache counts carry the bulk.

    If cache tokens were instead inside `inputTokens`, pricing them separately would
    double-count. This asserts the additive reading by pricing the second call's shape and
    checking the cache read is charged at the discounted rate *in addition to* the 10 new tokens.
    """
    priced = pricing.price(
        model_id=SONNET, input_tokens=10, output_tokens=4, cache_read_tokens=1_081
    )
    assert priced["usd_detail"]["input"] == round(10 * 3.00 / 1_000_000, 6)
    assert priced["usd_detail"]["cache_read"] == round(1_081 * 0.30 / 1_000_000, 6)
    assert priced["usd_detail"]["cache_read"] > 0, "a cache read is cheap, never free"

    # And the discount is real: the same tokens as fresh input cost about ten times as much.
    # Asserted loosely on purpose — the exact ratio lives in the rate table, checked below, and
    # comparing rounded components against each other tests the rounding rather than the rates
    # (0.000324 x 10 is 0.00324, while 1081 fresh tokens are 0.003243).
    fresh = pricing.price(model_id=SONNET, input_tokens=1_081)
    assert fresh["usd_detail"]["input"] == pytest.approx(
        priced["usd_detail"]["cache_read"] * 10, rel=1e-3
    )
    rates = pricing.FALLBACK_RATES[SONNET]
    assert rates["cache_read"] * 10 == rates["input"], "the exact ratio belongs to the rate card"


def test_the_write_rate_follows_the_ttl_bedrock_reported():
    at_5m = pricing.price(model_id=SONNET, cache_write_tokens=1_000, cache_ttl="5m")
    at_1h = pricing.price(model_id=SONNET, cache_write_tokens=1_000, cache_ttl="1h")
    assert at_5m["usd_detail"]["cache_write"] == round(1_000 * 3.75 / 1_000_000, 6)
    assert at_1h["usd_detail"]["cache_write"] == round(1_000 * 6.00 / 1_000_000, 6)
    # An unknown TTL defaults down, so a missing field understates rather than overstates.
    unknown = pricing.price(model_id=SONNET, cache_write_tokens=1_000, cache_ttl=None)
    assert unknown["usd_detail"]["cache_write"] == at_5m["usd_detail"]["cache_write"]


def test_an_unknown_model_is_unpriced_rather_than_free():
    """The branch whose wrongness would be invisible.

    Zero would make a model upgrade look like a cost improvement and let the gate pass a change
    that had stopped being measured at all.
    """
    priced = pricing.price(model_id="anthropic.some-future-model", input_tokens=100_000)
    assert priced["usd"] is None
    assert "no rate card" in priced["unpriced_reason"]
    assert priced["usd"] != 0


def test_the_parts_sum_to_the_whole():
    priced = pricing.price(
        model_id=SONNET,
        input_tokens=1_234,
        output_tokens=567,
        cache_read_tokens=8_910,
        cache_write_tokens=1_112,
        cache_ttl="5m",
    )
    assert priced["usd"] == pytest.approx(sum(priced["usd_detail"].values()), abs=5e-7)


def test_malformed_published_rates_fall_back_loudly(monkeypatch, caplog):
    """A broken override must not silently price against the built-in table.

    Absent rates are normal and stay quiet; rates that someone *set* and got wrong mean the bill
    is being computed from something other than what they wrote.
    """
    monkeypatch.setattr(pricing, "_rates", None)
    monkeypatch.setenv(pricing.RATES_VAR, "{not json")
    with caplog.at_level("WARNING"):
        priced = pricing.price(model_id=SONNET, input_tokens=1_000)
    assert priced["usd"] == 0.003
    assert any("unusable" in r.getMessage() for r in caplog.records)


def test_published_rates_override_the_built_in_table(monkeypatch):
    monkeypatch.setattr(pricing, "_rates", None)
    monkeypatch.setenv(
        pricing.RATES_VAR,
        f'{{"version": "test-card", "rates": {{"{SONNET}": {{"input": 30.0}}}}}}',
    )
    priced = pricing.price(model_id=SONNET, input_tokens=1_000)
    assert priced["usd"] == 0.03, "ten times the list rate, so the override is really in effect"
    assert priced["rate_version"] == "test-card"


# --- the ledger's side of the seam ------------------------------------------------------------


def _trajectory(**kwargs) -> Trajectory:
    return Trajectory(
        tenant_id="globex",
        traveler_id="trv_1",
        session_id="sess_1",
        model_id=SONNET,
        prompt_version="abc123",
        **kwargs,
    )


def test_a_ledger_without_a_pricer_records_no_cost_at_all():
    """The seam that keeps `ledger.py` free of rate knowledge.

    Not merely a default: it is what lets the ledger be read as a record of facts, and lets these
    tests exercise it without a rate card.
    """
    trajectory = _trajectory()
    trajectory.record_usage({"inputTokens": 1_000, "outputTokens": 500})
    line = trajectory.as_dict()
    assert "usd" not in line
    assert line["input_tokens"] == 1_000


def test_a_ledger_with_a_pricer_carries_cost_beside_the_tokens():
    trajectory = _trajectory(pricer=pricing.price)
    trajectory.record_usage({"inputTokens": 1_000, "outputTokens": 500})
    line = trajectory.as_dict()
    assert line["usd"] == 0.0105
    assert line["rate_version"] == pricing.RATE_VERSION
    # The tokens that produced the figure stay on the same line, so it is checkable.
    assert line["input_tokens"] == 1_000
    assert line["output_tokens"] == 500


def test_cost_is_rounded_once_rather_than_per_step():
    """Two steps whose individual costs would each round, priced from the totals.

    Rounding per step and summing drifts by up to half a unit in the last place per step, and the
    gate compares this figure against a fixed threshold.
    """
    trajectory = _trajectory(pricer=pricing.price)
    trajectory.record_usage({"inputTokens": 1, "outputTokens": 1})
    trajectory.start_step()
    trajectory.record_usage({"inputTokens": 1, "outputTokens": 1})
    line = trajectory.as_dict()
    expected = pricing.price(model_id=SONNET, input_tokens=2, output_tokens=2)
    assert line["usd"] == expected["usd"]


def test_the_ttl_a_step_observed_is_the_one_used_to_price_the_trajectory():
    trajectory = _trajectory(pricer=pricing.price)
    trajectory.record_usage(
        {
            "inputTokens": 10,
            "cacheWriteInputTokens": 1_000,
            "cacheDetails": [{"inputTokens": 1_000, "ttl": "1h"}],
        }
    )
    line = trajectory.as_dict()
    assert line["step_detail"][0]["cache_ttl"] == "1h"
    assert line["usd_detail"]["cache_write"] == round(1_000 * 6.00 / 1_000_000, 6)


# --- the reflection metric, rebuilt from two real trajectories --------------------------------
#
# Both of these are verbatim shapes from the deployment's own log group, which is how the
# miscount was found: a clean one-tool answer was reporting a 50% reflection rate.


def _two_step_turn(*, tools_on_first: list[str]) -> Trajectory:
    """Step one calls tools, step two writes the answer. The commonest shape there is."""
    trajectory = _trajectory(pricer=pricing.price)
    for name in tools_on_first:
        trajectory.record_tool(name)
    trajectory.record_usage({"inputTokens": 438, "outputTokens": 69, "cacheReadInputTokens": 5901})
    trajectory.start_step()
    trajectory.record_usage({"inputTokens": 647, "outputTokens": 50, "cacheReadInputTokens": 5901})
    return trajectory


def test_the_answer_writing_step_is_not_a_reflection():
    """The bug: every turn ends by writing a reply, and writing a reply calls no tool.

    Observed on the deployment — `steps: 2, reflection_steps: 1` for a single `get_travel_policy`
    answer. That is a 50% reflection rate on a trajectory with nothing wrong with it, against a
    gate threshold of 15% max, so the threshold could never have been met.
    """
    line = _two_step_turn(tools_on_first=["get_travel_policy"]).as_dict()
    assert line["steps"] == 2
    assert line["reflection_steps"] == 0, "a tool call then an answer wastes nothing"
    assert line["step_detail"][1]["tools_called"] == [], "the answer step still calls no tool"
    assert line["step_detail"][1]["reflection"] is False


def test_a_middle_step_that_acquires_nothing_is_a_reflection():
    """The real thing the metric is for: reasoning that went nowhere, mid-trajectory."""
    trajectory = _trajectory(pricer=pricing.price)
    trajectory.record_tool("get_travel_policy")
    trajectory.record_usage({"inputTokens": 400, "outputTokens": 60})
    trajectory.start_step()  # acquires nothing, and is followed by more work
    trajectory.record_usage({"inputTokens": 500, "outputTokens": 70})
    trajectory.start_step()
    trajectory.record_tool("search_policy_knowledge")
    trajectory.record_usage({"inputTokens": 600, "outputTokens": 40})
    trajectory.start_step()
    trajectory.record_usage({"inputTokens": 700, "outputTokens": 90})  # the answer
    line = trajectory.as_dict()
    assert line["steps"] == 4
    assert line["reflection_steps"] == 1, "only the toolless middle step counts"
    assert [s["reflection"] for s in line["step_detail"]] == [False, True, False, False]


def test_a_single_step_turn_has_no_reflections():
    """The degenerate case, where an off-by-one is easiest to introduce."""
    trajectory = _trajectory(pricer=pricing.price)
    trajectory.record_usage({"inputTokens": 300, "outputTokens": 40})
    line = trajectory.as_dict()
    assert line["steps"] == 1
    assert line["reflection_steps"] == 0


def test_a_real_warm_trajectory_prices_as_measured():
    """A verbatim warm turn from the deployment, priced.

    Kept because it is the number Ep5 quotes, and because it shows why the additive cache reading
    matters: `cache_read` is the *largest* component here at 41% of the turn, so pricing cache
    tokens as though they were already inside `inputTokens` would under-report this turn by 41%.
    """
    line = _two_step_turn(tools_on_first=["get_travel_policy"]).as_dict()
    assert line["input_tokens"] == 1_085
    assert line["output_tokens"] == 119
    assert line["cache_read_tokens"] == 11_802
    assert line["cache_write_tokens"] == 0

    detail = line["usd_detail"]
    assert detail["input"] == round(1_085 * 3.00 / 1_000_000, 6)
    assert detail["output"] == round(119 * 15.00 / 1_000_000, 6)
    assert detail["cache_read"] == round(11_802 * 0.30 / 1_000_000, 6)
    assert line["usd"] == 0.008581

    # The claim in the docstring, asserted rather than asserted-in-prose.
    assert detail["cache_read"] == max(detail.values())
    assert detail["cache_read"] / line["usd"] > 0.40
