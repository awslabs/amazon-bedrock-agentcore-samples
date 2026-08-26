"""Publish a trajectory's cost as a CloudWatch metric, dimensioned by tenant.

**Why a metric and not just the log line.** The ledger line already carries everything, and
"which tenant is expensive?" can be answered from it with a query. What a query cannot do is
alarm, or hold a p95 on a dashboard next to a deploy marker. A metric needs its dimensions at
publication time, so this is the one thing that cannot be recovered by joining afterwards.

**EMF written by hand rather than through Powertools.** The tool Lambdas use
`aws_lambda_powertools` and should keep doing so; this package deliberately carries a small
dependency set for a container that cold-starts on the conversational path, and Embedded Metric
Format is a documented, stable JSON shape. One log line, no new dependency.

**The cardinality rule, restated because it is the expensive mistake.** `tenant_id` and `outcome`
are bounded — tens of tenants, a handful of outcomes. `traveler_id` and `session_id` are not: a
dimension per person or per conversation creates a custom metric per person or per conversation.
They stay log *fields*, and `agent/tests/test_metrics.py` asserts that split so it cannot be relaxed
by accident.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

METRICS_NAMESPACE = "MultiTenantTravel"
SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "multi-tenant-travel-agent")

# A tenant that could not be resolved still has to land somewhere, and a bucket nobody owns is
# exactly the thing you want to see on the dashboard rather than have silently dropped.
UNKNOWN_TENANT = "unattributed"


def _emf(
    *,
    dimensions: dict[str, str],
    values: dict[str, tuple[float, str]],
    fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One Embedded Metric Format document.

    `values` maps a metric name to `(value, unit)`. USD is emitted as unit `None`, which is
    CloudWatch's own spelling for "a number with no unit" — there is no currency unit, and picking
    `Count` would make a cost graph claim to be a tally.
    """
    document: dict[str, Any] = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": METRICS_NAMESPACE,
                    "Dimensions": [list(dimensions)],
                    "Metrics": [{"Name": name, "Unit": unit} for name, (_, unit) in values.items()],
                }
            ],
        },
        **dimensions,
        **{name: value for name, (value, _) in values.items()},
    }
    document.update(fields or {})
    return document


def publish_trajectory(log: logging.Logger, line: dict[str, Any]) -> dict[str, Any] | None:
    """Emit the cost metrics for one finished trajectory, from the ledger's own line.

    **Derived from the emitted line rather than recomputed.** Two code paths producing "the cost"
    is how a dashboard and a log line come to disagree, and the one a reader trusts is whichever
    they saw first. This reads the line the ledger just wrote.

    **An unpriced trajectory publishes no cost, and says so with a counter.** Emitting `0.0` would
    let a rate-card gap look like a free turn, flattering every average it lands in. The gap is a
    metric of its own so it can be alarmed on — an unpriced deployment is a reporting outage, and
    nothing else notices one.

    Never raises: a metric is not worth a conversation.
    """
    try:
        dimensions = {
            "service": SERVICE_NAME,
            "tenant_id": line.get("tenant_id") or UNKNOWN_TENANT,
            "outcome": line.get("outcome") or "completed",
        }
        values: dict[str, tuple[float, str]] = {
            # The denominator of cost per resolved task. Counted per trajectory so the ratio can be
            # taken per tenant and per outcome, which is what makes "resolved" meaningful.
            "Trajectories": (1, "Count"),
            "TrajectorySteps": (line.get("steps", 0), "Count"),
            "ReflectionSteps": (line.get("reflection_steps", 0), "Count"),
            "CacheReadTokens": (line.get("cache_read_tokens", 0), "Count"),
            "InputTokens": (line.get("input_tokens", 0), "Count"),
            "OutputTokens": (line.get("output_tokens", 0), "Count"),
        }

        usd = line.get("usd")
        if isinstance(usd, int | float):
            values["TrajectoryCostUsd"] = (float(usd), "None")
        else:
            values["UnpricedTrajectories"] = (1, "Count")

        document = _emf(
            dimensions=dimensions,
            values=values,
            # Carried as fields, not dimensions — see the cardinality note in the module docstring.
            fields={
                "session_id": line.get("session_id"),
                "traveler_id": line.get("traveler_id"),
                "model_id": line.get("model_id"),
                "rate_version": line.get("rate_version"),
            },
        )
        log.info(json.dumps(document))
        return document
    except Exception:  # noqa: BLE001 - see the docstring: never fatal
        log.warning("could not publish trajectory metrics", exc_info=True)
        return None
