"""Arranger authorization and name resolution.

Two questions the travel platform owns, and the identity provider does not:

1. **May this person act for that one?** A corporate directory authenticates who
   you are; it has no concept of who may book on whose behalf. That mapping is
   configured in the booking tool, so it is resolved here — live, at the moment it
   matters — rather than copied into a token that would go stale for its whole
   lifetime.
2. **Which "Sam" did the user mean?** The model passes a *name*, because that is
   what a person says. Turning it into a traveller id is authorization work, not
   language work, so it happens in code.

**Resolution is bounded by permission, not by the directory.** Candidates come
from the caller's authorised set, so an arranger cannot resolve to someone they
may not book for — ambiguity is limited by what they are allowed to do rather
than by how common a name is. The tenant's other travellers are not merely
filtered out at the end; they are never candidates.
"""

from enum import StrEnum

from pydantic import BaseModel, Field

from ..models import TravelerProfile
from ..models.common import TenantId, TravelerId
from ..observability import log_decision, log_refusal
from ..repository import Repository


class Resolution(StrEnum):
    """Why a name did or did not become a single traveller.

    Three outcomes rather than an optional id, because the caller must handle
    them differently: `AMBIGUOUS` is a question to ask the user, `NONE` is a
    refusal, and only `UNIQUE` may proceed. Returning `None` for both failure
    cases would let a caller collapse them into one wrong message.
    """

    UNIQUE = "unique"
    AMBIGUOUS = "ambiguous"
    NONE = "none"


class Candidate(BaseModel):
    """A traveller the caller may act for, with enough context to choose between.

    `"Did you mean Sam or Sam?"` is a useless question, so a candidate carries a
    differentiator. Home airport is the one that reads naturally in a
    disambiguation prompt ("Sam in Chicago or Sam in San Francisco?") and is not
    personal data in the way a passport or an email address is.

    Deliberately not the full profile: this list can be long, it exists to answer
    an authorization question, and a profile row here would put passport numbers
    into a response whose only job is to name people.
    """

    traveler_id: TravelerId
    full_name: str
    home_airport: str | None = None


class NameResolution(BaseModel):
    """The outcome of turning a spoken name into a traveller id."""

    resolution: Resolution
    query: str
    candidates: list[Candidate] = Field(default_factory=list)

    @property
    def traveler_id(self) -> TravelerId | None:
        """The resolved id, and only when it is unambiguous."""
        return self.candidates[0].traveler_id if self.resolution is Resolution.UNIQUE else None


class Authorization(BaseModel):
    """Whether one traveller may act for another, and why.

    The reason is part of the contract rather than a log detail: the agent needs
    to tell the user *why* it will not act, and "you are not an arranger" and "you
    are not authorised for this person" call for different next steps.
    """

    allowed: bool
    arranger_id: TravelerId
    traveler_id: TravelerId
    reason: str


# --- authorised scope ------------------------------------------------------


def authorized_scope(
    repo: Repository, tenant_id: TenantId, actor_id: TravelerId
) -> list[TravelerProfile]:
    """Everyone this caller may act for, themselves included.

    Self is in scope because acting for yourself is the common case — an arranger
    who books their own travel would otherwise fail the same check that protects
    everyone else. For a plain traveller the scope is exactly one person, which is
    why no separate role branch is needed downstream.

    An id in `can_book_for` that no longer resolves is skipped rather than raised
    on: a departed colleague should narrow an arranger's scope, not break every
    request they make.
    """
    actor = repo.traveler(tenant_id, actor_id)
    if actor is None:
        return []

    scope = [actor]
    for traveler_id in actor.can_book_for:
        managed = repo.traveler(tenant_id, traveler_id)
        if managed is not None:
            scope.append(managed)
    return scope


