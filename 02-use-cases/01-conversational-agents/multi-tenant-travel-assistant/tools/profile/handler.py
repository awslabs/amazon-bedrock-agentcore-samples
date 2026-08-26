"""`get_traveler_profile` — the PII curation demonstration.

The backend returns the **full** record: passport numbers, card last-four, loyalty numbers.
That is correct for a system of record, and it is the point — this tool exists to show that
**curation belongs to the layer that talks to the model**, because that is the only layer
which knows what the model may safely see.

What crosses this boundary:

| Backend has | Model gets | Why |
|---|---|---|
| `passports[].number` | *nothing* | never needed downstream; a leak with no upside |
| `passports[].country` | the country | entry requirements need the issuing country |
| `loyalty[].number` | *nothing* | booking passes a profile reference instead |
| `loyalty[].program/tier` | both | "you're Gold with United" is the useful part |
| `payment_instruments[].last_four` | *nothing* | the label identifies the card |
| `…[].display_label` | label, **digits stripped** | a label built upstream smuggles digits |
| `…[].payment_profile_id` | the id | booking passes a reference, not card data |

**PII that never leaves this Lambda cannot leak into model context, a card, a log, or a
transcript.** Bedrock Guardrails and log-ingestion masking are backstops for mistakes;
this is the primary control, and "never present" beats "present then masked".
"""

from __future__ import annotations

import re
from typing import Any

from shared.cards import CardType, card
from tools.common import (
    RequestContext,
    backend_url,
    dispatch,
    get,
    log_decision,
    tool_response,
)
from tools.common.authz import ensure_can_act_for, resolve_target_traveler

from .schemas import GET_TRAVELER_PROFILE


def _preferences(raw: dict[str, Any]) -> dict[str, Any]:
    """Declared preferences — what the traveller entered in a form.

    Distinct from *observed* preferences ("always books the 6am flight"), which are
    AgentCore Memory's job. This is the system of record; memory is the
    personalisation layer on top, and conflating them would make a stale form entry look
    like learned behaviour.
    """
    out: dict[str, Any] = {}
    for key in ("home_airport", "seat", "preferred_cabin", "dietary_notes"):
        if value := raw.get(key):
            out[key] = value
    if chains := raw.get("preferred_hotel_chains"):
        out["preferred_hotel_chains"] = chains
    return out


def _loyalty(raw: Any) -> list[dict[str, Any]]:
    """Programme and tier. **Never the membership number.**

    The number is PII with no downstream use: booking passes a profile reference, and the
    tier is the part that changes an answer ("you're Gold, so lounge access is included").
    """
    if not isinstance(raw, list):
        return []
    return [
        {"program": item.get("program"), "tier": item.get("tier")}
        for item in raw
        if isinstance(item, dict) and item.get("program")
    ]


def _passports(raw: Any) -> list[dict[str, Any]]:
    """Issuing country and expiry only. **Never the passport number.**

    Expiry is included because it changes advice — a passport expiring within six months
    fails entry requirements for many destinations, and that is a useful thing to surface
    without ever naming the document.
    """
    if not isinstance(raw, list):
        return []
    return [
        {"country": item.get("country"), "expires_on": item.get("expires_on")}
        for item in raw
        if isinstance(item, dict) and item.get("country")
    ]


def _payment(raw: Any) -> list[dict[str, Any]]:
    """A reference and a label with the digits stripped out of it.

    `payment_profile_id` is what `confirm_booking` passes to the backend, so the model can say
    "I'll use your Globex corporate Visa" and the charge is recorded against a reference only
    the backend can resolve. Card data never enters the agent, the model, or a tool argument —
    which is what keeps PCI-shaped data behind the API.

    **`display_label` had to be sanitised, and that is the most instructive bug in this
    file.** Dropping `last_four` felt sufficient; a test asserting the digits were absent
    then failed, because the backend's own label is
    `"Visa •••4821 — Globex corporate"` — a *human-readable* field, built by another system,
    carrying the exact value being withheld.

    The general lesson for curation: an allowlist protects you only if you also know what the
    allowed fields *contain*. Free-text and display strings composed upstream are the ones
    that smuggle PII past a field-level review, because nobody thinks of a label as data.
    """
    if not isinstance(raw, list):
        return []
    return [
        {
            "payment_profile_id": item.get("payment_profile_id"),
            "label": _strip_digit_groups(item.get("display_label")),
        }
        for item in raw
        if isinstance(item, dict) and item.get("payment_profile_id")
    ]


