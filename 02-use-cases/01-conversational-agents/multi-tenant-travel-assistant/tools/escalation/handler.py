"""`escalate_to_human` — the handoff, and the context that makes it worth having.

**The context package is the product.** "Connects to a human" is the easy part; what decides whether
the handoff was worth anything is *what the human agent sees on pickup*. A traveller who has spent
five minutes explaining a problem and then hears "hello, how can I help?" has been made to start
over — which is worse than never offering a human at all, because it wasted their time twice.

So this tool assembles: who they are, which trip, what they were trying to do, what has already been
attempted, and their current trip state. The human agent opens the right record before they speak.

**The transport is deliberately not implemented, and that is the extension point.** This tool ends
by logging the assembled package as a structured decision line. Delivering it to a queue is one call
in one place — everything above it (which queue, what context, when to refuse) is already done, and
is the part that carries the design.

Where that call goes is a customer decision, not ours:

* **Amazon Connect** — `StartTaskContact` with the package as contact attributes, so the task
  arrives in `support_queue` with the record already attached. Needs `connect:StartTaskContact` on
  this function's role, and a Connect instance.
* **Genesys, Salesforce Service Cloud, ServiceNow, Zendesk** — an authenticated HTTP call to create
  a work item. The package is already a flat JSON object for exactly this reason.
* **A queue you own** — SQS or EventBridge, if the contact centre is somewhere this account cannot
  reach directly.

**Shipping it as a stub is a deliberate choice, not an unfinished one.** Binding to Connect would
make a reader's deploy depend on a Connect instance they may not have, and would make the sample
look like it is *about* Connect — when the transferable idea is the context package and the refusal
rules.
The log line is a real handoff record: it carries `session_id`, so a transcript and the cost ledger
can both be joined to it.

**The escalation queue comes from the tenant, and its absence is a refusal.** A tenant with no
support queue cannot escalate, and saying "I'm connecting you" into a void is the one failure this
tool must never produce.

**A note on the `reason` field.** It is the only free-text argument in the tool set that reaches a
*human*, which makes it the one place a gateway-side content guardrail would genuinely earn its
keep — abusive text or smuggled PII landing in a human agent's queue is a real harm the model-level
guardrail cannot see (a direct MCP caller bypasses the model entirely). That placement is currently
blocked service-side, so this is an accepted gap rather than an oversight: the reason is
length-capped and logged, and the model-level guardrail covers the conversational path.
"""

from __future__ import annotations

from typing import Any

from shared.cards import CardType, card
from tools.common import (
    BackendError,
    RequestContext,
    ToolError,
    backend_url,
    dispatch,
    get,
    log_decision,
    log_refusal,
    tool_response,
)

from .schemas import ESCALATE_TO_HUMAN

# Long enough for a real explanation, short enough that a runaway generation cannot flood a
# human agent's screen. Truncated rather than refused: a slightly clipped reason still beats no
# handoff.
MAX_REASON_CHARS = 500


def _trip_state(context: RequestContext) -> dict[str, Any]:
    """What the traveller has in flight right now.

    Read here rather than expected as an argument: the model would have to have called `get_trips`
    first and remembered it, and a handoff that degrades because of conversation length is a handoff
    that fails exactly when it is most needed.
    """
    try:
        trips = get(
            backend_url(), "/v1/trips", context, params={"traveler": context.traveler_id or ""}
        )
    except BackendError:
        # A failed lookup must not block the handoff — a thinner package still beats none.
        return {}
    if not isinstance(trips, list):
        return {}

    in_progress = [t for t in trips if t.get("status") == "in_progress"]
    upcoming = [t for t in trips if t.get("status") == "upcoming"]
    state: dict[str, Any] = {"trip_count": len(trips)}
    if in_progress:
        state["currently_travelling"] = {
            "trip_id": in_progress[0].get("trip_id"),
            "label": in_progress[0].get("label"),
            "destination": (in_progress[0].get("destination") or {}).get("city"),
        }
    if upcoming:
        state["next_trip"] = {
            "trip_id": upcoming[0].get("trip_id"),
            "label": upcoming[0].get("label"),
            "starts_on": upcoming[0].get("starts_on"),
        }
    return state


