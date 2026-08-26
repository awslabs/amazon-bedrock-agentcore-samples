"""`get_travel_policy` — the tenant's structured rules, curated into facts.

The simplest tool in the catalog, chosen as the first one on purpose: a single read,
no composition, no writes. So when the identity chain breaks, the failure is
unambiguously in the wiring rather than in the tool.

**Why a Lambda target rather than OpenAPI.** It fails the 4-clause rule on shaping.
A raw policy record carries `sections`, nulls, nested rule objects and a version
string — more than a model should read, and shaped wrong for narration. Curation is
the tool's whole contribution here.

**Facts, not a summary.** The tool does not write "your cap is $250" because the user
may never have asked about caps. It returns the cap as a fact and lets the model
choose what is worth saying. What the tool *does* own is that the number is correct
and came from this tenant's policy.
"""

from __future__ import annotations

from typing import Any

from shared.cards import Action, CardType, action, card
from tools.common import (
    BackendError,
    RequestContext,
    ToolError,
    backend_url,
    dispatch,
    get,
    log_decision,
    post,
    tool_response,
)

from .schemas import CABINS, CHECK_POLICY_ELIGIBILITY, CHECKS, GET_TRAVEL_POLICY, TOPICS


def _money(value: Any) -> dict[str, Any] | None:
    """Keep amount and currency together.

    Never flattened to a bare number: Globex bills USD and Initech EUR, so a naked
    `250` invites the model to render "$250" for a tenant whose cap is in euros.
    """
    if not isinstance(value, dict) or value.get("amount") is None:
        return None
    return {"amount": str(value["amount"]), "currency": value.get("currency")}


def _core_facts(core: dict[str, Any]) -> dict[str, Any]:
    """Select the typed fields, dropping the ones this tenant leaves unset.

    Absent keys rather than nulls: `"advance_purchase_days": null` reads to a model
    as a value it might mention, while an absent key is simply not part of the
    answer. The distinction matters because "no advance-purchase requirement" and
    "an advance-purchase requirement of null" are different sentences.
    """
    facts: dict[str, Any] = {}

    if cap := _money(core.get("hotel_nightly_cap")):
        facts["hotel_nightly_cap"] = cap
    if (stars := core.get("max_hotel_star_rating")) is not None:
        facts["max_hotel_star_rating"] = stars
    if (days := core.get("advance_purchase_days")) is not None:
        facts["advance_purchase_days"] = days
    if (refundable := core.get("refundable_allowed")) is not None:
        facts["refundable_allowed"] = refundable

    if rule := core.get("cabin_rule"):
        facts["cabin_rule"] = _cabin_rule(rule)

    return facts


def _cabin_rule(rule: dict[str, Any]) -> dict[str, Any]:
    """Describe the cabin rule without evaluating it.

    Deliberately *not* a verdict. "Every 4th international trip" is a fact the model
    may state; "you are entitled to business class" requires counting trips, which
    is `check_policy_eligibility`'s job in code. Returning a verdict here would let
    a follow-up question be answered from a stale count.
    """
    described: dict[str, Any] = {"type": rule.get("type"), "cabin": rule.get("cabin")}

    # Only the parameters this rule type actually uses. A `duration` rule carrying
    # `every_nth_trip: null` invites the model to mention trip counts that do not
    # apply to it.
    if rule.get("type") == "duration" and rule.get("threshold_hours") is not None:
        described["threshold_hours"] = rule["threshold_hours"]
    elif rule.get("type") == "trip_count" and rule.get("every_nth_trip") is not None:
        described["every_nth_trip"] = rule["every_nth_trip"]
        described["period"] = rule.get("period")

    return described


def _rules(raw: Any) -> list[dict[str, Any]]:
    """The loose, prose rules — passed through for narration, never computed on."""
    if not isinstance(raw, list):
        return []
    return [
        {
            "code": rule.get("code"),
            "applies_to": rule.get("applies_to"),
            "description": rule.get("description"),
        }
        for rule in raw
        if isinstance(rule, dict) and rule.get("description")
    ]


def _facts_for_topic(payload: dict[str, Any]) -> dict[str, Any]:
    facts = _core_facts(payload.get("core") or {})
    if rules := _rules(payload.get("rules")):
        facts["additional_rules"] = rules
    return facts


def get_travel_policy(arguments: dict[str, Any], context: RequestContext) -> dict[str, Any]:
    """Read this tenant's policy. Tenant comes from the verified context, never args.

    A topic is optional: omitting it reads all three, so a broad question does not
    require the model to guess which bucket a rule lives in.
    """
    topic = (arguments.get("topic") or "").strip().lower() or None

    # The schema cannot express a closed set (no `enum` in inlinePayload), so the
    # tool enforces it. Refusing beats silently reading a different topic than the
    # model asked for.
    if topic is not None and topic not in TOPICS:
        raise ToolError(
            f"'{topic}' isn't a policy topic I can read. Valid topics are: {', '.join(TOPICS)}."
        )

    base = backend_url()

    if topic:
        payload = get(base, f"/v1/policy/{topic}", context)
        facts = _facts_for_topic(payload)
        version = payload.get("version")
        topics_read = [topic]
    else:
        payloads = get(base, "/v1/policy", context) or []
        facts = {}
        topics_read = []
        version = None
        for payload in payloads:
            if not isinstance(payload, dict):
                continue
            topics_read.append(payload.get("topic"))
            version = version or payload.get("version")
            # Merge across topics: the typed core fields are disjoint by topic
            # (caps are hotel, cabin rules are air), so a flat merge reads more
            # naturally to the model than a nested per-topic structure would.
            for key, value in _facts_for_topic(payload).items():
                if key == "additional_rules":
                    facts.setdefault("additional_rules", []).extend(value)
                else:
                    facts[key] = value

    # The decision, not the action: which tenant's policy was read, and what came
    # back. No policy *values* in the log — a cap is not secret, but logging payload
    # contents by default is the habit that eventually logs a passport.
    log_decision(
        "read travel policy",
        topics=topics_read,
        fact_keys=sorted(facts),
        policy_version=version,
    )

    if not facts:
        # An empty policy would read as "no restrictions" — the most dangerous
        # possible default, so it is a refusal instead.
        return tool_response(
            message="I couldn't find any travel policy on file for your company.",
            provenance={"source": "travel_policy", "tenant_id": context.tenant_id},
        )

    return tool_response(
        facts=facts,
        provenance={
            "source": "travel_policy",
            "tenant_id": context.tenant_id,
            "topics": topics_read,
            "policy_version": version,
        },
    )


