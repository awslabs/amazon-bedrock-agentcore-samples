"""Eligibility endpoint — the verdict, decided here.

**Why this exists as an endpoint rather than logic in the tool.** The comparison rules already live
on the policy model, because search annotates every option with them. A second implementation in
the tool layer would be the same rule in two languages behind two deploys — and the drift shows up
as search saying "in policy" while eligibility says "no", which is the worst kind of bug: both
answers look authoritative.

**Why a POST.** The question has a small object's worth of inputs (cabin, hours or trip, rate,
stars, an as-of date), and cramming that into a query string would make the awkward combinations
easy to get wrong. Nothing is written; the verb is about payload shape, not mutation.
"""

from datetime import date

from fastapi import APIRouter, HTTPException, status

from ..dependencies import RepositoryDep, ScenarioFlagsDep, TenantIdDep, TravelerIdDep
from ..models import EligibilityRequest, EligibilityVerdict
from ..service import policy_check
from ..service.drift import apply_to_policy

router = APIRouter(prefix="/v1/eligibility", tags=["eligibility"])

CHECKS = ("air", "hotel", "advance_purchase")


def _policy(repo, tenant_id: str, topic: str, flags):
    policy = repo.policy(tenant_id, topic)
    if policy is None:
        # A missing policy is a 404, never an empty one. An empty policy reads as "no
        # restrictions", which is the most dangerous possible default for an eligibility answer.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no {topic} policy for this tenant",
        )
    # The same drift the policy read applies, for the same reason: a verdict computed from an
    # undrifted cap would disagree with the cap the policy tool just reported.
    return apply_to_policy(policy, flags)


@router.post("", response_model=EligibilityVerdict)
def check_eligibility(
    request: EligibilityRequest,
    tenant_id: TenantIdDep,
    traveler_id: TravelerIdDep,
    repo: RepositoryDep,
    flags: ScenarioFlagsDep,
) -> EligibilityVerdict:
    """Decide one eligibility question and show the arithmetic.

    Refuses an incomplete request rather than assuming a default: an assumed flight duration or an
    assumed nightly rate produces a confident answer to a question nobody asked, which is worse
    than an error the caller can fix.
    """
    as_of = request.as_of or date.today()
    check = (request.check or "").strip().lower()

    if check not in CHECKS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unknown check {check!r}; expected one of {', '.join(CHECKS)}",
        )

    if check == "air":
        if request.cabin is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="air eligibility needs a cabin",
            )
        hours = request.flight_hours
        exclude: str | None = None
        if hours is None and request.trip_id:
            # Derived from the trip's **longest** air segment — a threshold is about the long-haul
            # leg, and applying it to a short connection would deny an earned benefit.
            context = policy_check.trip_context(repo, tenant_id, request.trip_id)
            if context is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="no trip with air segments for that id",
                )
            hours, _ = context
            # A trip cannot count itself as prior history when asked about itself.
            exclude = request.trip_id
        if hours is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="air eligibility needs either flight_hours or a trip_id",
            )
        verdict = policy_check.check_cabin(
            repo,
            tenant_id,
            traveler_id,
            _policy(repo, tenant_id, "air", flags),
            request.cabin,
            hours,
            as_of,
            exclude_trip_id=exclude,
        )

    elif check == "hotel":
        if request.nightly_rate is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="hotel eligibility needs a nightly_rate",
            )
        verdict = policy_check.check_hotel(
            _policy(repo, tenant_id, "hotel", flags), request.nightly_rate, request.star_rating
        )

    else:
        if request.depart_on is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="advance-purchase eligibility needs depart_on",
            )
        verdict = policy_check.check_advance_purchase(
            _policy(repo, tenant_id, "air", flags), request.depart_on, as_of
        )

    return EligibilityVerdict(
        eligible=verdict.eligible,
        reason_code=verdict.reason_code,
        rule_quote=verdict.rule_quote,
        request_label=verdict.request_label,
        computation=verdict.computation,
        trips_until_entitled=verdict.trips_until_entitled,
    )
