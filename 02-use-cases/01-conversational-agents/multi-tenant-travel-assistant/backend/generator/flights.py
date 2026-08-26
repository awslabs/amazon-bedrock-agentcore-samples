"""Deterministic flight option generation.

Options are computed per request and never stored. Durations come from real
great-circle distance between the two airports, which is why the airport fixture
carries coordinates: a Dublin -> Atlanta option must look like eight hours, not
forty-five minutes.

The backend also annotates each option with the tenant's policy verdict, the way
a real online booking tool does. The agent layer passes that verdict through; it
never recomputes it.
"""

from datetime import date, datetime, time, timedelta

from app.models import (
    AirSearchResponse,
    CabinClass,
    Currency,
    FlightOption,
    GenerationMode,
    Money,
    PolicyStatus,
    SearchSummary,
    SortOrder,
    TravelPolicy,
)
from app.reference import carriers, resolve_airport

from .scenarios import PRICE_DRIFT_FACTOR, Scenario, ScenarioFlags, SimulatedTimeout
from .seeding import air_query_parts, option_id, rng_for

OPTIONS_PER_SEARCH = 5

# Cruise speed and a fixed allowance for taxi, climb and descent. Crude, but it
# turns distance into a believable schedule.
CRUISE_KMH = 840.0
GROUND_ALLOWANCE_MINUTES = 40

# Fare shape: a base, a per-km component, and a spread so the five options
# differ. Business is a multiple of the economy fare, as in real fare ladders.
BASE_FARE = 90.0
FARE_PER_KM = 0.055
FARE_SPREAD = 0.35
BUSINESS_MULTIPLIER = 3.4
PREMIUM_ECONOMY_MULTIPLIER = 1.6

# Long-haul threshold used for cabin availability and connection likelihood.
LONG_HAUL_KM = 4000


def _carriers_for(origin: str, destination: str, long_haul: bool) -> list[dict]:
    """Carriers plausible for this route.

    Prefers airlines that actually hub at either end, so Dublin -> Atlanta offers
    Aer Lingus and Delta rather than an arbitrary pick. Falls back to any
    long-haul carrier when no hub matches.
    """
    hubbed = [c for c in carriers() if origin in c["hubs"] or destination in c["hubs"]]
    if long_haul:
        hubbed = [c for c in hubbed if c["long_haul"]]
    if hubbed:
        return hubbed
    return [c for c in carriers() if c["long_haul"]] if long_haul else list(carriers())


def _cabin_ladder(long_haul: bool) -> list[CabinClass]:
    """Cabins actually sold on this kind of route."""
    if long_haul:
        return [CabinClass.ECONOMY, CabinClass.PREMIUM_ECONOMY, CabinClass.BUSINESS]
    return [CabinClass.ECONOMY, CabinClass.BUSINESS]


def _fare(distance_km: float, cabin: CabinClass, jitter: float) -> float:
    economy = (BASE_FARE + distance_km * FARE_PER_KM) * (1 + jitter)
    match cabin:
        case CabinClass.BUSINESS:
            return economy * BUSINESS_MULTIPLIER
        case CabinClass.PREMIUM_ECONOMY:
            return economy * PREMIUM_ECONOMY_MULTIPLIER
        case _:
            return economy


