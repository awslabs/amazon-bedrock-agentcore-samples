"""The write path: `prepare_booking`, `confirm_booking`, `cancel_reservation`.

**The only tools where an error is unrecoverable**, which shapes every decision here.

**Nothing is auto-booked.** `prepare_booking` holds and prices; `confirm_booking` is a separate call
that a human's explicit confirmation triggers. Collapsing them into one "book it" tool would make
the model's judgement the last thing between a search result and a charge.

**The tenant decides how far the agent may go.** A `confirm_in_chat` tenant gets a summary card
with confirm and decline actions. A `handoff` tenant gets **no confirm action at all** — the card
renders a checkout link instead, and `confirm_booking` refuses. This is a real per-customer
difference rather than a setting: many travel programmes will not let an assistant transact, and a
sample that assumed otherwise would not be deployable by them.

**Cancellation is two-stage.** First call returns penalties and cancels nothing. "Cancel my hotel"
is not agreement to a $200 penalty the traveller has not been shown — and a cancellation is
unrecoverable, so the confirmation must be informed rather than merely present.

**Client input is an identifier, never a value.** No price, no description, no traveller id is
accepted back. The server re-derives and re-validates on every step, which is why a fare that moved
between prepare and confirm becomes a refusal rather than a surprise charge.
"""

from __future__ import annotations

import json
import re
from typing import Any

from shared.cards import Action, CardType, action, card
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
    post,
    resolve_target_traveler,
    tool_response,
)

from .schemas import CANCEL_RESERVATION, CONFIRM_BOOKING, KINDS, PREPARE_BOOKING

CONFIRM_IN_CHAT = "confirm_in_chat"

# **The shape of a real offer handle, so a fabricated one is refused before a request is spent.**
# `booking.hold` issues `f"off_{secrets.token_hex(5)}"` — ten hex characters. Checked rather than
# trusted
# because the schema's "do not invent one" did not hold: measured against a deployed agent, it sent
# `book_7a1d3e9f2b4c6a8e` — plausible, well-formed and entirely made up — while the real reference
# from
# the `prepare_booking` immediately before it was `off_294eae67b1`.
#
# The cost of not checking was a *wrong answer*, not an error: the backend refused correctly, and
# the
# tool relayed "that hold is no longer valid — it may have expired" about a hold seconds old. The
# model
# then searched and re-prepared, leaving two holds and confirming neither.
_OFFER_REF = re.compile(r"^off_[0-9a-f]{10}$")


