"""Acting on another traveller's behalf.

**Cedar answers the static half; this answers the dynamic half.** Cedar can see claims and
arguments, so it can enforce "only arrangers may name another traveller". It cannot query
DynamoDB, so it cannot know whether *this* arranger may act for *this* traveller. That
question has a current answer, and it is asked here at the moment it matters rather than
read from a claim that went stale.

Shared rather than per-tool because many tools accept an optional traveller, and the check
must be identical in all of them. A tool that forgets it is a tool
that books on the wrong person's record — one of the few genuinely unrecoverable mistakes in
this product, since it moves someone else's money and exposes their itinerary.
"""

from __future__ import annotations

from typing import Any

from .backend import get
from .context import RequestContext, backend_url
from .errors import ToolError
from .observability import count, log_decision, log_refusal


class AmbiguousTravelerError(ToolError):
    """A name matched more than one traveller the caller may act for.

    Carries the candidates so the model can ask *which*, rather than apologise vaguely or —
    far worse — pick one. Ambiguity is a question, never a coin flip.
    """

    def __init__(self, message: str, candidates: list[dict[str, Any]]) -> None:
        super().__init__(message)
        self.candidates = candidates


def resolve_target_traveler(
    context: RequestContext, traveler_name: str | None
) -> tuple[str, str | None]:
    """Return `(traveler_id, resolved_name)` for whoever this call acts on behalf of.

    No name means the caller themselves, which is the common case and needs no lookup or
    authorisation — acting for yourself is not delegation.

    A name is resolved **within the caller's authorised scope**, so ambiguity is bounded by
    permission rather than by how common a name is: an arranger cannot accidentally resolve
    to someone they may not act for, and another tenant's Sam is never a candidate.
    """
    if not traveler_name or not traveler_name.strip():
        if not context.traveler_id:
            raise ToolError("I don't know who this request is for.")
        return context.traveler_id, None

    if not context.traveler_id:
        raise ToolError("I don't know who this request is for.")

    base = backend_url()
    result = get(
        base,
        f"/v1/arrangers/{context.traveler_id}/resolve",
        context,
        params={"name": traveler_name.strip()},
    )

    resolution = (result or {}).get("resolution")
    candidates = (result or {}).get("candidates") or []

    if resolution == "unique":
        candidate = candidates[0]
        log_decision(
            "resolved a traveller name within the caller's authorised scope",
            target_traveler_id=candidate["traveler_id"],
        )
        return candidate["traveler_id"], candidate.get("full_name")

    if resolution == "ambiguous":
        # Names are not logged; the count and the opaque ids are enough to reconstruct the
        # decision, and a traveller's name must never reach a log line.
        log_refusal(
            "traveller name is ambiguous within the authorised scope",
            candidate_ids=[c["traveler_id"] for c in candidates],
        )
        options = ", ".join(
            f"{c['full_name']}"
            + (f" (based in {c['home_airport']})" if c.get("home_airport") else "")
            for c in candidates
        )
        raise AmbiguousTravelerError(
            f"There is more than one {traveler_name.strip()} you can book for: {options}. "
            "Which one did you mean?",
            candidates,
        )

    # Nobody matched. Deliberately the same answer whether the person does not exist or is
    # simply outside this caller's scope — distinguishing them would confirm to an
    # unauthorised caller that a traveller exists.
    log_refusal("traveller name matched nobody in the authorised scope")
    raise ToolError(
        f"I couldn't find anyone called {traveler_name.strip()} that you're able to book for."
    )


def ensure_can_act_for(context: RequestContext, target_traveler_id: str) -> None:
    """Confirm the caller may act for this traveller, right now.

    Called even when the id came from `resolve_target_traveler` — which already scoped its
    search — because a tool may receive an id from a card action or an earlier turn. That is
    design principle 1: **client-held references are re-validated, never trusted.** The
    resolution scope and this check are different guarantees, and the cheap one is not a
    substitute for the correct one.
    """
    if target_traveler_id == context.traveler_id:
        return  # acting for yourself is not delegation

    if not context.traveler_id:
        raise ToolError("I don't know who this request is for.")

    verdict = get(
        backend_url(),
        f"/v1/arrangers/{context.traveler_id}/can-book/{target_traveler_id}",
        context,
    )

    if (verdict or {}).get("allowed"):
        log_decision(
            "authorised to act for another traveller",
            target_traveler_id=target_traveler_id,
            reason=(verdict or {}).get("reason"),
        )
        return

    log_refusal(
        "not authorised to act for that traveller",
        target_traveler_id=target_traveler_id,
    )
    count("ArrangerDenials")
    raise ToolError("You're not set up to book for that traveller.")
