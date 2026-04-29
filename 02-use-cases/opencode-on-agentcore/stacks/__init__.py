# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""OpenCode on AgentCore — CDK stacks package.

Shared helpers for tagging, naming conventions, and CloudWatch log retention mapping.
"""

import aws_cdk as cdk
from aws_cdk import aws_logs as logs
from constructs import Construct

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_PREFIX = "OpenCode"

# ---------------------------------------------------------------------------
# CloudWatch log retention mapping
# ---------------------------------------------------------------------------
_RETENTION_MAP = {
    1: logs.RetentionDays.ONE_DAY,
    3: logs.RetentionDays.THREE_DAYS,
    5: logs.RetentionDays.FIVE_DAYS,
    7: logs.RetentionDays.ONE_WEEK,
    14: logs.RetentionDays.TWO_WEEKS,
    30: logs.RetentionDays.ONE_MONTH,
    60: logs.RetentionDays.TWO_MONTHS,
    90: logs.RetentionDays.THREE_MONTHS,
    120: logs.RetentionDays.FOUR_MONTHS,
    150: logs.RetentionDays.FIVE_MONTHS,
    180: logs.RetentionDays.SIX_MONTHS,
    365: logs.RetentionDays.ONE_YEAR,
    400: logs.RetentionDays.THIRTEEN_MONTHS,
    545: logs.RetentionDays.EIGHTEEN_MONTHS,
    731: logs.RetentionDays.TWO_YEARS,
    1096: logs.RetentionDays.THREE_YEARS,
    1827: logs.RetentionDays.FIVE_YEARS,
}


def retention_days(days: int) -> logs.RetentionDays:
    """Convert an integer number of days to the nearest valid RetentionDays enum value."""
    if days in _RETENTION_MAP:
        return _RETENTION_MAP[days]
    for d in sorted(_RETENTION_MAP):
        if d >= days:
            return _RETENTION_MAP[d]
    return logs.RetentionDays.ONE_YEAR


# ---------------------------------------------------------------------------
# Naming helpers
# ---------------------------------------------------------------------------
def resource_name(suffix: str) -> str:
    """Return a consistent resource name like 'opencode-<suffix>'."""
    return f"opencode-{suffix}"


# ---------------------------------------------------------------------------
# Tagging helper
# ---------------------------------------------------------------------------
def apply_standard_tags(scope: Construct) -> None:
    """Apply standard tags to all resources within a construct scope."""
    cdk.Tags.of(scope).add("Project", PROJECT_PREFIX)
    cdk.Tags.of(scope).add("ManagedBy", "CDK")


# ---------------------------------------------------------------------------
# Context value helpers
# ---------------------------------------------------------------------------
def context_bool(scope: Construct, key: str, default: bool = False) -> bool:
    """Normalize a CDK context value to a Python bool.

    CDK context values from ``cdk.json`` arrive as native Python types, but
    CLI overrides (``-c key=true``) always arrive as strings.  This helper
    handles both cases so callers don't need ``is True`` checks.

    Returns *default* when the key is missing (``None``).
    """
    value = scope.node.try_get_context(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "on"}
    return default