def _money(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    if not raw:
        return None
    return {"amount": raw.get("amount"), "currency": raw.get("currency")}


def _detail(error: BackendError) -> Any:
    """The backend's `detail`, parsed out of the error message.

    Needed because the interesting refusals carry structure — a moved fare returns both prices, and
    relaying "the fare changed" without them would leave the traveller unable to decide.
    """
    text = str(error)
    start = text.find("{")
    if start < 0:
        return None
    try:
        return json.loads(text[start:]).get("detail")
    except json.JSONDecodeError:
        return None


def _tenant_config(context: RequestContext) -> dict[str, Any]:
    """The caller's own tenant settings.

    Read per request rather than cached: booking mode is a runtime-changeable setting, and a stale
    cache here would let the agent offer to confirm for a tenant that has since disabled it.
    """
    try:
        return get(backend_url(), "/v1/config", context) or {}
    except BackendError:
        # Fail *closed*: an unknown booking mode must not default to "may transact".
        log_refusal("could not read tenant booking mode — assuming handoff")
        return {"booking_mode": "handoff"}


def _payment_label(context: RequestContext, traveler_id: str) -> str:
    """A masked payment label for the summary card.

    Read from the profile tool's own curation path, so the digits never reach here. If it is
    unavailable the card says so rather than inventing a card — "Visa •••1234" that does not exist
    is worse than "payment method on file".
    """
    try:
        profile = get(backend_url(), f"/v1/travelers/{traveler_id}", context) or {}
    except BackendError:
        return "Corporate card on file"
    for instrument in profile.get("payment_instruments") or []:
        label = instrument.get("display_label") or ""
        # The label may itself contain digits — a masked card label like 'Visa •••4821' hides them
        # in plain sight — so only the non-numeric part is used. The tool layer never emits
        # card digits, even indirectly.
        cleaned = "".join(char for char in label if not char.isdigit()).strip(" •-—")
        if cleaned:
            return cleaned
    return "Corporate card on file"


def prepare_booking(arguments: dict[str, Any], context: RequestContext) -> dict[str, Any]:
    """Hold and price a chosen option, and return it for review. Books nothing."""
    option_id = (arguments.get("option_id") or "").strip()
    kind = (arguments.get("kind") or "").strip().lower()
    destination = (arguments.get("destination") or "").strip()

    if not option_id:
        raise ToolError(
            "I need the id of the option you chose. Search again and pick one of the results."
        )
    if kind not in KINDS:
        raise ToolError(f"I can prepare bookings for: {', '.join(KINDS)}.")
    if not destination:
        raise ToolError("I need the destination from the search that produced this option.")

    traveler_id, _ = resolve_target_traveler(context, arguments.get("traveler_name"))
    ensure_can_act_for(context, traveler_id)

    body: dict[str, Any] = {"kind": kind, "option_id": option_id, "destination": destination}
    for key in ("origin", "depart_on", "check_in", "check_out"):
        if value := (arguments.get(key) or "").strip():
            body[key] = value

    try:
        held = post(backend_url(), "/v1/booking/hold", context, body=body)
    except BackendError as error:
        # **422 means the caller contradicted itself, not that inventory is gone.** The option id
        # encodes the search that produced it, so a mismatch says the destination or dates sent here
        # are not the ones from that search — which is what happens when the model recalls an option
        # from an earlier turn and retypes the details around it. Telling it "no longer available"
        # sent it searching again and apologising for lost inventory that had never existed.
        if error.status == 422:
            # **The offending values, not just the status.** A mismatch is by definition a
            # disagreement
            # between the option id and the search parameters, so a log without them cannot be
            # diagnosed — which cost a debugging cycle. These four are itinerary details, not PII:
            # no traveller name, no identifiers. The rule is "log an id or a hash, never a value"
            # for
            # *personal* data; a destination and two dates are neither.
            log_refusal(
                "option id did not match the search details",
                status=error.status,
                option_id=option_id,
                destination=destination,
                check_in=arguments.get("check_in"),
                check_out=arguments.get("check_out"),
                depart_on=arguments.get("depart_on"),
            )
            return tool_response(
                message=(
                    "I mixed up the details for that option. Let me search again and pick it "
                    "straight from the results."
                ),
                provenance={"source": "booking_hold", "tenant_id": context.tenant_id},
            )
        if error.status in (404, 409, 410):
            # A stale or foreign option id. Refusing and asking for a fresh search is the only safe
            # move: re-searching silently could hold a *different* flight at a different price.
            log_refusal("option could not be held", status=error.status)
            return tool_response(
                message=(
                    "That option is no longer available to book. Let me search again so you can "
                    "pick from current results."
                ),
                provenance={"source": "booking_hold", "tenant_id": context.tenant_id},
            )
        raise

    config = _tenant_config(context)
    mode = config.get("booking_mode") or "handoff"
    booking_ref = (held or {}).get("offer_id") or ""
    total = _money((held or {}).get("display_price"))

    data: dict[str, Any] = {
        "items": [{"type": kind, "label": (held or {}).get("description"), "price": total}],
        "total": total,
        "payment_label": _payment_label(context, traveler_id),
        "policy_status": (held or {}).get("policy_status"),
        "mode": mode,
    }
    # **The per-tenant difference, expressed as UI rather than prose.** A handoff tenant's card has
    # no confirm action, so there is no button to press and no ambiguity about whether the agent may
    # transact. Telling the user "I can't book this" while showing a confirm button would be worse
    # than either alone.
    actions: list[dict[str, Any]] = []
    if mode == CONFIRM_IN_CHAT:
        actions = [
            action(Action.CONFIRM_BOOKING, "Confirm booking", booking_ref=booking_ref),
            action(Action.DECLINE_BOOKING, "Not now", booking_ref=booking_ref),
        ]
    else:
        data["checkout_url"] = f"https://checkout.example/{context.tenant_id}/{booking_ref}"

    log_decision(
        "prepared a booking",
        kind=kind,
        booking_ref=booking_ref,
        target_traveler_id=traveler_id,
        booking_mode=mode,
        policy_status=(held or {}).get("policy_status"),
    )

    return tool_response(
        cards=[card(CardType.BOOKING_SUMMARY, booking_ref, data, actions)],
        facts={
            "booking_ref": booking_ref,
            "total": total,
            "expires_at": (held or {}).get("expires_at"),
            "booking_mode": mode,
            # Said explicitly so the model does not offer to confirm where it cannot.
            "can_confirm_in_chat": mode == CONFIRM_IN_CHAT,
        },
        provenance={
            "source": "booking_hold",
            "tenant_id": context.tenant_id,
            "traveler_id": traveler_id,
            "held_price_is_authoritative": "re-derived on confirm; a moved fare refuses",
        },
    )


def confirm_booking(arguments: dict[str, Any], context: RequestContext) -> dict[str, Any]:
    """Execute a prepared booking. Requires the tenant to permit in-chat booking."""
    booking_ref = (arguments.get("booking_ref") or "").strip()
    if not booking_ref:
        raise ToolError("I need the booking reference from the prepared summary.")

    # **A handle the server never issued is refused here, not at the backend.** Both refuse it, but
    # the
    # messages differ in a way that matters: the backend can only say "no such offer", which the
    # agent
    # relays as *"that hold is no longer valid — it may have expired"*. That sentence is wrong and
    # alarming when the truth is that the handle was invented. Saying what actually happened lets
    # the
    # model recover in one step instead of searching again.
    if not _OFFER_REF.match(booking_ref):
        log_refusal("booking reference was not a server-issued handle", booking_ref=booking_ref)
        return tool_response(
            message=(
                "That is not a booking reference I issued. A real one comes back from "
                "prepare_booking and looks like 'off_' followed by ten hex characters. Call "
                "prepare_booking and use the reference it returns — do not construct one."
            ),
            facts={"booked": False},
            provenance={"source": "booking_confirm", "tenant_id": context.tenant_id},
        )

    config = _tenant_config(context)
    mode = config.get("booking_mode") or "handoff"
    if mode != CONFIRM_IN_CHAT:
        # Refused at the tool, not merely discouraged in the prompt. A prompt instruction is a
        # suggestion to a model; this is a rule.
        log_refusal("in-chat booking is not permitted for this tenant", booking_mode=mode)
        return tool_response(
            message=(
                "Your company completes bookings on its own checkout page rather than in chat. "
                "The prepared summary has the link — everything is held and ready."
            ),
            provenance={
                "source": "booking_confirm",
                "tenant_id": context.tenant_id,
                "booking_mode": mode,
            },
        )

    try:
        reservation = post(
            backend_url(), "/v1/booking/confirm", context, body={"offer_id": booking_ref}
        )
    except BackendError as error:
        detail = _detail(error)
        if error.status == 409 and isinstance(detail, dict) and detail.get("current_price"):
            # **A moved fare is a refusal with both numbers**, never a silent re-price. The
            # traveller agreed to a specific amount; charging a different one is not a smaller
            # version of that agreement.
            log_refusal(
                "fare moved before confirmation",
                previous=detail.get("previous_price"),
                current=detail.get("current_price"),
            )
            return tool_response(
                message=(
                    f"The price changed before I could book it — it was "
                    f"{detail.get('previous_price')} and is now {detail.get('current_price')}. "
                    "I haven't booked anything. Shall I go ahead at the new price?"
                ),
                facts={
                    "previous_price": detail.get("previous_price"),
                    "current_price": detail.get("current_price"),
                    "booked": False,
                },
                provenance={"source": "booking_confirm", "tenant_id": context.tenant_id},
            )
        if error.status in (404, 409, 410):
            log_refusal("offer could not be confirmed", status=error.status)
            # **A 409 no longer means "you already booked this".** The backend answers a repeated
            # confirmation with the reservation it already created — `booking_ref` derives from the
            # offer, so a retry is recognisable — which is the case that used to land here and get
            # told "nothing has been charged" while the charge had gone through. What reaches this
            # branch now is a hold that is genuinely spent or gone with no reservation behind it, so
            # the claim is true again.
            #
            # Still hedged rather than asserted, because a status code alone does not say *why*, and
            # the expensive mistake in this direction is telling someone their money is safe when it
            # is not.
            return tool_response(
                message=(
                    "That hold is no longer valid — it may have expired, or the option was taken. "
                    "I have not booked anything on it. Let me search again."
                ),
                facts={"booked": False},
                provenance={"source": "booking_confirm", "tenant_id": context.tenant_id},
            )
        raise

    total = _money((reservation or {}).get("total"))
    confirmation = (reservation or {}).get("confirmation_number") or ""

    log_decision(
        "confirmed a booking",
        booking_ref=booking_ref,
        confirmation_number=confirmation,
        kind=(reservation or {}).get("kind"),
    )

    return tool_response(
        cards=[
            card(
                CardType.BOOKING_CONFIRMED,
                confirmation,
                {
                    "confirmation_number": confirmation,
                    "items": [
                        {
                            "type": (reservation or {}).get("kind"),
                            "label": (reservation or {}).get("description"),
                            "price": total,
                        }
                    ],
                    "total": total,
                    "issued_at": (reservation or {}).get("issued_at"),
                    # When the travel happens, so the frontend can offer a calendar download without
                    # asking the agent for anything. `issued_at` is the booking moment and would put
                    # the entry on today's date.
                    "starts_on": (reservation or {}).get("starts_on"),
                },
                # **No actions on this card, and that is the honest shape.**
                #
                # Both buttons that used to be here asked the *agent* to do something no tool
                # implements, and they failed in the two different ways that mistake can fail.
                #
                # `add_to_calendar` was keyed on a `trip_id` the confirm path never sets, so the BFF
                # refused every click outright ("needs a trip_id and none was supplied") — a visibly
                # broken button. `email_confirmation` was worse precisely because it *worked* as far
                # as
                # the registry was concerned: keyed on a real `booking_ref`, the click resolved into
                # a
                # sentence and reached a model with no email tool, leaving it to improvise about
                # something it had not done.
                #
                # A calendar entry is **browser work** — an `.ics` download needs no agent, no tool
                # and
                # no turn, and it cannot expire. So the frontend owns it (`CardView`'s
                # `booking_confirmed` case) and the card carries no action for it. The reply already
                # tells the traveller a confirmation has been emailed, so the second button was
                # promising a second time what the first sentence already said.
                [],
            )
        ],
        facts={
            "booked": True,
            "confirmation_number": confirmation,
            "booking_ref": (reservation or {}).get("booking_ref"),
            "total": total,
        },
        provenance={
            "source": "booking_confirm",
            "tenant_id": context.tenant_id,
            "price_source": "re-derived server-side at confirmation",
        },
    )


def cancel_reservation(arguments: dict[str, Any], context: RequestContext) -> dict[str, Any]:
    """Two-stage cancellation: terms first, then — separately — the cancellation."""
    booking_ref = (arguments.get("booking_ref") or "").strip()
    if not booking_ref:
        raise ToolError("I need the booking reference of the reservation to cancel.")
    confirmed = bool(arguments.get("confirm"))

    try:
        terms = get(
            backend_url(), f"/v1/booking/reservations/{booking_ref}/cancellation-terms", context
        )
    except BackendError as error:
        if error.status == 404:
            return tool_response(
                message="I couldn't find a booking with that reference.",
                provenance={"source": "cancellation", "tenant_id": context.tenant_id},
            )
        raise

    penalties = [
        {
            "item": penalty.get("item"),
            "penalty": _money(penalty.get("amount")),
            "deadline": penalty.get("deadline"),
        }
        for penalty in (terms or {}).get("penalties") or []
    ]

    if not confirmed:
        # **Stage one cancels nothing.** The terms are shown and the traveller decides. This is the
        # whole reason the tool has two stages rather than a single destructive call.
        log_decision("showed cancellation terms", booking_ref=booking_ref, penalties=len(penalties))
        return tool_response(
            cards=[
                card(
                    CardType.CANCELLATION,
                    booking_ref,
                    {
                        "booking_label": (terms or {}).get("description") or booking_ref,
                        "terms": penalties,
                        "refund_estimate": _money((terms or {}).get("refund_estimate")),
                        "stage": "terms_shown",
                    },
                    [
                        action(Action.CONFIRM_CANCEL, "Cancel booking", booking_ref=booking_ref),
                        action(Action.KEEP_BOOKING, "Keep booking"),
                    ],
                )
            ],
            facts={
                "cancelled": False,
                "fully_refundable": (terms or {}).get("fully_refundable"),
                "penalties": penalties,
                "refund_estimate": _money((terms or {}).get("refund_estimate")),
            },
            provenance={
                "source": "cancellation_terms",
                "tenant_id": context.tenant_id,
                "stage": "terms_shown",
            },
        )

    try:
        cancelled = post(backend_url(), f"/v1/booking/reservations/{booking_ref}/cancel", context)
    except BackendError as error:
        if error.status in (404, 409):
            return tool_response(
                message="That booking can't be cancelled — it may already have been.",
                facts={"cancelled": False},
                provenance={"source": "cancellation", "tenant_id": context.tenant_id},
            )
        raise

    log_decision("cancelled a reservation", booking_ref=booking_ref)

    return tool_response(
        cards=[
            card(
                CardType.CANCELLATION,
                booking_ref,
                {
                    "booking_label": (cancelled or {}).get("description") or booking_ref,
                    "terms": penalties,
                    "refund_estimate": _money((terms or {}).get("refund_estimate")),
                    "stage": "cancelled",
                },
            )
        ],
        facts={"cancelled": True, "status": (cancelled or {}).get("status")},
        provenance={
            "source": "cancellation",
            "tenant_id": context.tenant_id,
            "stage": "cancelled",
        },
    )


TOOLS = {
    PREPARE_BOOKING: prepare_booking,
    CONFIRM_BOOKING: confirm_booking,
    CANCEL_RESERVATION: cancel_reservation,
}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Gateway target entry point. All the shared work lives in `dispatch`."""
    return dispatch(event, context, TOOLS)
