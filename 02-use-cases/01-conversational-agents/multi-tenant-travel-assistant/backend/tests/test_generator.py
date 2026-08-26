"""Generator tests.

The load-bearing assertion is determinism: if the same query returned different
options between calls, no eval assertion could hold and every cost comparison
would be noise. Everything else here checks that generated data is *coherent* —
durations plausible, policy annotation correct, filters honest.
"""

from datetime import date, datetime

import pytest

from app.models import (
    CabinClass,
    Currency,
    GenerationMode,
    HotelFilters,
    Money,
    PolicyStatus,
    SortOrder,
)
from app.models.policy import CabinRule, CabinRuleType, PolicyCore, TravelPolicy
from app.reference import (
    AmbiguousPlaceError,
    UnknownPlaceError,
    _ambiguous_places,
    resolve_airport,
    supported_airport_codes,
)
from generator import (
    Scenario,
    ScenarioFlags,
    SimulatedTimeout,
    generate_air_options,
    generate_hotel_options,
    seed_for,
)

DEPART = date(2026, 9, 15)
CHECK_IN = date(2026, 9, 15)
CHECK_OUT = date(2026, 9, 18)


@pytest.fixture
def globex() -> TravelPolicy:
    return TravelPolicy(
        tenant_id="globex",
        topic="air",
        version="2026.1",
        core=PolicyCore(
            hotel_nightly_cap=Money(amount=250, currency=Currency.USD),
            max_hotel_star_rating=4,
            cabin_rule=CabinRule(
                type=CabinRuleType.DURATION, cabin=CabinClass.BUSINESS, threshold_hours=8
            ),
        ),
    )


@pytest.fixture
def initech() -> TravelPolicy:
    return TravelPolicy(
        tenant_id="initech",
        topic="air",
        version="2026.1",
        core=PolicyCore(
            hotel_nightly_cap=Money(amount=150, currency=Currency.EUR),
            max_hotel_star_rating=3,
            cabin_rule=CabinRule(type=CabinRuleType.NEVER),
        ),
    )


def air(policy: TravelPolicy, currency=Currency.USD, **kwargs):
    return generate_air_options(
        tenant_id=policy.tenant_id,
        origin_query=kwargs.pop("origin", "Dublin"),
        destination_query=kwargs.pop("destination", "Atlanta"),
        depart_on=kwargs.pop("depart_on", DEPART),
        policy=policy,
        currency=currency,
        **kwargs,
    )


def hotels(policy: TravelPolicy, currency=Currency.USD, **kwargs):
    return generate_hotel_options(
        tenant_id=policy.tenant_id,
        destination_query=kwargs.pop("destination", "Dublin"),
        check_in=kwargs.pop("check_in", CHECK_IN),
        check_out=kwargs.pop("check_out", CHECK_OUT),
        policy=policy,
        currency=currency,
        **kwargs,
    )


class TestDeterminism:
    """FIXTURE mode must be byte-identical across calls — the whole eval gate
    rests on this."""

    def test_air_search_is_reproducible(self, globex):
        first, second = air(globex), air(globex)
        assert first.model_dump_json() == second.model_dump_json()

    def test_hotel_search_is_reproducible(self, globex):
        first, second = hotels(globex), hotels(globex)
        assert first.model_dump_json() == second.model_dump_json()

    def test_seed_is_process_independent(self):
        """blake2b, not `hash()` — the latter is salted per process, so results
        would differ between Lambda invocations."""
        parts = ["air", "globex", "DUB", "ATL"]
        assert seed_for(parts) == seed_for(parts)

    def test_different_query_gives_different_options(self, globex):
        dub_atl = air(globex)
        dub_ord = air(globex, destination="Chicago")
        assert dub_atl.options[0].option_id != dub_ord.options[0].option_id

    def test_tenant_is_part_of_the_seed(self, globex, initech):
        """Tenants see different-looking inventory, so the isolation demo is
        visibly distinct rather than two identical result sets."""
        assert air(globex).options[0].option_id != air(initech).options[0].option_id

    def test_live_mode_varies_with_time_bucket(self, globex):
        early = air(globex, mode=GenerationMode.LIVE, now=datetime(2026, 9, 1, 1, 0))
        later = air(globex, mode=GenerationMode.LIVE, now=datetime(2026, 9, 3, 13, 0))
        assert early.model_dump_json() != later.model_dump_json()

    def test_live_mode_stable_inside_a_bucket(self, globex):
        a = air(globex, mode=GenerationMode.LIVE, now=datetime(2026, 9, 1, 1, 0))
        b = air(globex, mode=GenerationMode.LIVE, now=datetime(2026, 9, 1, 2, 30))
        assert a.model_dump_json() == b.model_dump_json()


