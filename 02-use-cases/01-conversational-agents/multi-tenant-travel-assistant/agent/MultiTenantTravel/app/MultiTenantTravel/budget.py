"""A circuit breaker for one conversation's spend.

**Not the same thing as the eval gate, and the distinction is the whole design.** The gate in
`evaluation/gate.yaml` judges a *commit* on aggregate quality and cost, offline, before it ships.
This judges a single *trajectory*, at runtime, while a traveller waits. A gate breach means "do
not merge"; a budget breach means "stop spending this traveller's money and get a human".

So the caps here sit deliberately **above** the gate's thresholds. The gate wants p95 spend under
`$0.60` and p95 steps under 10; if a cap fired at those values it would fire on turns the gate
considers healthy, and a circuit breaker that trips in normal operation gets raised until it is
meaningless. A measured warm turn on this deployment costs about `$0.0086` over 2 steps, so the
defaults below are roughly a hundred times a typical turn — they exist to catch a loop, not to
enforce efficiency.

**Both caps, not one.** Spend is the
honest unit and steps are the one a person perceives as "it's stuck", and they fail differently: a
reflection loop burns steps with small token counts, while one enormous context burns dollars in a
single step. Either alone leaves a real runaway uncaught.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

log = logging.getLogger(__name__)

# ~100x a measured typical turn, and above every gate threshold, so this only ever fires on a
# genuine runaway. Overridable because the right number depends on a tenant's tolerance, not on
# anything this code can know.
DEFAULT_MAX_USD = 1.00
DEFAULT_MAX_STEPS = 15

BUDGET_PARAM = "/multi-tenant-travel/budget/trajectory"
BUDGET_VAR = "TRAVEL_BUDGET_JSON"

_cached: Budget | None = None


@dataclass(frozen=True)
class Budget:
    max_usd: float = DEFAULT_MAX_USD
    max_steps: int = DEFAULT_MAX_STEPS

    def breach(self, *, steps: int, usd: float | None) -> str | None:
        """The reason this trajectory must stop, or `None` to carry on.

        Returns prose rather than a boolean because the string reaches a human agent as the
        escalation reason, and "the assistant stopped" without a number is not something a travel
        desk can act on.

        **An unpriced trajectory does not disable the spend cap silently.** `usd` is `None` when
        the model has no rate card, and treating that as "under budget" would remove the money
        guard on exactly the deployment whose spend nobody is tracking. The step cap still applies
        and the gap is logged, so the failure is visible rather than convenient.
        """
        if steps >= self.max_steps:
            return f"step budget reached: {steps} steps, limit {self.max_steps}"
        if usd is None:
            log.warning(
                "trajectory is unpriced, so the $%.2f spend cap cannot be enforced on it — the "
                "%d-step cap is still in force. Publish rates to restore the spend guard.",
                self.max_usd,
                self.max_steps,
            )
            return None
        if usd >= self.max_usd:
            return f"spend budget reached: ${usd:.4f}, limit ${self.max_usd:.2f}"
        return None


def _parse(raw: str, source: str) -> Budget | None:
    try:
        published = json.loads(raw)
        return Budget(
            max_usd=float(published.get("max_usd", DEFAULT_MAX_USD)),
            max_steps=int(published.get("max_steps", DEFAULT_MAX_STEPS)),
        )
    except Exception as error:  # noqa: BLE001 - a bad override must be loud, not silent
        log.warning(
            "budget at %s is unusable (%s) — falling back to $%.2f / %d steps, so any limit "
            "published there is NOT in force",
            source,
            type(error).__name__,
            DEFAULT_MAX_USD,
            DEFAULT_MAX_STEPS,
        )
        return None


def budget() -> Budget:
    """The caps in force, from SSM if published, else the defaults above.

    Cached per container for the same reason the model id and rates are: it changes on the order
    of months, and this is consulted after every model step.
    """
    global _cached
    if _cached is not None:
        return _cached

    raw = os.environ.get(BUDGET_VAR)
    source = BUDGET_VAR
    if not raw:
        try:
            import boto3

            ssm = boto3.client("ssm")
            raw = ssm.get_parameter(Name=BUDGET_PARAM)["Parameter"]["Value"]
            source = BUDGET_PARAM
        except Exception as error:  # noqa: BLE001 - see below: absent is fine, denied is not
            # **An absent parameter is normal; being unable to *read* one is not, and conflating them
            # hid a defect for the life of this file.**
            #
            # The runtime's role was granted SSM only under `/multi-tenant-travel/guardrails/*` and
            # `/model/*` — never `/budget/*`. So every attempt to read a published budget failed with
            # `AccessDenied`, this `except` swallowed it as "not published", and the defaults applied.
            # The documented override mechanism could not work, and nothing anywhere said so. It was
            # found by trying to lower the cap to prove the break-out fires and watching the cap not
            # change.
            #
            # Distinguished by name rather than by exception class so this module keeps needing no
            # botocore import at module scope.
            denied = "AccessDenied" in str(error)
            if denied:
                log.error(
                    "cannot read the budget at %s (%s) — any limit published there is NOT in force, "
                    "and the defaults of $%.2f / %d steps apply. Grant ssm:GetParameter on that "
                    "prefix; see policies/budget-iam.json",
                    BUDGET_PARAM,
                    type(error).__name__,
                    DEFAULT_MAX_USD,
                    DEFAULT_MAX_STEPS,
                )
            raw = None

    _cached = (_parse(raw, source) if raw else None) or Budget()
    return _cached


def reason_for_handoff(breach: str, *, steps: int, usd: float | None, tools: list[str]) -> str:
    """The escalation reason a human agent reads first.

    **Assembled from the ledger's own facts rather than asked of the model.** The model is the
    thing that just misbehaved, so asking it to summarise why would be asking the unreliable
    narrator for the incident report. What was tried, how many steps, and what it cost are all
    recorded, so they are stated.
    """
    spend = "unpriced" if usd is None else f"${usd:.4f}"
    tried = ", ".join(dict.fromkeys(tools)) or "no tools"
    return (
        f"The assistant stopped itself before finishing: {breach}. "
        f"It ran {steps} step(s) costing {spend} and used: {tried}. "
        "The traveller has not been helped yet and needs a person to pick this up."
    )
