"""The two seed tenants.

Their policies are opposite on purpose. The same question — "can I book business
class to Singapore?", "is this hotel in policy?" — must produce a different,
correct answer for each, and that contrast is the whole multi-tenancy demo. If
the policies were similar you would need to read logs to see isolation working;
made opposite, a 30-second conversation shows it.

Globex   — permissive: business every 4th international trip, 4-star / $250, USD.
Initech  — strict: economy always, 3-star / EUR 150, 7-day advance, EUR.

The trip-count rule (rather than a duration rule) is Globex's air policy so the
sample exercises the interesting case: a verdict that depends on travel history,
computed in code and narrated by the model.
"""

from app.models import (
    BookingMode,
    CabinClass,
    Currency,
    Money,
    PolicyCore,
    PolicyRule,
    TenantConfig,
    TravelPolicy,
)
from app.models.policy import CabinRule, CabinRuleType, EntitlementPeriod

GLOBEX = TenantConfig(
    tenant_id="globex",
    display_name="Globex Corporation",
    currency=Currency.USD,
    booking_mode=BookingMode.CONFIRM_IN_CHAT,
    home_country="US",
    support_queue="globex-travel-desk",
)

INITECH = TenantConfig(
    tenant_id="initech",
    display_name="Initech",
    currency=Currency.EUR,
    booking_mode=BookingMode.HANDOFF,
    home_country="IE",
    support_queue="initech-travel-desk",
)


def globex_policies() -> list[TravelPolicy]:
    return [
        TravelPolicy(
            tenant_id="globex",
            topic="air",
            version="2026.1",
            core=PolicyCore(
                cabin_rule=CabinRule(
                    type=CabinRuleType.TRIP_COUNT,
                    cabin=CabinClass.BUSINESS,
                    every_nth_trip=4,
                    period=EntitlementPeriod.CALENDAR_YEAR,
                ),
                refundable_allowed=True,
            ),
            rules=[
                PolicyRule(
                    code="business_every_fourth",
                    applies_to="air",
                    description=(
                        "Business class is permitted on every 4th international trip "
                        "within a calendar year."
                    ),
                ),
                PolicyRule(
                    code="ancillary_wifi",
                    applies_to="air",
                    description="In-flight wifi is reimbursable on flights over 3 hours.",
                ),
            ],
        ),
        TravelPolicy(
            tenant_id="globex",
            topic="hotel",
            version="2026.1",
            core=PolicyCore(
                hotel_nightly_cap=Money(amount=250, currency=Currency.USD),
                max_hotel_star_rating=4,
            ),
            rules=[
                PolicyRule(
                    code="breakfast_reimbursable",
                    applies_to="hotel",
                    description="Breakfast is reimbursable when not included in the room rate.",
                ),
            ],
        ),
        TravelPolicy(
            tenant_id="globex",
            topic="general",
            version="2026.1",
            rules=[
                PolicyRule(
                    code="car_insurance",
                    applies_to="car",
                    description="Decline the rental collision waiver — corporate policy covers it.",
                ),
            ],
        ),
    ]


def initech_policies() -> list[TravelPolicy]:
    return [
        TravelPolicy(
            tenant_id="initech",
            topic="air",
            version="2026.1",
            core=PolicyCore(
                cabin_rule=CabinRule(type=CabinRuleType.NEVER),
                advance_purchase_days=7,
                refundable_allowed=False,
            ),
            rules=[
                PolicyRule(
                    code="economy_only",
                    applies_to="air",
                    description="Economy class only, on all flights regardless of duration.",
                ),
                PolicyRule(
                    code="advance_purchase",
                    applies_to="air",
                    description="Flights must be booked at least 7 days before departure.",
                ),
            ],
        ),
        TravelPolicy(
            tenant_id="initech",
            topic="hotel",
            version="2026.1",
            core=PolicyCore(
                hotel_nightly_cap=Money(amount=150, currency=Currency.EUR),
                max_hotel_star_rating=3,
            ),
            rules=[
                PolicyRule(
                    code="no_upgrades",
                    applies_to="hotel",
                    description="Room upgrades are not reimbursable.",
                ),
            ],
        ),
    ]


TENANTS = [GLOBEX, INITECH]
POLICIES = globex_policies() + initech_policies()
