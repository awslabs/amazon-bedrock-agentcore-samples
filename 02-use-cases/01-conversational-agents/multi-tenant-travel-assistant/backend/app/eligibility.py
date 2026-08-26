"""Counting travel history for entitlement rules.

Some policies grant a benefit every Nth international trip. Answering "can I
book business class?" then depends on *history*, not just the trip in hand — so
something has to count, and that something must be code.

This module is deliberately small and pure: trips in, count out. It exists as a
named unit because it is exactly the kind of arithmetic a model would be happy
to attempt and occasionally get wrong, and because the eval gate asserts
`verdict_exact_match: 1.00` against it.
"""

from datetime import date, timedelta

from .models import Trip, TripStatus
from .models.policy import CabinRule, CabinRuleType, EntitlementPeriod

ROLLING_WINDOW_DAYS = 365


def period_start(period: EntitlementPeriod, as_of: date) -> date:
    """First day of the entitlement window containing `as_of`."""
    if period is EntitlementPeriod.CALENDAR_YEAR:
        return date(as_of.year, 1, 1)
    return as_of - timedelta(days=ROLLING_WINDOW_DAYS)


def count_international_trips(
    trips: list[Trip],
    rule: CabinRule,
    as_of: date,
    exclude_trip_id: str | None = None,
) -> int:
    """Count a traveller's international trips inside the rule's window.

    `exclude_trip_id` drops the trip being asked about, so a booked trip does not
    count itself as prior history.

    Which trips count is policy, not preference: `count_upcoming` decides whether
    a reserved-but-not-taken trip already consumes the entitlement. The stricter
    reading (it does) is the default — otherwise booking two trips in one sitting
    could claim the benefit twice.
    """
    if rule.type is not CabinRuleType.TRIP_COUNT:
        return 0

    start = period_start(rule.period, as_of)
    allowed_statuses = {TripStatus.PAST, TripStatus.IN_PROGRESS}
    if rule.count_upcoming:
        allowed_statuses.add(TripStatus.UPCOMING)

    return sum(
        1
        for trip in trips
        if trip.trip_id != exclude_trip_id
        and trip.is_international
        and trip.status in allowed_statuses
        and start <= trip.starts_on <= as_of + timedelta(days=ROLLING_WINDOW_DAYS)
    )