class TestPlausibility:
    def test_long_haul_duration_is_believable(self, globex):
        """DUB -> ATL is ~6300 km; anything near 45 minutes would discredit the
        whole sample."""
        for option in air(globex).options:
            assert 7 * 60 <= option.duration_minutes <= 13 * 60

    def test_short_haul_duration_is_believable(self, globex):
        for option in air(globex, origin="Dublin", destination="London").options:
            assert 45 <= option.duration_minutes <= 4 * 60

    def test_arrival_follows_departure(self, globex):
        for option in air(globex).options:
            assert option.arrive_at > option.depart_at

    def test_carriers_are_route_plausible(self, globex):
        """A hub carrier at either end, not an arbitrary airline."""
        codes = {o.carrier for o in air(globex).options}
        known = {
            "EI",
            "BA",
            "DL",
            "AA",
            "UA",
            "AF",
            "KL",
            "LH",
            "AC",
            "EK",
            "SQ",
            "AI",
            "LX",
            "IB",
            "AZ",
            "AY",
        }
        assert codes <= known

    def test_hotel_total_matches_nights(self, globex):
        for option in hotels(globex).options:
            expected = option.nightly_rate.amount * 3  # 15th -> 18th
            assert abs(option.total.amount - expected) < 1


class TestPolicyAnnotation:
    """The backend annotates; the agent passes the verdict through."""

    def test_tenant_contrast_on_business_class(self, globex, initech):
        g = air(globex, cabin_filter=CabinClass.BUSINESS)
        i = air(initech, cabin_filter=CabinClass.BUSINESS, currency=Currency.EUR)
        # DUB->ATL exceeds 8h, so Globex permits business and Initech never does.
        assert all(o.policy_status is PolicyStatus.IN_POLICY for o in g.options)
        assert all(o.policy_status is PolicyStatus.OUT_OF_POLICY for o in i.options)

    def test_out_of_policy_carries_a_reason(self, initech):
        for option in air(initech, cabin_filter=CabinClass.BUSINESS, currency=Currency.EUR).options:
            assert option.policy_note

    def test_hotel_cap_annotation(self, initech):
        """Initech's EUR 150 cap rules out most inventory; those that fail say why."""
        result = hotels(initech, currency=Currency.EUR)
        for option in result.options:
            if option.nightly_rate.amount > 150:
                assert option.policy_status is PolicyStatus.OUT_OF_POLICY
                assert option.policy_note

    def test_summary_counts_are_computed_not_inferred(self, globex):
        result = hotels(globex)
        counted = sum(1 for o in result.options if o.policy_status is PolicyStatus.IN_POLICY)
        assert result.summary.in_policy_options == counted
        assert result.summary.total_options == len(result.options)

    def test_summary_exposes_the_cap_for_narration(self, globex):
        assert hotels(globex).summary.policy_cap == globex.core.hotel_nightly_cap

    def test_currency_follows_the_tenant(self, initech):
        for option in hotels(initech, currency=Currency.EUR).options:
            assert option.nightly_rate.currency is Currency.EUR


class TestFilters:
    """Filters ride parameters — they never become separate tools."""

    def test_gym_filter_is_honest(self, globex):
        result = hotels(globex, filters=HotelFilters(gym=True))
        assert result.options  # fixture data should not filter to empty
        assert all("gym" in o.amenities for o in result.options)

    def test_chain_filter(self, globex):
        result = hotels(globex, filters=HotelFilters(chain="Hilton"))
        assert all("hilton" in o.chain.lower() for o in result.options)

    def test_star_filter(self, globex):
        result = hotels(globex, filters=HotelFilters(max_star_rating=3))
        assert all(o.star_rating <= 3 for o in result.options)

    def test_preferred_chain_is_flagged_not_filtered(self, globex):
        result = hotels(globex, preferred_chains=["Marriott"])
        flagged = [o for o in result.options if o.is_preferred_chain]
        assert all(o.chain == "Marriott" for o in flagged)