def escalate_to_human(arguments: dict[str, Any], context: RequestContext) -> dict[str, Any]:
    """Hand off to a human agent with the conversation's context attached."""
    reason = (arguments.get("reason") or "").strip()
    if not reason:
        raise ToolError("Before I connect you, I need to tell the human agent what this is about.")
    truncated = len(reason) > MAX_REASON_CHARS
    reason = reason[:MAX_REASON_CHARS]

    try:
        config = get(backend_url(), "/v1/config", context) or {}
    except BackendError:
        config = {}
    queue = config.get("support_queue")

    if not queue:
        # **The failure this tool must never produce is a fake transfer.** No queue means no
        # escalation path, and the traveller needs to know that now rather than after waiting.
        log_refusal("no support queue configured for this tenant")
        return tool_response(
            message=(
                "I can't transfer you to a person from here — your company hasn't set up a travel "
                "desk queue for this assistant. Your internal travel team will be able to help, "
                "and I can summarise everything we've discussed for you to pass on."
            ),
            provenance={"source": "escalation", "tenant_id": context.tenant_id},
        )

    trip_id = (arguments.get("trip_id") or "").strip() or None
    state = _trip_state(context)

    # The package. Assembled here, in code, because a model asked to summarise its own conversation
    # for a handoff will summarise it optimistically — and the agent's first question is always
    # "what has already been tried?".
    package: dict[str, Any] = {
        "tenant_id": context.tenant_id,
        "traveler_id": context.traveler_id,
        "traveler_role": context.role,
        "reason": reason,
        "queue": queue,
        "trip_id": trip_id,
        "trip_state": state,
        # The conversation id, so the agent's own tooling can pull the transcript and the ledger can
        # be joined to the handoff. Same dimension as the audit trail — one name per dimension.
        "session_id": context.session_id,
    }
    if truncated:
        package["reason_truncated"] = True

    # **This is the extension point.** One call here delivers `package` to a contact centre —
    # Connect's `StartTaskContact`, a Genesys or ServiceNow work item, or an SQS message. See the
    # module docstring for why the sample stops short of choosing one.
    #
    # Without it the log line *is* the handoff record, and a real one: it carries `session_id`, so
    # the transcript and the cost ledger both join to it.
    log_decision("escalated to a human", **package)

    summary_line = f"{context.role or 'Traveller'} needs help: {reason}"
    if state.get("currently_travelling"):
        summary_line += f" (currently in {state['currently_travelling'].get('destination')})"

    return tool_response(
        cards=[
            card(
                CardType.ESCALATION,
                f"escalation-{context.session_id or 'session'}",
                {
                    # **`prepared`, not `queued`, because nothing was queued.** The package is
                    # assembled and logged; delivery is the extension point above. `queued` read
                    # as a completed transfer, and the card rendered a success badge titled "Handed
                    # to a travel consultant" — a claim on the traveller's screen the code does not
                    # support. This module says at line 120 that a fake transfer is the one failure
                    # it must never produce; the rule was written down and the UI broke it anyway.
                    #
                    # **Whoever wires a real transport changes this string too.** That is why it
                    # is a value rather than a label hardcoded in the frontend: one edit at the
                    # delivery site, one here, and the UI follows.
                    "status": "prepared",
                    "reason_label": reason,
                    "context_summary_line": summary_line,
                    "queue_note": (
                        "Your travel desk will have everything we've discussed, including your "
                        "current trip details."
                    ),
                },
                # No actions — the handoff *is* the action. A button here would imply the traveller
                # still has something to do.
            )
        ],
        facts={
            "escalated": True,
            "queue": queue,
            # So the model tells the traveller what was sent rather than implying it started over.
            "context_included": sorted(k for k, v in package.items() if v),
        },
        provenance={
            "source": "escalation",
            "tenant_id": context.tenant_id,
            "traveler_id": context.traveler_id,
            "transport": "logged context package; Connect integration is optional at deploy",
        },
    )


TOOLS = {ESCALATE_TO_HUMAN: escalate_to_human}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Gateway target entry point. All the shared work lives in `dispatch`."""
    return dispatch(event, context, TOOLS)
