"""Eligibility: the *verdict*, computed here rather than narrated by a model.

**Why this is a service function and not a tool.** The verdict logic already lives on the policy
model (`CabinRule.permitted_cabin`, `trips_until_entitled`, `TravelPolicy.hotel_status`) because
search annotates every option with it. Recomputing any of that in the tool layer would duplicate a
policy rule across a language boundary and a deploy boundary — two copies that drift, and the
drift shows up as search saying "in policy" while eligibility says "no". So the tool *asks*; this
answers.

**Why the answer is a decision and not the inputs.** Returning the cap, the threshold and the trip
history and letting the model compare them would usually work — and be confidently wrong at the
edges: an off-by-one on the entitlement window, a duration threshold applied to the wrong leg,
"greater than" read as "at least". Those failures survive a demo and surface in production. The
whole non-negotiable ("deterministic facts in code; language in the model") is either honoured here
or it is decorative.

So the response carries `eligible`, a `reason_code`, the `rule_quote` the model may read aloud, and
the **arithmetic shown** (`"13h 20m > 8h threshold"`) so a user can see *why* rather than being
asked to trust it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ..eligibility import count_international_trips, period_start
from ..models import CabinClass, Money, TravelPolicy
from ..models.policy import CabinRuleType
from ..repository import Repository

# Ordered best-to-worst, so "did we get at least what was asked for?" is an index comparison rather
# than a pile of conditionals. Economy is the floor every policy allows.
CABIN_ORDER: tuple[CabinClass, ...] = (
    CabinClass.ECONOMY,
    CabinClass.PREMIUM_ECONOMY,
    CabinClass.BUSINESS,
    CabinClass.FIRST,
)


@dataclass(frozen=True)
class Verdict:
    """A decided answer. `computation` is the arithmetic, for the user to see."""

    eligible: bool
    reason_code: str
    rule_quote: str
    request_label: str
    computation: str | None = None
    # Set when a benefit is coming but not yet earned, so the agent can say "two more
    # international trips" instead of a bare no. A refusal that explains itself is actionable.
    trips_until_entitled: int | None = None


def _rank(cabin: CabinClass) -> int:
    try:
        return CABIN_ORDER.index(cabin)
    except ValueError:
        return 0


def check_cabin(
    repo: Repository,
    tenant_id: str,
    traveler_id: str | None,
    policy: TravelPolicy,
    requested: CabinClass,
    flight_hours: float,
    as_of: date,
    exclude_trip_id: str | None = None,
) -> Verdict:
    """May this traveller fly `requested` on a flight of `flight_hours`?

    Delegates the decision to `CabinRule.permitted_cabin` — the same method search uses to annotate
    options — so the two can never disagree.
    """
    rule = policy.core.cabin_rule
    label = f"{requested.value.replace('_', ' ')} cabin on a {flight_hours:.1f}h flight"

    prior: int | None = None
    if rule.type is CabinRuleType.TRIP_COUNT and traveler_id:
        prior = count_international_trips(
            repo.trips(tenant_id, traveler_id), rule, as_of, exclude_trip_id
        )

    permitted = rule.permitted_cabin(flight_hours, prior)
    eligible = _rank(requested) <= _rank(permitted)

    # The arithmetic, phrased so a person can check it. This string is the difference between "the
    # system said no" and "the system said no *because*".
    computation: str | None = None
    remaining: int | None = None
    match rule.type:
        case CabinRuleType.DURATION:
            threshold = rule.threshold_hours or 0
            comparison = ">" if flight_hours > threshold else "≤"
            computation = f"{flight_hours:.1f}h {comparison} {threshold}h threshold"
        case CabinRuleType.TRIP_COUNT:
            nth = rule.every_nth_trip or 0
            if prior is not None and nth:
                this_trip = prior + 1
                window = period_start(rule.period, as_of)
                computation = (
                    f"this is international trip {this_trip} since {window.isoformat()}; "
                    f"the benefit applies to every {nth}th"
                )
                remaining = rule.trips_until_entitled(prior)
        case CabinRuleType.ALWAYS:
            computation = f"{rule.cabin.value.replace('_', ' ')} permitted regardless of duration"
        case CabinRuleType.NEVER:
            computation = "no cabin upgrade rule in this policy"

    if eligible:
        reason_code = "cabin_permitted"
    elif remaining:
        reason_code = "cabin_entitlement_not_yet_earned"
    else:
        reason_code = "cabin_above_policy"

    return Verdict(
        eligible=eligible,
        reason_code=reason_code,
        rule_quote=_cabin_rule_quote(policy),
        request_label=label,
        computation=computation,
        trips_until_entitled=remaining or None,
    )


def _cabin_rule_quote(policy: TravelPolicy) -> str:
    """The rule in words, for the model to read aloud rather than paraphrase.

    Quoting beats paraphrasing here: a paraphrase of a policy rule is a new policy statement, and
    the user may act on it.
    """
    rule = policy.core.cabin_rule
    cabin = rule.cabin.value.replace("_", " ")
    match rule.type:
        case CabinRuleType.ALWAYS:
            return f"{cabin} is permitted on any flight."
        case CabinRuleType.DURATION:
            return f"{cabin} is permitted on flights longer than {rule.threshold_hours} hours."
        case CabinRuleType.TRIP_COUNT:
            period = (
                "calendar year" if rule.period.value == "calendar_year" else "rolling 12 months"
            )
            return (
                f"{cabin} is permitted on every {rule.every_nth_trip}th international trip "
                f"within a {period}."
            )
        case _:
            return "Economy is the standard cabin; no upgrade rule applies."


def check_hotel(policy: TravelPolicy, nightly_rate: Money, star_rating: int | None) -> Verdict:
    """Is this nightly rate and star rating within policy?

    Delegates to `TravelPolicy.hotel_status`, which search already uses per option.
    """
    status = policy.hotel_status(nightly_rate, star_rating)
    eligible = status.value == "in_policy"
    cap = policy.core.hotel_nightly_cap
    max_stars = policy.core.max_hotel_star_rating

    parts = []
    if cap:
        comparison = "≤" if nightly_rate.amount <= cap.amount else ">"
        parts.append(f"{nightly_rate.amount} {nightly_rate.currency} {comparison} {cap.amount} cap")
    if max_stars and star_rating:
        comparison = "≤" if star_rating <= max_stars else ">"
        parts.append(f"{star_rating}★ {comparison} {max_stars}★ limit")

    quote_parts = []
    if cap:
        quote_parts.append(f"hotels up to {cap.amount} {cap.currency} per night")
    if max_stars:
        quote_parts.append(f"a maximum of {max_stars} stars")
    quote = (
        "Policy permits " + " and ".join(quote_parts) + "."
        if quote_parts
        else "No hotel cap is set in this policy."
    )

    return Verdict(
        eligible=eligible,
        reason_code="hotel_in_policy" if eligible else f"hotel_{status.value}",
        rule_quote=quote,
        request_label=(
            f"{nightly_rate.amount} {nightly_rate.currency} per night"
            + (f" at {star_rating}★" if star_rating else "")
        ),
        computation="; ".join(parts) or None,
    )


def check_advance_purchase(policy: TravelPolicy, depart_on: date, as_of: date) -> Verdict:
    """Is this booked far enough ahead?

    Separate from the cabin check because it fails independently: a compliant cabin booked two days
    out is still out of policy, and collapsing both into one boolean would hide which one broke.
    """
    required = policy.core.advance_purchase_days
    days = (depart_on - as_of).days
    eligible = required is None or days >= required
    return Verdict(
        eligible=eligible,
        reason_code="advance_purchase_met" if eligible else "advance_purchase_short",
        rule_quote=(
            f"Flights must be booked at least {required} days ahead."
            if required
            else "No advance-purchase requirement applies."
        ),
        request_label=f"departure in {days} day{'s' if days != 1 else ''}",
        computation=(
            f"{days} days ahead {'≥' if eligible else '<'} {required} required"
            if required is not None
            else None
        ),
    )


def trip_context(repo: Repository, tenant_id: str, trip_id: str) -> tuple[float, bool] | None:
    """`(flight_hours, is_international)` for the longest air segment of a trip.

    **The longest segment, not the first.** A policy threshold is about the long-haul leg; applying
    it to a short connection would deny a benefit the traveller has earned, and that is exactly the
    off-by-one class of error this module exists to prevent.
    """
    trip = repo.trip(tenant_id, trip_id)
    if trip is None or not trip.air_segments:
        return None
    longest = max(
        trip.air_segments,
        key=lambda segment: (segment.arrive_at - segment.depart_at).total_seconds(),
    )
    hours = (longest.arrive_at - longest.depart_at).total_seconds() / 3600
    return hours, trip.is_international
