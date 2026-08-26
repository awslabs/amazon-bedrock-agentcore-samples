"""Logging and metrics.

Two distinct jobs, deliberately kept separate:

**Logs answer "what happened in session X".** Decisions, refusals, tenant
resolutions, authorization outcomes — read by a human reconstructing a
trajectory. Structured JSON so `tenant_id` is greppable.

**Metrics answer "what is the p95 across all sessions".** Emitted as CloudWatch
EMF: one log line that CloudWatch converts into a dimensioned metric, with no
`PutMetricData` call to pay for and no extraction pipeline to run.

The split matters because of **cardinality**. An EMF dimension creates a distinct
metric per value, so `tenant_id` (a handful of values) is safe while
`traveler_id` or `session_id` would create one metric per person or per
conversation and become expensive quickly. Those stay log *fields*, never
dimensions — an easy mistake with a real bill attached.
"""

import os
from typing import Any

from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit, single_metric

SERVICE_NAME = os.environ.get("POWERTOOLS_SERVICE_NAME", "multi-tenant-travel")
METRICS_NAMESPACE = "MultiTenantTravel"

logger = Logger(service=SERVICE_NAME)
metrics = Metrics(namespace=METRICS_NAMESPACE, service=SERVICE_NAME)


def bind_request_context(
    tenant_id: str | None = None,
    traveler_id: str | None = None,
    session_id: str | None = None,
) -> None:
    """Attach the dimensions every subsequent log line should carry.

    These are the same dimensions the audit trail and the cost ledger use.
    Attribution cannot be retrofitted onto historical logs, so a line without
    them is a line you cannot answer questions about later.
    """
    logger.append_keys(
        **{
            k: v
            for k, v in {
                "tenant_id": tenant_id,
                "traveler_id": traveler_id,
                "session_id": session_id,
            }.items()
            if v is not None
        }
    )


# Caller facts are nested under a single key rather than spread at the top level.
# Powertools ultimately passes them to stdlib logging, whose LogRecord reserves
# `name`, `msg`, `args`, `levelname`, `module` and others — and it *raises* on
# collision rather than ignoring it. `name` is precisely what a traveller-name
# resolution wants to log, so nesting is the only version that cannot break on a
# field a caller reasonably chooses.
def log_decision(decision: str, **facts: Any) -> None:
    """Record what the system *concluded*, not merely what it did.

    "called the backend" is nearly useless; "resolved 'Sam' to 2 candidates within
    adaeze's authorised list -> asking user" says what was decided and why. Every
    authorization outcome, deterministic verdict and refusal goes through here.
    """
    logger.info(decision, decision=decision, facts=facts)


def log_refusal(reason: str, **facts: Any) -> None:
    """A refusal is an expected outcome, not a fault.

    Warning rather than error so real failures stay visible — but never silent,
    because a silent refusal is indistinguishable from a bug.
    """
    logger.warning(reason, refusal=reason, facts=facts)
    count("Refusals", reason=reason)


def count(name: str, *, reason: str | None = None, tool: str | None = None) -> None:
    """Emit an EMF counter.

    Dimensions are restricted to low-cardinality values on purpose — see the
    module docstring. Anything identifying a person or a session belongs in the
    log line, not here.
    """
    observe(
        name,
        1,
        MetricUnit.Count,
        **{k: v for k, v in {"tool": tool, "reason": reason}.items() if v},
    )


# `single_metric` rather than the shared `metrics` object, and the reason is a bug
# we hit: dimensions added to the module-level Metrics instance persist until
# flush, so they accumulate across unrelated calls. A refusal tagged
# `reason=ambiguous_name` would leave that dimension attached to the next metric
# emitted, and a second refusal in the same invocation warns about overwriting it.
# Each metric here is independent, so each gets its own EMF blob and its own
# dimension set. The cost is one extra log line per metric, which is the correct
# trade against silently mis-attributed cost data.
def observe(
    name: str,
    value: float,
    unit: MetricUnit = MetricUnit.Count,
    **dimensions: str,
) -> None:
    """Emit an EMF metric with its own isolated dimension set.

    Used by the ledger for tokens and spend. Callers pass only low-cardinality
    dimensions (`tenant_id`, `tool`, `outcome`) — see the module docstring for why
    `session_id` must never appear here.
    """
    with single_metric(name=name, unit=unit, value=value, namespace=METRICS_NAMESPACE) as metric:
        metric.add_dimension(name="service", value=SERVICE_NAME)
        for key, dim_value in dimensions.items():
            metric.add_dimension(name=key, value=dim_value)


__all__ = [
    "MetricUnit",
    "bind_request_context",
    "count",
    "log_decision",
    "log_refusal",
    "logger",
    "metrics",
    "observe",
]
