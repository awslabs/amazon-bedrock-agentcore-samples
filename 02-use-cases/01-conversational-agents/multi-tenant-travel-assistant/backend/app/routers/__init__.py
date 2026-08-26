"""HTTP routers — one module per domain.

Routers do HTTP only: resolve dependencies, translate exceptions into status
codes, return models. Anything that reasons about travel lives in `app/service/`,
so the same logic is reachable from a test without a request.
"""

from . import (
    arrangers,
    booking,
    config,
    eligibility,
    entry,
    policy,
    profile,
    trips,
)

ALL_ROUTERS = [
    trips.router,
    profile.router,
    policy.router,
    eligibility.router,
    config.router,
    entry.router,
    booking.router,
    arrangers.router,
]

__all__ = [
    "ALL_ROUTERS",
    "arrangers",
    "booking",
    "config",
    "eligibility",
    "entry",
    "policy",
    "profile",
    "trips",
]
