"""Trip-count entitlement tests.

"Business class every 4th international trip" is the pattern where a model would
most plausibly try to help by counting — and occasionally miscount. These tests
pin the arithmetic the eval gate asserts against.
"""

from datetime import date

import pytest

from app.eligibility import count_international_trips, period_start
from app.models import CabinClass, Place, PolicyStatus, Trip, TripStatus
from app.models.policy import (
    CabinRule,
    CabinRuleType,
    EntitlementPeriod,
    PolicyCore,
    TravelPolicy,
)
from app.models.trip import AirSegment

AS_OF = date(2026, 9, 15)


def trip(
    trip_id: str,
    starts_on: date,
    *,
    international: bool,
    status: TripStatus = TripStatus.PAST,
) -> Trip:
    """A trip whose only interesting property is whether it was international."""
    return Trip(
        tenant_id="globex",
        traveler_id="trv_31d81fa59772",
        trip_id=trip_id,
        label=f"Trip {trip_id}",
        status=status,
        starts_on=starts_on,
        ends_on=starts_on,
        destination=Place(name="Somewhere", city="Somewhere", country="US"),
        air_segments=[
            AirSegment(
                carrier="EI",
                flight_number="EI100",
                depart_airport="DUB",
                depart_at=f"{starts_on}T09:00:00",
                arrive_airport="ATL" if international else "LHR",
                arrive_at=f"{starts_on}T17:00:00",
                cabin=CabinClass.ECONOMY,
                is_international=international,
            )
        ],
    )


@pytest.fixture
def every_fourth() -> CabinRule:
    return CabinRule(
        type=CabinRuleType.TRIP_COUNT,
        cabin=CabinClass.BUSINESS,
        every_nth_trip=4,
        period=EntitlementPeriod.CALENDAR_YEAR,
    )


class TestCounting:
    def test_counts_only_international(self, every_fourth):
        trips = [
            trip("t1", date(2026, 2, 1), international=True),
            trip("t2", date(2026, 3, 1), international=False),
            trip("t3", date(2026, 4, 1), international=True),
        ]
        assert count_international_trips(trips, every_fourth, AS_OF) == 2

    def test_ignores_trips_before_the_window(self, every_fourth):
        """A calendar-year rule resets in January."""
        trips = [
            trip("old", date(2025, 11, 1), international=True),
            trip("new", date(2026, 2, 1), international=True),
        ]
        assert count_international_trips(trips, every_fourth, AS_OF) == 1

    def test_rolling_window_looks_back_12_months(self):
        rule = CabinRule(
            type=CabinRuleType.TRIP_COUNT,
            cabin=CabinClass.BUSINESS,
            every_nth_trip=4,
            period=EntitlementPeriod.ROLLING_12_MONTHS,
        )
        trips = [
            trip("late_2025", date(2025, 11, 1), international=True),
            trip("early_2026", date(2026, 2, 1), international=True),
        ]
        # Both fall inside a rolling year from Sept 2026 — the same data gives a
        # different answer than the calendar-year rule. That's why period is data.
        assert count_international_trips(trips, rule, AS_OF) == 2

    def test_upcoming_counts_by_default(self, every_fourth):
        """A reserved trip consumes the entitlement — otherwise booking two in
        one sitting could claim the benefit twice."""
        trips = [
            trip("past", date(2026, 2, 1), international=True),
            trip("booked", date(2026, 11, 1), international=True, status=TripStatus.UPCOMING),
        ]
        assert count_international_trips(trips, every_fourth, AS_OF) == 2

    def test_upcoming_excluded_when_policy_says_so(self):
        rule = CabinRule(
            type=CabinRuleType.TRIP_COUNT,
            cabin=CabinClass.BUSINESS,
            every_nth_trip=4,
            count_upcoming=False,
        )
        trips = [
            trip("past", date(2026, 2, 1), international=True),
            trip("booked", date(2026, 11, 1), international=True, status=TripStatus.UPCOMING),
        ]
        assert count_international_trips(trips, rule, AS_OF) == 1

    def test_excludes_the_trip_under_consideration(self, every_fourth):
        """The trip being asked about is not its own prior history."""
        trips = [
            trip("t1", date(2026, 2, 1), international=True),
            trip("this_one", date(2026, 9, 20), international=True, status=TripStatus.UPCOMING),
        ]
        count = count_international_trips(trips, every_fourth, AS_OF, exclude_trip_id="this_one")
        assert count == 1

    def test_non_count_rule_returns_zero(self):
        duration_rule = CabinRule(
            type=CabinRuleType.DURATION, cabin=CabinClass.BUSINESS, threshold_hours=8
        )
        trips = [trip("t1", date(2026, 2, 1), international=True)]
        assert count_international_trips(trips, duration_rule, AS_OF) == 0


class TestVerdict:
    """The 4th trip earns business; the 1st through 3rd do not."""

    @pytest.mark.parametrize(
        ("prior", "expected"),
        [
            (0, CabinClass.ECONOMY),
            (1, CabinClass.ECONOMY),
            (2, CabinClass.ECONOMY),
            (3, CabinClass.BUSINESS),  # this trip is the 4th
            (4, CabinClass.ECONOMY),
            (7, CabinClass.BUSINESS),  # the 8th
        ],
    )
    def test_every_fourth_trip(self, every_fourth, prior, expected):
        assert every_fourth.permitted_cabin(13.0, prior) == expected

    def test_flight_length_is_irrelevant_to_a_count_rule(self, every_fourth):
        assert every_fourth.permitted_cabin(1.0, 3) == CabinClass.BUSINESS

    def test_missing_history_denies_rather_than_grants(self, every_fourth):
        """Absent evidence must not confer a benefit."""
        assert every_fourth.permitted_cabin(13.0, None) == CabinClass.ECONOMY

    def test_trips_until_entitled(self, every_fourth):
        assert every_fourth.trips_until_entitled(0) == 3
        assert every_fourth.trips_until_entitled(2) == 1
        assert every_fourth.trips_until_entitled(3) == 0
        assert every_fourth.trips_until_entitled(4) == 3

    def test_trips_until_entitled_is_none_for_other_rules(self):
        rule = CabinRule(type=CabinRuleType.DURATION, threshold_hours=8)
        assert rule.trips_until_entitled(3) is None


class TestAirStatusWithHistory:
    def test_policy_grants_business_on_the_fourth(self, every_fourth):
        policy = TravelPolicy(
            tenant_id="globex",
            topic="air",
            version="2026.1",
            core=PolicyCore(cabin_rule=every_fourth),
        )
        assert (
            policy.air_status(CabinClass.BUSINESS, 13.0, prior_international_trips=3)
            is PolicyStatus.IN_POLICY
        )
        assert (
            policy.air_status(CabinClass.BUSINESS, 13.0, prior_international_trips=1)
            is PolicyStatus.OUT_OF_POLICY
        )


class TestPeriodStart:
    def test_calendar_year(self):
        assert period_start(EntitlementPeriod.CALENDAR_YEAR, AS_OF) == date(2026, 1, 1)

    def test_rolling(self):
        assert period_start(EntitlementPeriod.ROLLING_12_MONTHS, AS_OF) == date(2025, 9, 15)
