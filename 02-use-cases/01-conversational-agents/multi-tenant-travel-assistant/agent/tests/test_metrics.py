"""The EMF document a trajectory publishes.

Worth asserting rather than eyeballing, because every failure here is silent by construction: a
malformed EMF document is still a perfectly valid log line. CloudWatch simply does not create the
metric, and the dashboard stays empty while the logs look fine.

Two properties carry real money:

  * **an unpriced trajectory must not publish a zero cost**, which would flatter every average it
    lands in, and
  * **`session_id` and `traveler_id` must stay fields, never dimensions** — a dimension per
    conversation is a custom metric per conversation.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parents[1] / "MultiTenantTravel" / "app" / "MultiTenantTravel"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

import metrics  # noqa: E402
import pricing  # noqa: E402
from ledger import Trajectory  # noqa: E402

SONNET = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
log = logging.getLogger("test")


def _line(*, pricer=pricing.price, tenant="globex", outcome="completed") -> dict:
    trajectory = Trajectory(
        tenant_id=tenant,
        traveler_id="trv_bbc2e338c41a",
        session_id="sess_abc",
        model_id=SONNET,
        prompt_version="abc123",
        pricer=pricer,
    )
    trajectory.outcome = outcome
    # The same verbatim warm turn from the deployment that `test_pricing` pins, so the two suites
    # cannot drift on what this trajectory costs.
    trajectory.record_tool("get_travel_policy")
    trajectory.record_usage({"inputTokens": 438, "outputTokens": 69, "cacheReadInputTokens": 5_901})
    trajectory.start_step()
    trajectory.record_usage({"inputTokens": 647, "outputTokens": 50, "cacheReadInputTokens": 5_901})
    return trajectory.as_dict()


def _metric_names(document: dict) -> set[str]:
    return {m["Name"] for m in document["_aws"]["CloudWatchMetrics"][0]["Metrics"]}


def _dimension_names(document: dict) -> list[str]:
    return document["_aws"]["CloudWatchMetrics"][0]["Dimensions"][0]


def test_the_document_is_shaped_the_way_cloudwatch_requires():
    """A malformed EMF block is still a valid log line, so nothing complains — it just never
    becomes a metric."""
    document = metrics.publish_trajectory(log, _line())
    block = document["_aws"]["CloudWatchMetrics"][0]

    assert block["Namespace"] == "MultiTenantTravel"
    assert isinstance(document["_aws"]["Timestamp"], int)
    assert isinstance(block["Dimensions"][0], list), "Dimensions is a list of dimension-set lists"
    # Every declared metric and dimension must also exist as a top-level member, or CloudWatch
    # drops it silently.
    for name in _metric_names(document):
        assert name in document, f"{name} declared but not present as a value"
    for name in _dimension_names(document):
        assert name in document, f"{name} declared as a dimension but not present"


def test_cost_is_published_with_no_unit_rather_than_as_a_count():
    document = metrics.publish_trajectory(log, _line())
    units = {m["Name"]: m["Unit"] for m in document["_aws"]["CloudWatchMetrics"][0]["Metrics"]}
    assert units["TrajectoryCostUsd"] == "None", "there is no currency unit; Count would lie"
    assert units["TrajectorySteps"] == "Count"
    assert document["TrajectoryCostUsd"] == 0.008581, "the measured warm turn"


def test_an_unpriced_trajectory_publishes_no_cost_and_flags_the_gap():
    """Zero would make a rate-card gap look like a free turn.

    And the gap gets its own counter, because an unpriced deployment is a reporting outage that
    nothing else notices.
    """
    document = metrics.publish_trajectory(log, _line(pricer=None))
    assert "TrajectoryCostUsd" not in _metric_names(document)
    assert "TrajectoryCostUsd" not in document
    assert document["UnpricedTrajectories"] == 1


def test_the_tenant_is_a_dimension_and_the_conversation_is_not():
    """The cardinality rule from `metrics.py`'s docstring, asserted so it cannot be relaxed.

    A dimension per traveller or per conversation is a custom CloudWatch metric per traveller or per
    conversation, which is the expensive mistake this whole module is arranged to avoid — and it is
    one line to make, so it needs a test rather than a comment.
    """
    document = metrics.publish_trajectory(log, _line())
    dimensions = _dimension_names(document)

    assert "tenant_id" in dimensions
    assert "outcome" in dimensions
    assert "session_id" not in dimensions, "one metric per conversation"
    assert "traveler_id" not in dimensions, "one metric per person"
    # Still present, as fields, so a single conversation remains findable in the logs.
    assert document["session_id"] == "sess_abc"
    assert document["traveler_id"] == "trv_bbc2e338c41a"


def test_an_unresolved_tenant_lands_in_a_named_bucket_rather_than_vanishing():
    """Cost nobody owns is the thing to notice, not the thing to drop."""
    document = metrics.publish_trajectory(log, _line(tenant=None))
    assert document["tenant_id"] == metrics.UNKNOWN_TENANT
    assert document["TrajectoryCostUsd"] > 0, "the spend still happened"


def test_the_outcome_dimension_carries_the_escalated_path():
    """CPRT needs resolved-vs-not to be a dimension, so a handoff can be counted as resolved."""
    document = metrics.publish_trajectory(log, _line(outcome="escalated_budget"))
    assert document["outcome"] == "escalated_budget"
    assert document["Trajectories"] == 1


def test_a_broken_line_does_not_take_the_turn_down():
    """A metric is not worth a conversation.

    Both cases return `None` rather than raising: a missing line (nothing to read) and a line
    carrying something unserialisable (nothing to write).
    """
    assert metrics.publish_trajectory(log, None) is None
    assert metrics.publish_trajectory(log, {"steps": object()}) is None


def test_the_published_numbers_match_the_ledger_line_exactly():
    """One source, so a graph and a log line cannot disagree about the same turn."""
    line = _line()
    document = metrics.publish_trajectory(log, line)
    assert document["TrajectorySteps"] == line["steps"]
    assert document["ReflectionSteps"] == line["reflection_steps"]
    assert document["CacheReadTokens"] == line["cache_read_tokens"]
    assert document["InputTokens"] == line["input_tokens"]
    assert document["OutputTokens"] == line["output_tokens"]
    assert document["TrajectoryCostUsd"] == line["usd"]