def generate_air_options(
    tenant_id: str,
    origin_query: str,
    destination_query: str,
    depart_on: date,
    policy: TravelPolicy,
    currency: Currency,
    cabin_filter: CabinClass | None = None,
    sort: SortOrder = SortOrder.PRICE,
    mode: GenerationMode = GenerationMode.FIXTURE,
    flags: ScenarioFlags | None = None,
    now: datetime | None = None,
    prior_international_trips: int | None = None,
) -> AirSearchResponse:
    """Generate policy-annotated flight options for one query.

    Raises `UnknownPlaceError` (from `resolve_airport`) for unsupported places —
    the caller turns that into an honest not-found with suggestions.
    """
    flags = flags or ScenarioFlags.none()

    if Scenario.TIMEOUT in flags:
        raise SimulatedTimeout("upstream fare search did not respond")

    origin = resolve_airport(origin_query)
    destination = resolve_airport(destination_query)

    parts = air_query_parts(tenant_id, origin.code, destination.code, depart_on)
    rng = rng_for(parts, mode, now)

    if Scenario.NO_AVAILABILITY in flags:
        return AirSearchResponse(
            options=[],
            summary=SearchSummary(total_options=0, in_policy_options=0),
            resolved_origin=origin.code,
            resolved_destination=destination.code,
        )

    distance_km = origin.distance_km(destination)
    long_haul = distance_km >= LONG_HAUL_KM
    base_minutes = int(distance_km / CRUISE_KMH * 60) + GROUND_ALLOWANCE_MINUTES
    is_international = origin.country != destination.country

    route_carriers = _carriers_for(origin.code, destination.code, long_haul)
    cabins = _cabin_ladder(long_haul)

    options: list[FlightOption] = []
    for index in range(OPTIONS_PER_SEARCH):
        carrier = route_carriers[rng.randrange(len(route_carriers))]
        cabin = cabin_filter or cabins[rng.randrange(len(cabins))]

        # Connections add time; long-haul is likelier to route via a hub.
        stops = 1 if (long_haul and rng.random() < 0.4) else 0
        duration = base_minutes + (rng.randrange(60, 150) if stops else rng.randrange(-10, 20))

        depart_at = datetime.combine(
            depart_on,
            time(hour=rng.randrange(6, 21), minute=rng.choice([0, 15, 30, 45])),
        )
        arrive_at = depart_at + timedelta(minutes=duration)

        fare = _fare(distance_km, cabin, rng.uniform(-FARE_SPREAD, FARE_SPREAD))
        if Scenario.PRICE_DRIFT in flags:
            fare *= PRICE_DRIFT_FACTOR

        flight_hours = duration / 60
        status = policy.air_status(cabin, flight_hours, prior_international_trips)
        note = None
        if status is PolicyStatus.OUT_OF_POLICY:
            permitted = policy.core.cabin_rule.permitted_cabin(
                flight_hours, prior_international_trips
            )
            note = f"{cabin.value} exceeds policy; {permitted.value} permitted on this route"

        options.append(
            FlightOption(
                option_id=option_id(parts, index),
                carrier=carrier["code"],
                carrier_name=carrier["name"],
                flight_number=f"{carrier['code']}{rng.randrange(100, 999)}",
                depart_airport=origin.code,
                depart_at=depart_at,
                arrive_airport=destination.code,
                arrive_at=arrive_at,
                duration_minutes=duration,
                stops=stops,
                cabin=cabin,
                price=Money(amount=round(fare, 2), currency=currency),
                refundable=rng.random() < 0.3,
                is_international=is_international,
                policy_status=status,
                policy_note=note,
            )
        )

    options = _sorted(options, sort)
    return AirSearchResponse(
        options=options,
        summary=_summarize(options, policy, currency),
        resolved_origin=origin.code,
        resolved_destination=destination.code,
    )


def _sorted(options: list[FlightOption], sort: SortOrder) -> list[FlightOption]:
    match sort:
        case SortOrder.DURATION:
            return sorted(options, key=lambda o: o.duration_minutes)
        case SortOrder.DEPARTURE:
            return sorted(options, key=lambda o: o.depart_at)
        case _:
            return sorted(options, key=lambda o: o.price.amount)


def _summarize(
    options: list[FlightOption], policy: TravelPolicy, currency: Currency
) -> SearchSummary:
    """Aggregates the model must not compute itself.

    A count belongs to the whole result set rather than to any single option, so
    it is calculated here and handed over as a fact.
    """
    in_policy = [o for o in options if o.policy_status is PolicyStatus.IN_POLICY]
    return SearchSummary(
        total_options=len(options),
        in_policy_options=len(in_policy),
        cheapest_in_policy=min((o.price for o in in_policy), key=lambda m: m.amount, default=None),
        policy_cap=None,  # air policy is expressed as a cabin rule, not a cap
    )
