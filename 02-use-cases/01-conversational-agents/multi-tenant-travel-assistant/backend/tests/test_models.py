"""Model-level tests.

These cover the parts a model must never be trusted to compute: policy verdicts,
cabin thresholds, cap comparisons, offer expiry. The eval gate asserts
`verdict_exact_match: 1.00`, which is only meaningful if the arithmetic behind it
is pinned here.
"""

from datetime import datetime, timedelta

import pytest

from app.models import (
    OFFER_TTL_MINUTES,
    Airport,
    CabinClass,
    CabinRule,
    Currency,
    HeldOffer,
    Money,
    OfferStatus,
    PolicyCore,
    PolicyRule,
    PolicyStatus,
    TravelKind,
    TravelPolicy,
    tenant_pk,
)
from app.models.policy import CabinRuleType


@pytest.fixture
def globex() -> TravelPolicy:
    """Permissive tenant: business above 8h, 4 star / $250 cap, USD."""
    return TravelPolicy(
        tenant_id="globex",
        topic="air",
        version="2026.1",
        core=PolicyCore(
            hotel_nightly_cap=Money(amount=250, currency=Currency.USD),
            max_hotel_star_rating=4,
            cabin_rule=CabinRule(
                type=CabinRuleType.DURATION,
                cabin=CabinClass.BUSINESS,
                threshold_hours=8,
            ),
        ),
        rules=[
            PolicyRule(
                code="ancillary_wifi",
                applies_to="air",
                description="In-flight wifi reimbursable on flights over 3 hours",
            ),
            PolicyRule(
                code="car_insurance",
                applies_to="car",
                description="Decline CDW — corporate policy covers it",
            ),
        ],
    )


@pytest.fixture
def initech() -> TravelPolicy:
    """Strict tenant: economy always, 3 star / EUR 150 cap, 7-day advance."""
    return TravelPolicy(
        tenant_id="initech",
        topic="air",
        version="2026.1",
        core=PolicyCore(
            hotel_nightly_cap=Money(amount=150, currency=Currency.EUR),
            max_hotel_star_rating=3,
            cabin_rule=CabinRule(type=CabinRuleType.NEVER),
            advance_purchase_days=7,
        ),
    )


class TestMoney:
    def test_cents_are_exact(self):
        # Decimal, not float — 178.50 must not become 178.49999
        assert str(Money(amount="178.50", currency=Currency.USD).amount) == "178.50"

    def test_currency_always_travels_with_amount(self):
        m = Money(amount=100, currency=Currency.EUR)
        assert m.currency == Currency.EUR
        assert "EUR" in str(m)

    def test_negative_rejected(self):
        with pytest.raises(ValueError):
            Money(amount=-1, currency=Currency.USD)


class TestCabinRule:
    def test_duration_rule_above_threshold(self, globex):
        assert globex.core.cabin_rule.permitted_cabin(13.0) == CabinClass.BUSINESS

    def test_duration_rule_below_threshold(self, globex):
        assert globex.core.cabin_rule.permitted_cabin(6.0) == CabinClass.ECONOMY

    def test_boundary_is_strictly_greater_than(self, globex):
        """Exactly 8h is NOT over 8h.

        Eval suite B tests this edge; the rule reads "over 8 hours", so equality
        must fall to economy.
        """
        assert globex.core.cabin_rule.permitted_cabin(8.0) == CabinClass.ECONOMY
        assert globex.core.cabin_rule.permitted_cabin(8.01) == CabinClass.BUSINESS

    def test_never_rule_ignores_duration(self, initech):
        assert initech.core.cabin_rule.permitted_cabin(13.0) == CabinClass.ECONOMY


