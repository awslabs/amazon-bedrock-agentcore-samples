"""Deterministic option generation for the mock TMC.

Search results are computed per request, never stored. The same query always
returns the same options in `FIXTURE` mode, which is what lets the eval suite
make exact-match assertions and lets cost baselines be compared across commits.

Non-determinism that matters — fares moving, holds expiring, suppliers timing
out — is exposed as explicit `Scenario` flags so those conditions can be tested
deliberately instead of waited for.
"""

from .flights import generate_air_options
from .hotels import generate_hotel_options
from .scenarios import PRICE_DRIFT_FACTOR, Scenario, ScenarioFlags, SimulatedTimeout
from .seeding import air_query_parts, hotel_query_parts, option_id, rng_for, seed_for

__all__ = [
    "PRICE_DRIFT_FACTOR",
    "Scenario",
    "ScenarioFlags",
    "SimulatedTimeout",
    "air_query_parts",
    "generate_air_options",
    "generate_hotel_options",
    "hotel_query_parts",
    "option_id",
    "rng_for",
    "seed_for",
]
