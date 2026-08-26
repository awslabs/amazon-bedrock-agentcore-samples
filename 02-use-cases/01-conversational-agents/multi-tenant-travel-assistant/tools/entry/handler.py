"""`check_entry_requirements` — visa rules, with uncertainty preserved.
**The tool where a confidently wrong answer strands someone at a border.** That single fact drives
every decision here.

**"Not on file" is never narrated as "no visa required".** The backend returns 404 for a pair it has
no data for, and this tool relays that as explicit uncertainty with a route to a real answer. The
tempting failure — treating absence as permission — would produce a fluent, plausible, actionable
lie. Refusal beats invention is a general rule; here it is the difference between an inconvenience
and a missed flight.

**The disclaimer is always present**, on the card and in facts, because entry advice is
legal-adjacent and must never read as authoritative. The data is fictional; a production system
reads from a licensed provider behind the same contract.

**The passport country is never an argument.** It comes from the profile, server-side.
"""

from __future__ import annotations

import json
from typing import Any

from shared.cards import CardType, card
from tools.common import (
    BackendError,
    RequestContext,
    ToolError,
    backend_url,
    dispatch,
    ensure_can_act_for,
    get,
    log_decision,
    log_refusal,
    resolve_target_traveler,
    tool_response,
)

from .schemas import CHECK_ENTRY_REQUIREMENTS

# What each requirement means in a sentence the model can relay without embellishing.
MEANINGS = {
    "none": "No visa is required for a short business visit.",
    "evisa": "An electronic visa or travel authorisation is required before departure.",
    "visa": "A visa must be obtained in advance.",
}


def _detail(error: BackendError) -> Any:
    text = str(error)
    start = text.find("{")
    if start < 0:
        return None
    try:
        return json.loads(text[start:]).get("detail")
    except json.JSONDecodeError:
        return None


def check_entry_requirements(arguments: dict[str, Any], context: RequestContext) -> dict[str, Any]:
    """Entry rules for the traveller's own passport into a destination."""
    destination = (arguments.get("destination_country") or "").strip().upper()
    if not destination:
        raise ToolError("I need the destination country to check entry requirements.")
    if len(destination) != 2 or not destination.isalpha():
        # A country *name* would silently miss the fixture lookup and return "not on file", which
        # reads as uncertainty about the destination rather than about our input. Refusing names it.
        raise ToolError(
            f"I need a two-letter country code rather than {destination!r} — "
            "for example 'IN' for India or 'GB' for the United Kingdom."
        )

    traveler_id, _ = resolve_target_traveler(context, arguments.get("traveler_name"))
    ensure_can_act_for(context, traveler_id)

    try:
        found = get(backend_url(), f"/v1/entry-requirements/{destination}", context)
    except BackendError as error:
        if error.status == 404:
            detail = _detail(error)
            passport = (detail or {}).get("passport_country") if isinstance(detail, dict) else None
            log_refusal(
                "no entry rules on file",
                destination_country=destination,
                passport_country=passport,
            )
            # **Uncertainty, stated as uncertainty.** No card: a card would render as an answer,
            # and there is no answer here.
            return tool_response(
                message=(
                    f"I don't have entry rules on file for travel to {destination}"
                    + (f" on a {passport} passport" if passport else "")
                    + ". That means I don't know — not that no visa is needed. Your travel team "
                    "or the destination's embassy can confirm before you book."
                ),
                facts={
                    "requirement": "unknown",
                    # Named so a model cannot round "unknown" down to "none".
                    "meaning": (
                        "no data on file; this is not a statement that travel is unrestricted"
                    ),
                    "destination_country": destination,
                },
                provenance={"source": "entry_requirements", "tenant_id": context.tenant_id},
            )
        raise

    requirement = (found or {}).get("requirement") or "unknown"
    disclaimer = (found or {}).get("disclaimer") or ("Verify with official sources before travel.")

    log_decision(
        "checked entry requirements",
        destination_country=destination,
        requirement=requirement,
        # The passport *country* only — never a number. This is the densest PII path in the tool set
        # after the profile, and a careless log line here would put a nationality in CloudWatch
        # alongside a traveller id.
        passport_country=(found or {}).get("passport_country"),
    )

    data: dict[str, Any] = {
        "destination_country": destination,
        "passport_country": (found or {}).get("passport_country"),
        # **The sentence, not the enum.** `requirement` is `none`/`evisa`/`visa` — machine values,
        # and
        # a card that rendered `none` told a traveller "none" where the answer is "no visa
        # required".
        # Nearly the opposite reading, on the one artefact people screenshot. The raw value stays in
        # `facts` for the model and for anything that needs to branch on it.
        "requirement": MEANINGS.get(requirement, "Requirement is unclear; verify before travel."),
        # Always present, on the card as well as in facts: a rendered tile that omitted it would be
        # the one artefact a user screenshots and treats as authoritative.
        "disclaimer": disclaimer,
    }
    if note := (found or {}).get("note"):
        data["apply_note"] = note

    return tool_response(
        # No actions — there is nothing to click. Applying for a visa happens outside this system,
        # and a button implying otherwise would overpromise.
        cards=[card(CardType.ENTRY_REQUIREMENTS, f"entry-{destination}", data)],
        facts={
            "requirement": requirement,
            "meaning": MEANINGS.get(requirement, "Requirement is unclear; verify before travel."),
            "destination_country": destination,
            "apply_note": (found or {}).get("note"),
            "disclaimer": disclaimer,
        },
        provenance={
            "source": "entry_requirements",
            "tenant_id": context.tenant_id,
            "traveler_id": traveler_id,
            # Stated so a reader knows this is demo data rather than a licensed feed.
            "data_source": "fictional demo matrix; production reads a licensed provider",
        },
    )


TOOLS = {CHECK_ENTRY_REQUIREMENTS: check_entry_requirements}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Gateway target entry point. All the shared work lives in `dispatch`."""
    return dispatch(event, context, TOOLS)