class TestSorting:
    def test_price_sort(self, globex):
        prices = [o.price.amount for o in air(globex, sort=SortOrder.PRICE).options]
        assert prices == sorted(prices)

    def test_duration_sort(self, globex):
        mins = [o.duration_minutes for o in air(globex, sort=SortOrder.DURATION).options]
        assert mins == sorted(mins)


class TestScenarios:
    """Non-deterministic conditions, fired deterministically (eval suite G)."""

    def test_price_drift_raises_fares(self, globex):
        base = air(globex).options[0].price.amount
        drifted = air(globex, flags=ScenarioFlags.of(Scenario.PRICE_DRIFT)).options[0].price.amount
        assert drifted > base

    def test_no_availability_returns_empty_not_invented(self, globex):
        result = air(globex, flags=ScenarioFlags.of(Scenario.NO_AVAILABILITY))
        assert result.options == []
        assert result.summary.total_options == 0
        # Places still resolve — an empty result is not a failed lookup.
        assert result.resolved_origin == "DUB"

    def test_timeout_raises_for_the_retry_path(self, globex):
        with pytest.raises(SimulatedTimeout):
            air(globex, flags=ScenarioFlags.of(Scenario.TIMEOUT))

    def test_hotel_scenarios_apply_too(self, globex):
        assert hotels(globex, flags=ScenarioFlags.of(Scenario.NO_AVAILABILITY)).options == []
        with pytest.raises(SimulatedTimeout):
            hotels(globex, flags=ScenarioFlags.of(Scenario.TIMEOUT))


class TestPlaceResolution:
    def test_city_name(self):
        assert resolve_airport("Dublin").code == "DUB"

    def test_iata_code_passes_through(self):
        """The model may supply a code from prior knowledge; accept it."""
        assert resolve_airport("DUB").code == "DUB"

    def test_case_insensitive(self):
        assert resolve_airport("dublin").code == "DUB"

    def test_airport_name(self):
        assert resolve_airport("London Heathrow").code == "LHR"

    def test_multi_airport_city_picks_primary(self):
        """ "London" means Heathrow — file order encodes that."""
        assert resolve_airport("London").code == "LHR"

    def test_same_name_in_two_countries_asks_rather_than_picking(self):
        """Manchester, England and Manchester, New Hampshire are both real.

        **The distinction this draws is between two airports and two cities.** "London" is one city
        with two airports and the primary is a safe default — nobody asking for London is unsure of
        the country. "Manchester" is two different places, and a silent choice is wrong roughly half
        the time in a way that succeeds all the way through booking before anyone notices.
        """
        with pytest.raises(AmbiguousPlaceError) as caught:
            resolve_airport("Manchester")
        labels = [c["label"] for c in caught.value.candidates]
        assert any("England" in label for label in labels)
        assert any("New Hampshire" in label for label in labels)

    def test_a_code_is_never_ambiguous(self):
        """`MAN` and `MHT` each name exactly one airport, so neither may raise."""
        assert resolve_airport("MAN").code == "MAN"
        assert resolve_airport("MHT").code == "MHT"

    def test_every_candidate_actually_resolves(self):
        """A question offering an option the system cannot then serve is worse than no question."""
        for candidates in _ambiguous_places().values():
            for candidate in candidates:
                assert resolve_airport(candidate["resolves_to"]).code == candidate["resolves_to"]

    def test_unknown_place_refuses_with_suggestions(self):
        """Refusal beats invention: no coordinates means no plausible duration."""
        with pytest.raises(UnknownPlaceError) as exc:
            resolve_airport("Atlantis")
        assert exc.value.suggestions

    def test_supported_list_is_advertised(self):
        codes = supported_airport_codes()
        assert "DUB" in codes and "LOS" in codes
        assert len(codes) >= 40
