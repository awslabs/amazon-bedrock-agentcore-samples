"""Deterministic seeding.

The whole generator hangs off one idea: **the same query must produce the same
options.** That is what makes exact-match eval assertions and cost baselines
mean anything — if search results drifted per call, no assertion could hold and
every CPRT comparison would be noise.

`FIXTURE` mode seeds on the query alone. `LIVE` mode folds in a coarse time
bucket, so a demo shows plausible drift between sessions while remaining stable
within one.

Determinism here is a property of the test environment, not a claim about
reality: real fare search *is* non-stationary. Suite G tests that
non-stationarity deliberately via the scenario flags in `scenarios.py`.
"""

import hashlib
from datetime import date, datetime
from random import Random

from app.models import GenerationMode

# How long a LIVE seed stays stable. Long enough that a demo conversation sees
# consistent prices; short enough that returning tomorrow looks like a new day.
LIVE_BUCKET_HOURS = 6


def seed_for(
    parts: list[str],
    mode: GenerationMode = GenerationMode.FIXTURE,
    now: datetime | None = None,
) -> int:
    """Stable integer seed from query components.

    Uses blake2b rather than `hash()`, which is salted per process and would make
    results differ between Lambda invocations.
    """
    material = "|".join(parts)

    if mode is GenerationMode.LIVE:
        clock = now or datetime.now()
        # Day-aligned buckets. Dividing the raw epoch instead would put the
        # boundary at an arbitrary wall-clock time (02:00 for a 6h window), so a
        # single demo could straddle two buckets and appear non-deterministic.
        bucket = f"{clock.date().isoformat()}#{clock.hour // LIVE_BUCKET_HOURS}"
        material = f"{material}|bucket={bucket}"

    digest = hashlib.blake2b(material.encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big")


def rng_for(
    parts: list[str],
    mode: GenerationMode = GenerationMode.FIXTURE,
    now: datetime | None = None,
) -> Random:
    """A `Random` instance dedicated to one query — never the global one."""
    return Random(seed_for(parts, mode, now))


def air_query_parts(tenant_id: str, origin: str, destination: str, depart_on: date) -> list[str]:
    """Seed inputs for an air search.

    Tenant is included so the two seed tenants see different-looking inventory —
    otherwise Globex and Initech would return identical options and the
    isolation demo would be less convincing.
    """
    return ["air", tenant_id, origin, destination, depart_on.isoformat()]


def hotel_query_parts(tenant_id: str, city: str, check_in: date, check_out: date) -> list[str]:
    return ["hotel", tenant_id, city.lower(), check_in.isoformat(), check_out.isoformat()]


def option_id(parts: list[str], index: int) -> str:
    """Opaque, reproducible option id.

    Encodes the seed material so the backend can re-derive the very same option
    later (to re-price a held offer) without having stored it. Clients receive
    only this id — never a price, which would be forgeable.
    """
    digest = hashlib.blake2b("|".join(parts).encode(), digest_size=5).hexdigest()
    return f"opt_{digest}_{index}"
