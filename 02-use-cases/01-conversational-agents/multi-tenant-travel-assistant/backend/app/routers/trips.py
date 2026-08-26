"""Trip endpoints.

Trips are the agent's context resolver: "which hotel am I at?", "chargers near my
hotel", and every eligibility question that depends on travel history all start
here. So the payload carries what downstream tools need — notably a full address
on each hotel segment, because the location tools geocode a *string* and an
address resolves far more reliably than a property name.
"""

from fastapi import APIRouter, HTTPException, Query, status

from ..dependencies import RepositoryDep, TenantIdDep
from ..models import Trip, TripStatus

router = APIRouter(prefix="/v1/trips", tags=["trips"])


@router.get("", response_model=list[Trip])
def list_trips(
    tenant_id: TenantIdDep,
    repo: RepositoryDep,
    traveler: str | None = Query(default=None, description="Filter to one traveler"),
    status_filter: TripStatus | None = Query(
        default=None, alias="status", description="past | upcoming | in_progress"
    ),
) -> list[Trip]:
    """Trips for the tenant, optionally narrowed to a traveler or status.

    Ordered by start date so "my next trip" and "my last trip" are both a simple
    read rather than something the caller has to sort.
    """
    trips = repo.trips(tenant_id, traveler)
    if status_filter is not None:
        trips = [trip for trip in trips if trip.status is status_filter]
    return trips


@router.get("/{trip_id}", response_model=Trip)
def get_trip(trip_id: str, tenant_id: TenantIdDep, repo: RepositoryDep) -> Trip:
    """One trip, scoped to the calling tenant."""
    trip = repo.trip(tenant_id, trip_id)
    if trip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="trip not found",
        )
    return trip