class TestTenantContrast:
    """The same question must yield different, correct answers per tenant."""

    def test_business_on_long_haul(self, globex, initech):
        assert globex.air_status(CabinClass.BUSINESS, 13.0) == PolicyStatus.IN_POLICY
        assert initech.air_status(CabinClass.BUSINESS, 13.0) == PolicyStatus.OUT_OF_POLICY

    def test_cheaper_cabin_always_allowed(self, globex):
        assert globex.air_status(CabinClass.ECONOMY, 13.0) == PolicyStatus.IN_POLICY

    def test_hotel_caps_differ(self, globex, initech):
        assert (
            globex.hotel_status(Money(amount=200, currency=Currency.USD), 4)
            == PolicyStatus.IN_POLICY
        )
        assert (
            initech.hotel_status(Money(amount=200, currency=Currency.EUR), 3)
            == PolicyStatus.OUT_OF_POLICY
        )


class TestHotelStatus:
    def test_over_cap(self, globex):
        assert (
            globex.hotel_status(Money(amount=300, currency=Currency.USD), 4)
            == PolicyStatus.OUT_OF_POLICY
        )

    def test_star_rating_over_limit(self, globex):
        assert (
            globex.hotel_status(Money(amount=100, currency=Currency.USD), 5)
            == PolicyStatus.OUT_OF_POLICY
        )

    def test_cross_currency_requires_approval(self, initech):
        """We don't fake FX. An unresolvable comparison escalates, never guesses."""
        assert (
            initech.hotel_status(Money(amount=100, currency=Currency.USD), 3)
            == PolicyStatus.REQUIRES_APPROVAL
        )


class TestPolicyRules:
    def test_rules_filtered_by_topic_including_general(self, globex):
        air = {r.code for r in globex.rules_for("air")}
        assert "ancillary_wifi" in air
        assert "car_insurance" not in air

    def test_loose_rules_are_not_computed_on(self, globex):
        """Narrated, never evaluated — they carry no machine-readable value."""
        for rule in globex.rules:
            assert set(type(rule).model_fields) == {"code", "applies_to", "description"}


class TestHeldOffer:
    def _offer(self, now: datetime) -> HeldOffer:
        return HeldOffer(
            tenant_id="globex",
            traveler_id="trv_31d81fa59772",
            offer_id="off_1",
            kind=TravelKind.AIR,
            option_id="opt_1",
            frozen_price=Money(amount=612, currency=Currency.USD),
            payment_profile_id="pp_1",
            policy_status=PolicyStatus.IN_POLICY,
            held_at=now,
            expires_at=now + timedelta(minutes=OFFER_TTL_MINUTES),
        )

    def test_valid_before_expiry(self):
        now = datetime(2026, 8, 2, 12, 0)
        assert self._offer(now).is_valid_at(now + timedelta(minutes=5))

    def test_invalid_after_expiry(self):
        now = datetime(2026, 8, 2, 12, 0)
        assert not self._offer(now).is_valid_at(now + timedelta(minutes=11))

    def test_consumed_offer_cannot_be_reused(self):
        """Idempotency: a double-click must not book twice."""
        now = datetime(2026, 8, 2, 12, 0)
        offer = self._offer(now)
        offer.status = OfferStatus.CONSUMED
        assert not offer.is_valid_at(now)


class TestAirportDistance:
    def test_known_route_is_plausible(self):
        """Coordinates exist so durations are believable, not exact."""
        dub = Airport(
            code="DUB",
            name="Dublin",
            city="Dublin",
            country="IE",
            latitude=53.4213,
            longitude=-6.2701,
        )
        atl = Airport(
            code="ATL",
            name="Hartsfield-Jackson",
            city="Atlanta",
            country="US",
            latitude=33.6407,
            longitude=-84.4277,
        )
        assert 6000 < dub.distance_km(atl) < 6600  # great-circle ~6320 km


class TestTenantKey:
    def test_partition_key_is_prefixed(self):
        """`dynamodb:LeadingKeys` constrains this exact string at the IAM layer."""
        assert tenant_pk("globex") == "TENANT#globex"