def check_policy_eligibility(arguments: dict[str, Any], context: RequestContext) -> dict[str, Any]:
    """Return a **decided** verdict, with the arithmetic shown.

    **The tool does not compute the answer, and that is the point.** The comparison rules live on
    the backend's policy model because search annotates every option with them; recomputing them
    here would be the same rule in two languages behind two deploys, and the drift surfaces as
    search saying "in policy" while eligibility says "no". So this shapes the question, calls the
    backend, and renders the verdict.

    It also does not hand the model raw figures to compare. Returning the cap, the threshold and
    the trip history would usually work and be confidently wrong at the edges — an off-by-one on an
    entitlement window, a threshold applied to the wrong leg. Those failures survive a demo.
    """
    check = (arguments.get("check") or "").strip().lower()
    if check not in CHECKS:
        raise ToolError(f"I can't decide '{check}'. I can check: {', '.join(CHECKS)}.")

    body: dict[str, Any] = {"check": check}

    if check == "air":
        cabin = (arguments.get("cabin") or "").strip().lower()
        if cabin not in CABINS:
            raise ToolError(f"I need to know which cabin to check. One of: {', '.join(CABINS)}.")
        body["cabin"] = cabin
        if trip_id := (arguments.get("trip_id") or "").strip():
            body["trip_id"] = trip_id
        elif (hours := arguments.get("flight_hours")) is not None:
            body["flight_hours"] = hours
        else:
            raise ToolError(
                "To check a cabin I need either the flight length in hours, or the id of the "
                "trip it is for."
            )

    elif check == "hotel":
        amount = arguments.get("nightly_rate_amount")
        if amount is None:
            raise ToolError("To check a hotel against policy I need the nightly rate.")
        # Flattened in the schema because `inlinePayload` supports no nested objects, and
        # reassembled here — the backend's contract is a `Money`, and bending that to suit a
        # schema limitation would leak the limitation into the API.
        currency = (arguments.get("nightly_rate_currency") or "").strip().upper()
        body["nightly_rate"] = {
            "amount": str(amount),
            # Absent currency means the caller's own policy currency, which the backend knows and
            # the model should not have to guess.
            "currency": currency or _policy_currency(context),
        }
        if (stars := arguments.get("star_rating")) is not None:
            body["star_rating"] = int(stars)

    else:
        depart_on = (arguments.get("depart_on") or "").strip()
        if not depart_on:
            raise ToolError("To check advance purchase I need the departure date.")
        body["depart_on"] = depart_on

    verdict = post(backend_url(), "/v1/eligibility", context, body=body)
    if not isinstance(verdict, dict):
        raise ToolError("I couldn't get a policy decision just now, so I'd rather not guess.")

    facts = {
        "eligible": verdict.get("eligible"),
        "reason_code": verdict.get("reason_code"),
        "rule_quote": verdict.get("rule_quote"),
        # The arithmetic. Present so the model can show *why* rather than asserting a verdict the
        # user has to take on trust.
        "computation": verdict.get("computation"),
    }
    if (remaining := verdict.get("trips_until_entitled")) is not None:
        # Lets the agent say "two more international trips" instead of a bare no. A refusal that
        # explains itself is actionable.
        facts["trips_until_entitled"] = remaining

    log_decision(
        "decided policy eligibility",
        check=check,
        eligible=verdict.get("eligible"),
        reason_code=verdict.get("reason_code"),
    )

    return tool_response(
        cards=[
            card(
                CardType.POLICY_VERDICT,
                f"verdict-{check}",
                {
                    "request_label": verdict.get("request_label"),
                    "eligible": verdict.get("eligible"),
                    "rule_quote": verdict.get("rule_quote"),
                    "reason_code": verdict.get("reason_code"),
                    "computation": verdict.get("computation"),
                },
                [action(Action.VIEW_TRAVEL_POLICY, "View travel policy")],
            )
        ],
        facts=facts,
        provenance={
            "source": "policy_eligibility",
            "tenant_id": context.tenant_id,
            "check": check,
            # Named so a reader of the transcript knows the verdict was computed rather than
            # inferred by the model.
            "decided_by": "backend policy engine",
        },
    )


def _policy_currency(context: RequestContext) -> str:
    """The caller's own policy currency, so the model never has to guess one.

    Falls back to USD only if the hotel policy carries no cap at all — at which point the currency
    is not used for a comparison anyway.
    """
    try:
        payload = get(backend_url(), "/v1/policy/hotel", context)
        cap = ((payload or {}).get("core") or {}).get("hotel_nightly_cap") or {}
        return cap.get("currency") or "USD"
    except BackendError:
        return "USD"


TOOLS = {
    GET_TRAVEL_POLICY: get_travel_policy,
    CHECK_POLICY_ELIGIBILITY: check_policy_eligibility,
}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Gateway target entry point. All the shared work lives in `dispatch`."""
    return dispatch(event, context, TOOLS)
