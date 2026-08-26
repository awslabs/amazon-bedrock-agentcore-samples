"""Deterministic hotel option generation.

Same contract as flights: seeded, reproducible, policy-annotated by the backend.

Filters (breakfast, gym, workspace, chain, star rating) ride *parameters* — they
never become separate tools. That is the "one tool per intent" rule made
concrete: "show me hotels with a gym" is `search_hotels` with a filter, not
`search_hotels_with_gym`.
"""

from datetime import date, datetime

from app.models import (
    Currency,
    GenerationMode,
    HotelFilters,
    HotelOption,
    HotelSearchResponse,
    Money,
    PolicyStatus,
    SearchSummary,
    SortOrder,
    TravelPolicy,
)
from app.reference import hotel_chains, resolve_airport

from .scenarios import PRICE_DRIFT_FACTOR, Scenario, ScenarioFlags, SimulatedTimeout
from .seeding import hotel_query_parts, option_id, rng_for

OPTIONS_PER_SEARCH = 6

# Amenities a corporate traveller actually filters on. Closed list: an unknown
# amenity is never invented, it simply yields no match.
AMENITY_POOL = [
    "breakfast_included",
    "gym",
    "workspace",
    "high_speed_wifi",
    "business_centre",
    "parking",
    "ev_charging",
    "airport_shuttle",
]

# Street names are cosmetic, but an address must look like an address: the
# location tools geocode a *string*, and "12 King Street, Dublin" resolves far
# better than a property name alone.
STREET_NAMES = [
    "King Street",
    "Market Square",
    "Harbour Road",
    "Central Avenue",
    "Station Road",
    "Cathedral Lane",
    "Riverside Walk",
    "Park Place",
]


def generate_hotel_options(
    tenant_id: str,
    destination_query: str,
    check_in: date,
    check_out: date,
    policy: TravelPolicy,
    currency: Currency,
    filters: HotelFilters | None = None,
    preferred_chains: list[str] | None = None,
    sort: SortOrder = SortOrder.PRICE,
    mode: GenerationMode = GenerationMode.FIXTURE,
    flags: ScenarioFlags | None = None,
    now: datetime | None = None,
) -> HotelSearchResponse:
    """Generate policy-annotated hotel options for one query."""
    filters = filters or HotelFilters()
    flags = flags or ScenarioFlags.none()
    preferred = {c.lower() for c in (preferred_chains or [])}

    if Scenario.TIMEOUT in flags:
        raise SimulatedTimeout("upstream hotel availability did not respond")

    # Reuse airport resolution so "Dublin" and "DUB" both work, and so the
    # supported-place limit is identical across both search types.
    airport = resolve_airport(destination_query)
    city = airport.city

    nights = max((check_out - check_in).days, 1)
    parts = hotel_query_parts(tenant_id, city, check_in, check_out)
    rng = rng_for(parts, mode, now)

    if Scenario.NO_AVAILABILITY in flags:
        return HotelSearchResponse(
            options=[],
            summary=SearchSummary(total_options=0, in_policy_options=0),
            resolved_city=city,
        )

    chains = list(hotel_chains())
    options: list[HotelOption] = []

    for index in range(OPTIONS_PER_SEARCH):
        chain = chains[rng.randrange(len(chains))]
        brand = chain["brands"][rng.randrange(len(chain["brands"]))]

        star_low, star_high = chain["star_band"]
        stars = rng.randint(star_low, star_high)

        rate_low, rate_high = chain["rate_band"]
        nightly = rng.uniform(rate_low, rate_high)
        if Scenario.PRICE_DRIFT in flags:
            nightly *= PRICE_DRIFT_FACTOR

        # Higher-starred properties carry more amenities — keeps the data coherent
        # so a filter on "gym" doesn't return a 2-star budget property.
        amenity_count = min(len(AMENITY_POOL), 2 + stars)
        amenities = sorted(rng.sample(AMENITY_POOL, amenity_count))

        nightly_rate = Money(amount=round(nightly, 2), currency=currency)
        status = policy.hotel_status(nightly_rate, stars)
        note = None
        if status is PolicyStatus.OUT_OF_POLICY:
            cap = policy.core.hotel_nightly_cap
            if cap and nightly_rate.amount > cap.amount:
                note = f"above the {cap} nightly cap"
            else:
                note = f"{stars}-star exceeds the policy maximum"

        options.append(
            HotelOption(
                option_id=option_id(parts, index),
                property_code=f"h_{option_id(parts, index)[-6:]}",
                property_name=f"{brand} {city}",
                chain=chain["chain"],
                address=(
                    f"{rng.randrange(1, 200)} "
                    f"{STREET_NAMES[rng.randrange(len(STREET_NAMES))]}, {city}"
                ),
                city=city,
                star_rating=stars,
                nightly_rate=nightly_rate,
                total=Money(amount=round(nightly * nights, 2), currency=currency),
                amenities=amenities,
                is_preferred_chain=chain["chain"].lower() in preferred,
                policy_status=status,
                policy_note=note,
            )
        )

    options = _apply_filters(options, filters)
    options = _sorted(options, sort)
    return HotelSearchResponse(
        options=options,
        summary=_summarize(options, policy),
        resolved_city=city,
    )


def _apply_filters(options: list[HotelOption], filters: HotelFilters) -> list[HotelOption]:
    """Filtering happens after generation so the seed stays query-shaped.

    Generating then filtering keeps the same property set stable regardless of
    which filters were applied — asking for "hotels in Dublin" and "hotels in
    Dublin with a gym" returns a consistent view of the same inventory.
    """
    kept = options
    if filters.breakfast_included:
        kept = [o for o in kept if "breakfast_included" in o.amenities]
    if filters.gym:
        kept = [o for o in kept if "gym" in o.amenities]
    if filters.workspace:
        kept = [o for o in kept if "workspace" in o.amenities]
    if filters.chain:
        wanted = filters.chain.lower()
        kept = [o for o in kept if wanted in o.chain.lower()]
    if filters.max_star_rating is not None:
        kept = [o for o in kept if o.star_rating <= filters.max_star_rating]
    return kept


def _sorted(options: list[HotelOption], sort: SortOrder) -> list[HotelOption]:
    if sort is SortOrder.PRICE:
        return sorted(options, key=lambda o: o.nightly_rate.amount)
    return options


def _summarize(options: list[HotelOption], policy: TravelPolicy) -> SearchSummary:
    in_policy = [o for o in options if o.policy_status is PolicyStatus.IN_POLICY]
    return SearchSummary(
        total_options=len(options),
        in_policy_options=len(in_policy),
        cheapest_in_policy=min(
            (o.nightly_rate for o in in_policy), key=lambda m: m.amount, default=None
        ),
        policy_cap=policy.core.hotel_nightly_cap,
    )
