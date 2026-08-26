"""Search orchestration.

Sits between the router and the generator so the router stays HTTP-only. Its job
is assembling the inputs a search needs — the tenant's policy, its currency, the
traveller's preferred chains, their travel history for count-based rules — and
handing them to the generator.

This is where the "sequences live in code, not in the model" rule shows up
concretely: three reads and a generation step become one call.
"""

from datetime import date

from generator import generate_air_options, generate_hotel_options
from generator.scenarios import ScenarioFlags

from ..eligibility import count_international_trips
from ..models import (
    AirSearchRequest,
    AirSearchResponse,
    GenerationMode,
    HotelSearchRequest,
    HotelSearchResponse,
    TenantConfig,
    TravelPolicy,
)
from ..models.policy import CabinRuleType, PolicyCore
from ..repository import Repository


class MissingOriginError(LookupError):
    """No origin was given and the traveller has no home airport on file.

    Distinct from a validation error because the caller did nothing wrong: the tool is *expected* to
    omit the origin. This says "the profile could not supply one either", which is a question to ask
    the traveller, not a malformed request.
    """


def resolve_origin(
    repo: Repository, tenant_id: str, traveler_id: str | None, origin: str | None
) -> str:
    """The origin to search from: what was asked for, else the traveller's home airport.

    **Shared with the booking path, and it has to be.** Options are found again by regenerating them
    from their search parameters — generation is deterministic, so nothing needs storing. That only
    holds if every path resolves the query *identically*. When search resolved an absent origin to
    ORD and the hold left it empty, regeneration seeded on a different origin, produced different
    option ids, and reported "that option is no longer available" for an option the traveller was
    looking at a second earlier. A 404 that says "search again" for something that cannot be found
    again is the worst version of this bug, and it appeared the moment origin became optional.
    """
    if origin and origin.strip():
        return origin.strip()
    if traveler_id:
        traveler = repo.traveler(tenant_id, traveler_id)
        if traveler and traveler.preferences.home_airport:
            return traveler.preferences.home_airport
    # Asks for the one fact that is missing rather than guessing a hub. A wrong origin produces a
    # plausible itinerary from the wrong city, which is worse than a question.
    raise MissingOriginError()


def _policy_or_empty(repo: Repository, tenant_id: str, topic: str) -> TravelPolicy:
    """A tenant with no policy on file is treated as fully restricted.

    An absent policy must never read as "no restrictions" — that is the most
    dangerous possible default, so the fallback is an empty `PolicyCore` whose
    cabin rule denies upgrades.
    """
    policy = repo.policy(tenant_id, topic)
    if policy is not None:
        return policy
    return TravelPolicy(tenant_id=tenant_id, topic=topic, version="none", core=PolicyCore())


def _prior_international_trips(
    repo: Repository,
    tenant_id: str,
    traveler_id: str | None,
    policy: TravelPolicy,
    as_of: date,
) -> int | None:
    """Travel history, but only when the policy actually needs it.

    Skipping the read for duration-based rules keeps the common path to a single
    lookup. `None` means "not applicable", which `permitted_cabin` treats as
    not-yet-entitled rather than entitled.
    """
    if policy.core.cabin_rule.type is not CabinRuleType.TRIP_COUNT or not traveler_id:
        return None
    trips = repo.trips(tenant_id, traveler_id)
    return count_international_trips(trips, policy.core.cabin_rule, as_of)


def search_air(
    repo: Repository,
    tenant_id: str,
    config: TenantConfig,
    request: AirSearchRequest,
    mode: GenerationMode,
    traveler_id: str | None = None,
    flags: ScenarioFlags | None = None,
) -> AirSearchResponse:
    policy = _policy_or_empty(repo, tenant_id, "air")
    prior_trips = _prior_international_trips(
        repo, tenant_id, traveler_id, policy, request.depart_on
    )

    # **An absent origin is the traveller's home airport, not an error.** Nobody says "a flight
    # from Chicago to London" when Chicago is where they always leave from, so the tool sends no
    # origin and documents that this means "read it from the profile" — the same way
    # `search_hotels` below reads preferred chains rather than making the model carry them.
    # Resolved through the shared helper because the booking path must resolve it the same way.
    origin_query = resolve_origin(repo, tenant_id, traveler_id, request.origin)

    return generate_air_options(
        tenant_id=tenant_id,
        origin_query=origin_query,
        destination_query=request.destination,
        depart_on=request.depart_on,
        policy=policy,
        currency=config.currency,
        cabin_filter=request.cabin,
        sort=request.sort,
        mode=mode,
        prior_international_trips=prior_trips,
        flags=flags,
    )


def search_hotels(
    repo: Repository,
    tenant_id: str,
    config: TenantConfig,
    request: HotelSearchRequest,
    mode: GenerationMode,
    traveler_id: str | None = None,
    flags: ScenarioFlags | None = None,
) -> HotelSearchResponse:
    policy = _policy_or_empty(repo, tenant_id, "hotel")

    # Preferred chains come from the profile so "show me my preferred hotels"
    # needs no extra round trip from the caller.
    preferred: list[str] = []
    if traveler_id:
        traveler = repo.traveler(tenant_id, traveler_id)
        if traveler:
            preferred = traveler.preferences.preferred_hotel_chains

    return generate_hotel_options(
        tenant_id=tenant_id,
        destination_query=request.destination,
        check_in=request.check_in,
        check_out=request.check_out,
        policy=policy,
        currency=config.currency,
        filters=request.filters,
        preferred_chains=preferred,
        sort=request.sort,
        mode=mode,
        flags=flags,
    )
