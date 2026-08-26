"""Seed the mock TMC with its two tenants and three travelers.

`seed(repo)` is idempotent — writes overwrite by key, so re-running is safe.
Against the in-memory repository it powers every test and local run; against the
DynamoDB repository it's the post-deploy load step. Same data, same
function, either backend.
"""

from app.repository import InMemoryRepository

from .tenants import POLICIES, TENANTS
from .travelers import (
    ADAEZE_ID,
    MARCUS_ID,
    PRIYA_DALLAS_HOTEL_REF,
    PRIYA_ID,
    RESERVATIONS,
    SAM_ADEWALE_ID,
    SAM_OKONJO_ID,
    SAM_WHITFIELD_ID,
    TRAVELERS,
    TRIPS,
)


def seed(repo: InMemoryRepository) -> InMemoryRepository:
    """Populate a repository with the full fixture set. Returns it for chaining."""
    for tenant in TENANTS:
        repo.put_tenant_config(tenant)
    for policy in POLICIES:
        repo.put_policy(policy)
    for traveler in TRAVELERS:
        repo.put_traveler(traveler)
    for trip in TRIPS:
        repo.put_trip(trip)
    for reservation in RESERVATIONS:
        repo.put_reservation(reservation)
    return repo


def seeded_repository() -> InMemoryRepository:
    """A fresh, fully seeded in-memory repository — the standard test fixture."""
    return seed(InMemoryRepository())


__all__ = [
    "ADAEZE_ID",
    "MARCUS_ID",
    "PRIYA_DALLAS_HOTEL_REF",
    "PRIYA_ID",
    "SAM_ADEWALE_ID",
    "SAM_OKONJO_ID",
    "SAM_WHITFIELD_ID",
    "seed",
    "seeded_repository",
]
