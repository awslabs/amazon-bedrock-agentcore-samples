"""Card action clicks, replayed as user turns.

**The closed registry is a security boundary, not a convenience.** A card's buttons come from a
tool's response, and a tool's response is shaped by a model. If this API relayed whatever
`action_id` arrived, a prompt-injected model could emit `transfer_funds` and the click would reach
the agent as an instruction. So the set is closed *twice*: the frontend refuses to render an
unknown action, and this refuses to relay one.

**The registry itself is imported from `shared/cards.py`**, the same file the tools construct cards
from and the frontend's types are generated from. A hand-maintained third copy here would be the
one that drifts, and drift means either a dead button or an accepted action nobody vetted.

**A click becomes a sentence, deliberately.** The alternative — a side channel that calls a tool
directly — would give the UI a second way to reach the capability layer, bypassing the guardrail,
the Cedar policy and the conversation history that makes the next turn coherent. One entrance means
one set of controls. The cost is that the model re-derives which tool to call from a phrase, and
that is acceptable because the tool re-validates ownership of whatever handle the phrase names.

**Payloads are echoed into the phrase, never trusted as arguments.** `booking_ref` in a click is
client-supplied and therefore forgeable; it reaches the agent as text, and the write tool re-derives
the booking and re-checks the caller owns it. That is the same "opaque handle out, ownership
re-checked in" rule the rest of the sample follows — a click is not a privileged channel.
"""

from __future__ import annotations

from typing import Any

from shared.cards import Action

# What each click tells the agent to do.
#
# **Short, and naming only the handle — because `FORCED_TOOLS` already guarantees the call.** These
# phrases used to be imperatives naming the tool and insisting on it ("…now by calling the
# preparation tool with this exact reference. I have already chosen it, so do not ask me to
# confirm"), which was persuasion aimed at a model that could decline. Forcing the tool removed the
# choice, so the insistence became redundant — and it was not free: prose written to override a
# model's judgement is what a prompt-attack guardrail is trained to catch, so a legitimate click on
# the traveller's own card could be blocked as an injection attempt.
#
# What survives is what the model cannot get anywhere else: which handle was pressed, and (for the
# two that transact) that the pressed handle wins over anything it remembers.
#
# `{handle}` is filled from the action's payload when it carries one. A phrase with no placeholder
# needs no handle — `keep_booking` is a refusal, and there is nothing to identify.
PHRASES: dict[Action, str] = {
    Action.SELECT_FLIGHT: "Prepare a booking for flight option {handle}.",
    Action.SELECT_HOTEL: "Prepare a booking for hotel option {handle}.",
    Action.VIEW_DETAILS: "Tell me more about property {handle}.",
    Action.VIEW_FARE_RULES: "What are the fare rules for option {handle}?",
    Action.VIEW_TRIP: "Show me trip {handle}.",
    Action.VIEW_TRAVEL_POLICY: "Show me my travel policy.",
    # **The clicked handle is declared authoritative, and that clause is not decoration.** Memory
    # reintroduces a second source: the model's own prose from an earlier turn ("I've prepared
    # booking off_abc") stays in the transcript, and once holds got unique ids that older reference
    # genuinely differs from the one on the button. The model then refused, comparing the click
    # against its own recollection — safe, but wrong, since only the client knows which button was
    # actually pressed.
    #
    # The second sentence guards the other direction: a model that narrates "your booking is
    # confirmed, reference BKG-…" without calling the tool has invented a reference for a booking
    # that never happened.
    Action.CONFIRM_BOOKING: (
        "Confirm booking {handle}. This reference came from the button the traveller pressed, so "
        "it is the correct one even if an earlier reference appears elsewhere in this "
        "conversation. Do not state any confirmation number that the tool did not return."
    ),
    Action.DECLINE_BOOKING: "No, don't book that for now.",
    # Same reasoning as `confirm_booking` — a cancellation is equally unrecoverable, and equally
    # damaging to claim without doing.
    Action.CONFIRM_CANCEL: (
        "Cancel booking {handle}. This reference came from the button the traveller pressed, so it "
        "is the correct one even if an earlier reference appears elsewhere in this conversation. "
        "Do not report it cancelled unless the tool confirms it."
    ),
    Action.KEEP_BOOKING: "No, keep the booking as it is.",
    Action.GET_DIRECTIONS: "How do I get to {handle}?",
}

