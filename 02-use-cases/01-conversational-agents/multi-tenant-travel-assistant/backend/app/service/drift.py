"""Applying simulated conditions to stored records.

The generators already honour scenarios for things they *invent* — a fare that rises, availability
that vanishes, an upstream that stalls. This is the other half: conditions that act on data the
repository already holds, which is where the interesting agent failures live.

**Why the policy cap is the one worth simulating.** Everything else in suite G tests whether the
agent reports a failure honestly. A policy that changes mid-session tests something harder: whether
the agent *re-reads* a fact it has already been told. An agent carrying "your cap is 250" in context
will happily answer a second question from it, with a rule quote that was accurate when it was
fetched and is now wrong. No error is raised, nothing times out, and the transcript looks clean —
which is exactly why the whole "deterministic facts come from a tool, every time" rule exists. This
makes that rule falsifiable.

Applied on read rather than by writing the tenant's record, so the drift is invisible to every other
session and needs no undo. Rewriting the stored policy would leave a lowered cap behind for whoever
opened the demo next, and the failure would look like a seeding bug.
"""

from __future__ import annotations

from decimal import Decimal

from generator.scenarios import POLICY_CAP_LOWERED_FACTOR, Scenario, ScenarioFlags

from ..models import TravelPolicy


def apply_to_policy(policy: TravelPolicy, flags: ScenarioFlags) -> TravelPolicy:
    """The policy as this session should see it.

    Returns the original object when no scenario touches it, so the ordinary path allocates nothing
    and cannot be changed by accident.
    """
    if Scenario.POLICY_CAP_LOWERED not in flags:
        return policy
    cap = policy.core.hotel_nightly_cap
    if cap is None:
        return policy

    # `model_copy(deep=True)` rather than mutating: the repository may hand back a cached instance,
    # and quietly editing it would leak this session's scenario into the next request served by the
    # same process.
    drifted = policy.model_copy(deep=True)
    lowered = (cap.amount * Decimal(str(POLICY_CAP_LOWERED_FACTOR))).quantize(Decimal("0.01"))
    drifted.core.hotel_nightly_cap = cap.model_copy(update={"amount": lowered})
    return drifted