def can_book_for(
    repo: Repository, tenant_id: TenantId, arranger_id: TravelerId, traveler_id: TravelerId
) -> Authorization:
    """Answer "may X book for Y?" as an explicit question with a current answer.

    The Cedar policy layer consults this rather than reading a claim. The decision is
    logged either way — a denial that leaves no trace is indistinguishable from a
    bug, and an approval with no trace cannot be audited.
    """
    scope = {t.traveler_id for t in authorized_scope(repo, tenant_id, arranger_id)}

    if traveler_id in scope:
        result = Authorization(
            allowed=True,
            arranger_id=arranger_id,
            traveler_id=traveler_id,
            reason="self" if arranger_id == traveler_id else "in the arranger's authorised list",
        )
        log_decision(
            "arranger authorised",
            arranger_id=arranger_id,
            target_traveler_id=traveler_id,
            reason=result.reason,
            scope_size=len(scope),
        )
        return result

    # An unknown traveller and an unauthorised one get the same answer on
    # purpose: distinguishing them would confirm whether an id exists to a caller
    # with no right to know.
    result = Authorization(
        allowed=False,
        arranger_id=arranger_id,
        traveler_id=traveler_id,
        reason="not in the arranger's authorised list",
    )
    log_refusal(
        "arranger not authorised",
        arranger_id=arranger_id,
        target_traveler_id=traveler_id,
        scope_size=len(scope),
    )
    return result


# --- name resolution -------------------------------------------------------


def _tokens(value: str) -> list[str]:
    return value.casefold().split()


def _matches(query_tokens: list[str], full_name: str) -> bool:
    """Every query token must prefix some name token.

    Token-prefix rather than substring so "Adewale" finds "Sam Adewale" without
    depending on word order, and "Sam Ade" narrows to one person. Prefix matching
    deliberately keeps "Sam" matching "Samantha": over-matching produces a
    question, under-matching produces a wrong refusal, and the question is the
    safer failure.
    """
    name_tokens = _tokens(full_name)
    return all(
        any(name_token.startswith(query_token) for name_token in name_tokens)
        for query_token in query_tokens
    )


def resolve_name(
    repo: Repository, tenant_id: TenantId, actor_id: TravelerId, name: str
) -> NameResolution:
    """Turn a spoken name into a traveller id within the caller's authorised scope.

    Returns candidates rather than a guess when a name is shared. Booking against
    the wrong person's record is one of the few genuinely unrecoverable mistakes
    in this product — it moves someone else's money and exposes their itinerary —
    so an ambiguous name must become a question.

    An exact full-name match wins outright even when it also prefixes a longer
    name, because "Sam" resolving to "Sam" while "Samantha" exists is the answer
    the user meant, not an ambiguity.
    """
    query = name.strip()
    query_tokens = _tokens(query)

    if not query_tokens:
        log_refusal("name resolution attempted with an empty name", actor_id=actor_id)
        return NameResolution(resolution=Resolution.NONE, query=query)

    scope = authorized_scope(repo, tenant_id, actor_id)
    matched = [t for t in scope if _matches(query_tokens, t.full_name)]

    if len(matched) > 1:
        exact = [t for t in matched if _tokens(t.full_name) == query_tokens]
        if len(exact) == 1:
            matched = exact

    candidates = [
        Candidate(
            traveler_id=t.traveler_id,
            full_name=t.full_name,
            home_airport=t.preferences.home_airport,
        )
        for t in matched
    ]

    if not candidates:
        # Not an error: the arranger may simply have named someone outside their
        # scope, which is exactly what the scope is for.
        log_refusal(
            "name matched nobody in the authorised scope",
            actor_id=actor_id,
            scope_size=len(scope),
        )
        return NameResolution(resolution=Resolution.NONE, query=query, candidates=[])

    resolution = Resolution.UNIQUE if len(candidates) == 1 else Resolution.AMBIGUOUS

    # Names are not logged — only the count and the ids, which are opaque. The
    # decision is still reconstructable: "2 candidates, asked the user" is the
    # fact that matters, and it needs no personal data to be useful.
    log_decision(
        f"name resolved to {len(candidates)} candidate(s) -> {resolution}",
        actor_id=actor_id,
        candidate_ids=[c.traveler_id for c in candidates],
        scope_size=len(scope),
        resolution=resolution,
    )
    return NameResolution(resolution=resolution, query=query, candidates=candidates)
