"""Arranger endpoints — authorization as a question, not a field.

`TravelerProfile.can_book_for` already holds this data, so these endpoints add no
storage. What they add is a **boundary**: the relationship becomes something a
tool *asks about* rather than an array a tool happens to read while fetching a
profile. The Cedar policy layer consults these rather than reading a claim.

That boundary is also where the field stops being load-bearing. A real programme
models this as its own many-to-many relation, often *derived* from an attribute
("arranger for cost centre 4400") rather than enumerated, because explicit lists
do not survive enterprise scale. For a handful of fixture travellers a field is
honest and a table would be ceremony — and because callers only ever see these
endpoints, swapping in a real relation later changes one implementation and no
callers.
"""

from fastapi import APIRouter, Query

from ..dependencies import RepositoryDep, TenantIdDep
from ..service.arrangers import (
    Authorization,
    Candidate,
    NameResolution,
    authorized_scope,
    can_book_for,
    resolve_name,
)

router = APIRouter(prefix="/v1/arrangers", tags=["arrangers"])


@router.get("/{arranger_id}/travelers", response_model=list[Candidate])
def list_authorized_travelers(
    arranger_id: str, tenant_id: TenantIdDep, repo: RepositoryDep
) -> list[Candidate]:
    """Everyone this caller may act for, themselves included.

    Candidates rather than full profiles: this answers an authorization question,
    and returning profile rows would put passport numbers in a response whose only
    job is to name people.

    An unknown arranger yields an empty list rather than a 404, because "you may
    act for nobody" is the correct answer for a caller who is not an arranger —
    and a 404 here would confirm whether a traveller id exists.
    """
    scope = authorized_scope(repo, tenant_id, arranger_id)
    return [
        Candidate(
            traveler_id=t.traveler_id,
            full_name=t.full_name,
            home_airport=t.preferences.home_airport,
        )
        for t in scope
    ]


@router.get("/{arranger_id}/can-book/{traveler_id}", response_model=Authorization)
def check_can_book(
    arranger_id: str, traveler_id: str, tenant_id: TenantIdDep, repo: RepositoryDep
) -> Authorization:
    """May this arranger act for this traveller, right now?

    Always 200 with `allowed: true|false` — a denial is a legitimate answer to a
    legitimate question, not an HTTP error. Returning 403 would conflate "you may
    not book for this person" with "you may not ask", and the caller here is an
    authorization layer whose whole purpose is to ask.
    """
    return can_book_for(repo, tenant_id, arranger_id, traveler_id)


@router.get("/{arranger_id}/resolve", response_model=NameResolution)
def resolve_traveler_name(
    arranger_id: str,
    tenant_id: TenantIdDep,
    repo: RepositoryDep,
    name: str = Query(min_length=1, description="A spoken name, full or partial"),
) -> NameResolution:
    """Turn a name into a traveller id, or into a question.

    The model passes a name because that is what a person says; converting it to
    an id is authorization work, so it happens here. Candidates are drawn from the
    caller's authorised scope, which means a shared first name can only ever be
    ambiguous *among people they may already act for*.

    An ambiguous name returns 200 with two candidates rather than an error: the
    agent's correct next move is to ask which, and an error would push it toward
    an apology or, worse, a guess.
    """
    return resolve_name(repo, tenant_id, arranger_id, name)