# Three or more consecutive digits. Deliberately blunt: this runs over labels a *backend*
# composed, so the safe assumption is that any digit run could be part of an account number.
# Over-redacting a label costs nothing ("Visa ••• — Globex corporate" still identifies the
# card to its owner); under-redacting puts card digits in model context.
_DIGIT_RUN = re.compile(r"\d{3,}")


def _strip_digit_groups(label: Any) -> str | None:
    if not label:
        return None
    return _DIGIT_RUN.sub("", str(label)).replace("  ", " ").strip()


def get_traveler_profile(arguments: dict[str, Any], context: RequestContext) -> dict[str, Any]:
    """Read a traveller's profile, curated. Defaults to the caller.

    Acting for someone else passes through both authorization halves: the name is resolved
    inside the caller's authorised scope, then `can_book_for` is re-checked against the
    backend even though the resolution already scoped it — client-held references are
    re-validated, never trusted.
    """
    traveler_id, resolved_name = resolve_target_traveler(context, arguments.get("traveler_name"))
    ensure_can_act_for(context, traveler_id)

    raw = get(backend_url(), f"/v1/travelers/{traveler_id}", context)

    facts: dict[str, Any] = {"full_name": raw.get("full_name"), "role": raw.get("role")}
    if preferences := _preferences(raw.get("preferences") or {}):
        facts["preferences"] = preferences
    if loyalty := _loyalty(raw.get("loyalty")):
        facts["loyalty"] = loyalty
    if passports := _passports(raw.get("passports")):
        facts["passports"] = passports
    if payment := _payment(raw.get("payment_instruments")):
        facts["payment_methods"] = payment

    # The decision and the *shape* of what was returned — never the values. A profile is the
    # densest PII in the system, so this log line is exactly where a careless
    # `facts=facts` would put a passport number into CloudWatch.
    log_decision(
        "read traveller profile",
        target_traveler_id=traveler_id,
        acting_for_self=traveler_id == context.traveler_id,
        fact_keys=sorted(facts),
        loyalty_count=len(facts.get("loyalty", [])),
        passport_count=len(facts.get("passports", [])),
    )

    # **The card carries the curated view, and only fields already curated above.**
    # `CardType.PROFILE` and its `Profile` component both existed from the start, and nothing
    # ever emitted one — so the PII-curation demonstration had no visible surface, and the eval
    # fixture asking for a profile card was asserting something no tool could produce.
    #
    # Built from `facts`, never from `raw`. Reaching back into the backend response for a
    # "convenient" field is how a passport number would reach the client: the curation above is
    # the only thing between `raw` and the browser, and a card built from `raw` walks around it.
    # `loyalty` is the programme without its number, `passport_country` the country without the
    # document — the same withholding, now visible.
    card_data: dict[str, Any] = {
        "traveler_name": facts.get("full_name"),
        "home_airport": (facts.get("preferences") or {}).get("home_airport"),
        "loyalty": facts.get("loyalty") or [],
        "passport_country": next(
            (p.get("country") for p in facts.get("passports") or [] if p.get("country")), None
        ),
    }

    return tool_response(
        # No actions: a profile is a statement of record, and every button that belongs near one
        # ("edit", "add a passport") is a different system's job.
        cards=[card(CardType.PROFILE, f"profile-{traveler_id}", card_data)],
        facts=facts,
        provenance={
            "source": "traveler_profile",
            "tenant_id": context.tenant_id,
            "traveler_id": traveler_id,
            # Stated so a reader of the transcript knows curation happened, rather than
            # assuming the backend simply had nothing more.
            "curated": "passport numbers, loyalty numbers and card digits withheld",
        },
    )


TOOLS = {GET_TRAVELER_PROFILE: get_traveler_profile}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Gateway target entry point. All the shared work lives in `dispatch`."""
    return dispatch(event, context, TOOLS)
