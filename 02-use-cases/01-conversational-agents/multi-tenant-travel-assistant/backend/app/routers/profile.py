"""Traveler profile endpoints.

These return the **full** record, PII included — passport numbers, card
last-four, loyalty numbers. That is correct for a system of record, and it is the
point: the tool Lambda curates this down to passport *country* and a masked
payment label before anything reaches model context.

If the backend pre-redacted, the sample would have nothing to demonstrate. The
lesson is that curation belongs to the layer that talks to the model, because
that is the only layer that knows what the model may safely see.
"""

import os

from fastapi import APIRouter, HTTPException, status

from ..dependencies import RepositoryDep, TenantIdDep
from ..models import TravelerProfile
from ..observability import logger

router = APIRouter(prefix="/v1/travelers", tags=["profile"])


@router.get("", response_model=list[TravelerProfile])
def list_travelers(tenant_id: TenantIdDep, repo: RepositoryDep) -> list[TravelerProfile]:
    """All travelers in the tenant."""
    return repo.travelers(tenant_id)


# **The masking demonstration is enabled by an environment variable, not a query parameter.**
#
# It was `?debug_log_pii=true`, which meant *any caller who could reach the URL* could make the
# backend log a full profile — passport number, card last four, loyalty numbers. The switch
# defended itself with a docstring saying never to enable it in production, which is not a control:
# the person it needs to stop is the one who has not read it, and a fork inherits the parameter
# along with the router.
#
# An environment variable moves the decision to whoever controls the deployment. A request cannot
# flip it, so the blast radius of the demo switch is a deploy rather than a URL. Read per-request
# rather than captured at import so a test can set it without rebuilding the app.
PII_LOG_DEMO_VAR = "TRAVEL_DEMO_LOG_PII"


def _pii_log_demo_enabled() -> bool:
    return os.environ.get(PII_LOG_DEMO_VAR, "").lower() == "true"


@router.get("/{traveler_id}", response_model=TravelerProfile)
def get_traveler(
    traveler_id: str,
    tenant_id: TenantIdDep,
    repo: RepositoryDep,
) -> TravelerProfile:
    """One traveler, scoped to the calling tenant.

    A traveler in another tenant is indistinguishable from one that doesn't
    exist — the 404 leaks nothing about whether the id is real elsewhere.

    **`TRAVEL_DEMO_LOG_PII=true` makes this log the unredacted record, to demonstrate that log
    masking works. It must never be set in production**, and it is off unless set — always logging a
    response body would model exactly the practice the masking policy defends against, and a control
    demonstrated by doing the wrong thing everywhere is not a control.

    Why the demonstration is here rather than in a test fixture: this is the *real* path, so one
    call exercises all three layers at once — the backend legitimately returns full PII because it
    is the system of record, CloudWatch masks it at ingestion, and the tool layer would have curated
    it away before the model saw it. A synthetic log line would prove only that masking matches a
    regex.
    """
    traveler = repo.traveler(tenant_id, traveler_id)
    if traveler is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="traveler not found",
        )

    if _pii_log_demo_enabled():
        # Deliberately the raw record, passport number and all. What lands in CloudWatch is
        # masked at ingestion, so the stored line reads `{US_PASSPORT_NUMBER}` — and reading the
        # real value back requires `logs:Unmask`, a *separate* permission from log-read. That
        # separation is the interesting half: an operator browsing logs cannot see a passport
        # number, while an incident responder can be granted it deliberately and audibly.
        # `facts=` nesting matches `log_decision`/`log_refusal`: stdlib `LogRecord` reserves
        # `name`, `module` and others and *raises* on collision, so caller-supplied keys are
        # never spread at the top level.
        logger.warning(
            "DEMO ONLY: logging an unredacted profile to exercise log masking",
            facts={"profile": traveler.model_dump(mode="json")},
        )

    return traveler
