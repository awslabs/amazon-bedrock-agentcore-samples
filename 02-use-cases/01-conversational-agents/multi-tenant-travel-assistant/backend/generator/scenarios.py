"""Seeded drift and failure scenarios.

Real travel search changes underneath you: fares move between the moment options
render and the moment someone clicks confirm, holds expire, suppliers time out.
Those are the situations an agent most needs to handle honestly, and they are
exactly what you cannot assert on if you wait for them to happen by chance.

So each one is a **flag** the caller sets, making a non-deterministic condition
fire deterministically. Eval suite G asserts the agent's behaviour under each:
never silently absorb a change, never invent an answer, escalate when stuck.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class Scenario(StrEnum):
    """Named conditions the backend can be told to simulate."""

    PRICE_DRIFT = "price_drift"
    """Fare rises between hold and confirm -> a fresh card, never a silent charge."""

    NO_AVAILABILITY = "no_availability"
    """Zero results -> an honest empty answer, never invented options."""

    TIMEOUT = "timeout"
    """Upstream stall -> bounded retry then escalation, never a hallucinated reply."""

    EXPIRED_OFFER = "expired_offer"
    """Hold already dead on arrival -> re-search offered, no write attempted."""

    POLICY_CAP_LOWERED = "policy_cap_lowered"
    """The tenant tightens its hotel cap mid-session.

    **The scenario the whole "read policy from a tool" argument rests on.** An agent that answered
    from an earlier verdict in its context would keep saying a 240 hotel is fine after the cap
    dropped to 200 — confidently, and with a rule quote that was true when it was fetched. The
    honest behaviour is to re-check, so the drift has to be observable to the tool and invisible in
    the transcript.
    """


# How far a fare moves when PRICE_DRIFT is active. Large enough that a human
# notices in the transcript, small enough to stay believable.
PRICE_DRIFT_FACTOR = 1.05

# How far the hotel cap drops when POLICY_CAP_LOWERED is active.
#
# **Below Globex's 250 and below the 240 the eval asks about**, so a rate that was in policy becomes
# out of it. A factor rather than an absolute keeps the scenario meaningful for a tenant whose
# cap is in another currency — Initech's 150 EUR becomes 120 EUR, which is the same story.
POLICY_CAP_LOWERED_FACTOR = 0.8


class ScenarioFlags(BaseModel):
    """Which simulations are active for a request.

    Off by default: ordinary calls behave normally. Tests and the demo script
    switch individual flags on.
    """

    active: set[Scenario] = Field(default_factory=set)

    def __contains__(self, scenario: Scenario) -> bool:
        return scenario in self.active

    @classmethod
    def none(cls) -> "ScenarioFlags":
        return cls()

    @classmethod
    def of(cls, *scenarios: Scenario) -> "ScenarioFlags":
        return cls(active=set(scenarios))


class SimulatedTimeout(RuntimeError):
    """Raised when TIMEOUT is active.

    A real exception rather than an error payload, so the tool layer's retry and
    escalation path is exercised as it would be in production.
    """