# **Which tool a click *must* run, when the click leaves no room for judgement.**
#
# Phrasing alone was not enough, and this is why the phrases above can be short. A click asking for
# a hotel to be prepared is answerable with "good choice — shall I prepare it?", which is a
# reasonable reply to what was said and a stall in the middle of a booking: measured at about one
# run in three, with nothing raised and no log looking unusual, because a skipped `prepare_booking`
# is not a *wrong* answer. Wording it more insistently reduced that to zero over four runs but
# remained persuasion the model could decline. **Forcing the tool removes the choice rather than
# discouraging it**, so no future prompt edit or model version can reintroduce the stall.
#
# Names are the **gateway-prefixed** ones (`booking___prepare_booking`, not `prepare_booking`): the
# model
# sees the prefixed name, and Bedrock rejects a `toolChoice` naming a tool that is not in the
# request.
# Verified against `agentcore.json`'s Cedar policy, which lists the same three.
#
# **Only the write path is here, deliberately.** A read click ("tell me more about…") answered with
# a
# question is still a correct answer, so forcing a tool would remove the model's ability to ask a
# clarifying question it legitimately needs. A *write* click answered with a question is a stall.
#
# **This does not weaken any control.** Forcing the tool decides *that* it runs, never *what it
# returns*:
# the tool still re-derives ownership from the handle, re-checks expiry, and reads the tenant's
# `booking_mode`. A confirm whose hold has lapsed still fails — the refusal simply comes from the
# tool
# rather than from the model declining to try. Cedar, the interceptor and the guardrail are
# untouched,
# because the request still goes through the agent.
FORCED_TOOLS: dict[Action, str] = {
    Action.SELECT_FLIGHT: "booking___prepare_booking",
    Action.SELECT_HOTEL: "booking___prepare_booking",
    Action.CONFIRM_BOOKING: "booking___confirm_booking",
    Action.CONFIRM_CANCEL: "booking___cancel_reservation",
}


def forced_tool_for(action_id: str) -> str | None:
    """The tool this click must call, or `None` when the model should choose.

    `None` for reads and for the refusals (`decline_booking`, `keep_booking`), where there is no
    tool to
    run and forcing one would be actively wrong.
    """
    try:
        return FORCED_TOOLS.get(Action(action_id))
    except ValueError:
        # Unregistered actions are refused by `phrase_for`, which is the one place that decision
        # belongs.
        return None


# Which payload key carries the handle for each action, matching what the tools actually put there.
# Named per action rather than "whatever the first key is", so a tool that starts sending an extra
# field cannot change which value ends up in the sentence.
HANDLE_KEYS: dict[Action, str] = {
    Action.SELECT_FLIGHT: "option_id",
    Action.SELECT_HOTEL: "option_id",
    Action.VIEW_DETAILS: "hotel_id",
    Action.VIEW_FARE_RULES: "option_id",
    Action.VIEW_TRIP: "trip_id",
    Action.CONFIRM_BOOKING: "booking_ref",
    Action.CONFIRM_CANCEL: "booking_ref",
    Action.GET_DIRECTIONS: "name",
}

# A handle reaches the model inside a sentence, so it has to be a *handle* — an opaque id, not
# arbitrary text. Bounded and character-restricted because the alternative is a click that can
# carry a paragraph of model-directed instructions into the next turn: prompt injection with the
# UI as the delivery vehicle.
MAX_HANDLE = 80
_ALLOWED_EXTRA = {"-", "_", ".", " ", ",", "'"}


class UnknownAction(ValueError):
    """The action is not in the closed registry. Refused, never relayed."""


def _clean_handle(value: Any) -> str:
    """A payload value reduced to something safe to put in a sentence.

    Not escaping — *filtering*. Escaping implies a syntax to escape for, and a prompt has none;
    the only defensible position is that a handle looks like a handle. Anything else is dropped
    rather than sanitised, because a partially-cleaned instruction is still an instruction.
    """
    text = str(value or "").strip()[:MAX_HANDLE]
    return "".join(c for c in text if c.isalnum() or c in _ALLOWED_EXTRA).strip()


def phrase_for(action_id: str, payload: dict[str, Any] | None = None) -> str:
    """Turn a click into the user turn it stands for. Raises `UnknownAction` if unregistered.

    `GET_DIRECTIONS` is the one action whose handle is a place name rather than an id, which is why
    the filter allows spaces and apostrophes — "O'Hare Terminal 3" has to survive.
    """
    try:
        action = Action(action_id)
    except ValueError:
        raise UnknownAction(f"{action_id!r} is not a known action") from None

    template = PHRASES[action]
    if "{handle}" not in template:
        return template

    handle = _clean_handle((payload or {}).get(HANDLE_KEYS[action]))
    if not handle:
        # The action needs a handle and the click carried none, so relaying it would produce a
        # sentence with a hole in it — which the model would fill by guessing. Refuse instead.
        raise UnknownAction(f"{action_id} needs a {HANDLE_KEYS[action]} and none was supplied")
    return template.format(handle=handle)


# Every registered action must have a phrase, and every phrase needing a handle must name its key.
# Checked at import so a new member of `Action` fails on the first request after deploy rather than
# on the first *click*, which could be days later and will be in front of someone.
_missing_phrases = [str(member) for member in Action if member not in PHRASES]
if _missing_phrases:
    raise RuntimeError(f"actions with no phrase: {_missing_phrases}")

_missing_keys = [
    str(member)
    for member, template in PHRASES.items()
    if "{handle}" in template and member not in HANDLE_KEYS
]
if _missing_keys:
    raise RuntimeError(
        f"actions whose phrase needs a handle but name no payload key: {_missing_keys}"
    )
