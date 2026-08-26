"""Logging and metrics for the tool layer.

A deliberate near-duplicate of `backend/app/observability.py`, and the duplication is
the point: `tools/` and `backend/` are separately deployed artifacts, and importing
across that boundary would couple the agent layer to the folder a reader is told to
delete. The two files stay small and are allowed to diverge.

Same two rules as the backend's version:
- **Logs** answer "what happened in session X"; **EMF metrics** answer "what is the
  p95 across all sessions".
- **Dimensions are cardinality-sensitive.** `tenant_id` and `tool` are safe;
  `traveler_id` and `session_id` would create one metric per person or per
  conversation and get expensive fast. Those stay log *fields*.
"""

from __future__ import annotations

import os
from typing import Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.metrics import MetricUnit, single_metric

SERVICE_NAME = os.environ.get("POWERTOOLS_SERVICE_NAME", "multi-tenant-travel-tools")
METRICS_NAMESPACE = "MultiTenantTravel"

logger = Logger(service=SERVICE_NAME)


def bind_request_context(**fields: str) -> None:
    """Attach dimensions to every subsequent log line in this invocation."""
    logger.append_keys(**{k: v for k, v in fields.items() if v})


def clear_request_context() -> None:
    """Drop bound keys.

    Lambda reuses a container across invocations, so without this one request's
    tenant would leak into the next request's log lines — which is worse than no
    attribution, because it is confidently wrong.
    """
    logger.remove_keys(["tenant_id", "traveler_id", "session_id", "tool"])


# Caller facts are nested rather than spread, because stdlib logging reserves
# `name`, `msg`, `args` and others on its LogRecord and *raises* on collision. A
# tool logging a traveller-name resolution would otherwise crash on the field it
# most wants to log.
def log_decision(decision: str, /, **facts: Any) -> None:
    """Record what the tool *concluded*, not merely that it ran.

    Positional-only for the same reason as `log_refusal`: a caller logging a fact
    it naturally calls `decision` must not collide with the message parameter.
    """
    logger.info(decision, decision=decision, facts=facts)


def log_refusal(refusal: str, /, **facts: Any) -> None:
    """A refusal is an expected outcome, and a silent one looks like a bug.

    Positional-only (`/`) so a caller may pass `reason=` as a *fact* without
    colliding with this parameter. Not hypothetical: `log_refusal("tool refused",
    reason=str(error))` is the natural call, and it raised `TypeError` — turning a
    clean refusal into an unhandled crash, in the exact path meant to keep failures
    clean.
    """
    logger.warning(refusal, refusal=refusal, facts=facts)
    # The metric dimension is the refusal *kind*, never a caller-supplied reason
    # string: reasons interpolate ids and messages, and one metric per distinct
    # string is the cardinality explosion the module docstring warns about.
    count("ToolRefusals", reason=refusal)


def count(name: str, *, tool: str | None = None, reason: str | None = None) -> None:
    """Emit an EMF counter with an isolated dimension set."""
    observe(
        name,
        1,
        MetricUnit.Count,
        **{k: v for k, v in {"tool": tool, "reason": reason}.items() if v},
    )


# `single_metric` per metric rather than one shared `Metrics` object: dimensions
# added to a shared instance persist until flush, so they accumulate across
# unrelated calls and silently mis-attribute the next metric emitted. One extra log
# line per metric is the right trade against wrong cost data.
def observe(
    name: str, value: float, unit: MetricUnit = MetricUnit.Count, **dimensions: str
) -> None:
    """Emit an EMF metric. Only low-cardinality dimensions belong here."""
    with single_metric(name=name, unit=unit, value=value, namespace=METRICS_NAMESPACE) as metric:
        metric.add_dimension(name="service", value=SERVICE_NAME)
        for key, dim_value in dimensions.items():
            metric.add_dimension(name=key, value=dim_value)


__all__ = [
    "MetricUnit",
    "bind_request_context",
    "clear_request_context",
    "count",
    "log_decision",
    "log_refusal",
    "logger",
    "observe",
]
