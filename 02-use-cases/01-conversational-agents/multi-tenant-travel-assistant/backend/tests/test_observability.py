"""Observability helpers.

Small surface, but load-bearing: the tokenomics story is only as good as the
dimensions on the metrics, and a mis-attributed metric is worse than a missing
one because it looks like data.
"""

import io
import json

import pytest

from app.observability import (
    MetricUnit,
    bind_request_context,
    count,
    log_decision,
    log_refusal,
    logger,
    observe,
)


@pytest.fixture
def log_output():
    """Capture Powertools log lines by redirecting the logger's own handler.

    Neither `capsys` nor `capfd` works here: the handler holds a reference to the
    stream it was constructed with, and pytest's logging plugin intercepts ahead
    of the file descriptor. Swapping the handler's stream is the one approach that
    reads exactly what the handler emits, formatting included.
    """
    handler = logger.registered_handler
    original = handler.stream
    buffer = io.StringIO()
    handler.setStream(buffer)
    try:
        yield buffer
    finally:
        handler.setStream(original)
        logger.remove_keys(["tenant_id", "traveler_id", "session_id"])


def _emf_blobs(captured: str) -> list[dict]:
    """EMF metrics are emitted as JSON log lines carrying `_aws`."""
    blobs = []
    for line in captured.splitlines():
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "_aws" in parsed:
            blobs.append(parsed)
    return blobs


class TestMetricIsolation:
    def test_dimensions_do_not_leak_between_metrics(self, capsys):
        """The bug this guards: dimensions added to a shared Metrics object persist.

        A refusal tagged `reason=X` used to leave that dimension attached to
        whatever metric was emitted next, silently mis-attributing it.
        """
        count("Refusals", reason="ambiguous_name")
        observe("InputTokens", 120, MetricUnit.Count, tenant_id="globex")

        blobs = _emf_blobs(capsys.readouterr().out)
        assert len(blobs) == 2

        tokens = next(b for b in blobs if "InputTokens" in b)
        assert "reason" not in tokens
        assert tokens["tenant_id"] == "globex"

    def test_repeated_reason_does_not_warn_or_overwrite(self, capsys):
        """Two refusals in one invocation are independent, not a collision."""
        count("Refusals", reason="ambiguous_name")
        count("Refusals", reason="unknown_airport")

        reasons = [b["reason"] for b in _emf_blobs(capsys.readouterr().out)]
        assert reasons == ["ambiguous_name", "unknown_airport"]

    def test_every_metric_carries_the_service_dimension(self, capsys):
        observe("Spend", 0.42, MetricUnit.Count, tenant_id="initech")
        assert all("service" in b for b in _emf_blobs(capsys.readouterr().out))


class TestLogging:
    def test_decision_facts_are_nested_not_spread(self, log_output):
        """`name` is a reserved LogRecord field and stdlib logging *raises* on it.

        Nesting caller facts is the only version that cannot break on a field a
        caller reasonably chooses — and resolving a traveller name is precisely
        the case that wants to log something called `name`.
        """
        log_decision("resolved a name", name="Sam", candidate_count=2)

        line = next(
            json.loads(raw)
            for raw in log_output.getvalue().splitlines()
            if "resolved a name" in raw
        )
        assert line["facts"]["candidate_count"] == 2
        assert line["message"] == "resolved a name"

    def test_refusal_logs_a_warning_and_counts_it(self, log_output, capsys):
        log_refusal("name matched nobody", actor_id="trv_31d81fa59772")

        assert '"level":"WARNING"' in log_output.getvalue().replace(" ", "")
        assert any("Refusals" in b for b in _emf_blobs(capsys.readouterr().out))

    def test_bound_context_appears_on_later_lines(self, log_output):
        bind_request_context(tenant_id="globex", traveler_id="trv_31d81fa59772")
        log_decision("something happened")

        line = next(
            json.loads(raw)
            for raw in log_output.getvalue().splitlines()
            if "something happened" in raw
        )
        assert line["tenant_id"] == "globex"
        assert line["traveler_id"] == "trv_31d81fa59772"
