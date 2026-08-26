"""Stop the agent claiming an action happened when no tool made it happen.

**The failure this exists for, measured rather than imagined.** Asked *"yes, confirm it"* after a
prepared booking, the deployed agent replied *"Your flight is confirmed. Aer Lingus EI 631… $557.75
charged to your corporate Visa. You'll receive a confirmation email shortly"* — and called **no tool at
all**. Nothing was booked, nothing was charged, no reservation exists. Across six consecutive runs the
booking tool ran **zero** times and four of the six answers claimed success anyway.

**The same shape recurred on the escalation path, found in the same browser sweep that redeployed the
SigV4 fix.** Asked *"I'd rather talk to a person about this"*, the agent answered *"I'm connecting you
to a human agent now"* — and `escalate_to_human` was never invoked; confirmed against CloudWatch, which
showed no log stream for the tool in that window. No card, no context package, no queue notified. A
traveller told "someone is coming" who is not is arguably worse than a traveller told a booking
succeeded that did not, because there is no card on screen inviting a second look — the sentence is the
whole of what they were given, and it reads as complete. So `HumanHandoffGuard` below applies the exact
same defence to the exact same failure: a completion claim is checked against a structural signal, not
trusted from the prose that made it.

**Why prompting did not fix it.** `writes.j2` already says *"never say something has been done unless a
tool did it in this turn"*, in those words. Four successive attempts to strengthen it — naming the
handle format, adding counter-examples, restating the rule beside the cue — moved the number between
0/6 and 3/5 and once made it strictly worse (a version scoring 3/3 dropped to 0/3, one run of which
fabricated a confirmation). A prompt is a request. This is a check.

**Why not force the tool instead.** A *clicked* confirm already forces it (`tool_choice.py`), which is
why the click path books reliably. Forcing on typed agreement would mean inferring "yes" from free text
on the write path, where a false positive books something the traveller never agreed to. Refusing to
*lie* is the smaller, safer control: it never books anything, it only declines to claim.

**The defect is channel-independent, which is why the guard sits here rather than in the interface.**
It is a claim the *model* makes, so anything that renders the model's prose inherits it — a chat
transcript, an exported conversation, an emailed summary. Putting the check at the stream means every
consumer is covered by construction instead of each one re-implementing it.

## How it works, and why the text is held back

`stream_async` emits prose as it is generated, so a claim cannot be retracted once it has been sent —
the traveller has already read it. So a short suffix remains **unemitted** while it might still become
a split completion claim, and a detected claim remains held until a successful matching tool result
proves it true or the turn ends and it is rewritten.

The cost is deliberate and bounded: ordinary prose trails the model by at most `LOOKBEHIND` characters,
while a possible completion claim waits until its outcome is known. No text is both retained and
emitted — that invariant prevents a later tool result from duplicating prose already on screen.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Literal

log = logging.getLogger("travel.unclaimed")

ClaimKind = Literal["booking", "cancellation"]
LOOKBEHIND = 80


def _word_boundary(pending: str, target: int) -> int:
    """The nearest release point at or before `target` that does not split a word.

    **Found live, not in a test.** Both guards below release `pending[:-LOOKBEHIND]` on every chunk
    that carries no claim, and a slice on a raw character count has no idea where a word ends. Asked
    about business class to Singapore, the transcript read *"I'll check your travel policy to see
    if yo"* / *"u're eligible..."* — two `<p>` elements, split inside "you're", because 80 characters
    from the end of that chunk landed between "yo" and "u're". Nothing here is a claim; `LOOKBEHIND`
    exists only so a claim spanning a chunk boundary is never released half-emitted, and that
    purpose is served exactly as well by releasing up to the word before the cutoff as by releasing
    up to the cutoff itself.

    Walks back from `target` to the previous whitespace rather than forward, because forward would
    grow the safety margin as a token straddles the boundary — the one case `LOOKBEHIND` is sized
    for. If no whitespace exists yet (one long unbroken token), returns 0: nothing new is releasable
    without cutting it, so the text stays pending one chunk longer, which only delays a release —
    the same trade-off the docstring above already accepts for an unresolved claim.
    """
    if target <= 0:
        return 0
    if target >= len(pending):
        return len(pending)
    boundary = pending.rfind(" ", 0, target)
    return boundary + 1 if boundary != -1 else 0


_BOOKING_CLAIMED = re.compile(
    r"""
    \b(?:
        (?:(?:your|the|this|that)\s+)?(?:flight|hotel|booking|reservation|trip)\s+
        (?:is|are|has\s+been|have\s+been|was|were)\s+(?:now\s+)?(?:confirmed|booked)
      | (?:i(?:'ve|\s+have)\s+(?:now\s+)?(?:confirmed|booked))
      | (?:booking|reservation)\s+(?:is\s+)?complete
      | (?:you(?:'re|\s+are)\s+(?:all\s+)?booked)
      # Named, and kept separate from the branch above, because it is the one ambiguous phrase in
      # this pattern — see `_BOOKING_NOUN` immediately below.
      | (?P<all_set>you(?:'re|\s+are)\s+(?:all\s+)?set)
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# **"You're all set" is not booking vocabulary on its own, and treating it as such produced a
# nonsensical reply.** Guiding the escalation path to say "I'll connect you" surfaced *"You're all
# set. Your travel desk will have everything we've discussed..."* — a sentence about a human handoff,
# not a booking, and `_BOOKING_CLAIMED` matched it anyway. Kept rather than dropped, because "You're
# all set — the flight is booked" is a real claim a fixture already asserts. So `all_set` — the one
# named group above — only counts as a booking claim when a booking noun also appears in the same
# sentence; checked in `completion_claim`, the one place that already has the sentence in hand.
_BOOKING_NOUN = re.compile(r"\b(?:flight|hotel|booking|reservation|trip)\b", re.IGNORECASE)

_CANCELLATION_CLAIMED = re.compile(
    r"""
    \b(?:
        (?:(?:your|the|this|that)\s+)?(?:flight|hotel|booking|reservation|trip)\s+
        (?:is|are|has\s+been|have\s+been|was|were)\s+(?:now\s+)?(?:cancelled|canceled)
      | (?:i(?:'ve|\s+have)\s+(?:now\s+)?(?:cancelled|canceled))
      | cancellation\s+(?:is\s+)?complete
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

_NEGATED: dict[ClaimKind, re.Pattern[str]] = {
    "booking": re.compile(
        r"\b(?:nothing|not|isn't|is\s+not|hasn't|has\s+not|haven't|no)\b[^.!?]{0,40}"
        r"\b(?:confirmed|booked)\b",
        re.IGNORECASE,
    ),
    "cancellation": re.compile(
        r"\b(?:nothing|not|isn't|is\s+not|hasn't|has\s+not|haven't|no)\b[^.!?]{0,40}"
        r"\b(?:cancelled|canceled)\b",
        re.IGNORECASE,
    ),
}

_CLAIM_PATTERNS: dict[ClaimKind, re.Pattern[str]] = {
    "booking": _BOOKING_CLAIMED,
    "cancellation": _CANCELLATION_CLAIMED,
}

# **A report of stored state is not a claim about this turn**, and conflating the two produced a
# visible defect on the likeliest first prompt in the sample. Asked "tell me about my Singapore trip",
# the agent said *"The outbound flight is booked"* — true, retrieved by `get_trips` — and the guard
# replaced it with *"I have not booked anything yet … tap Confirm booking on the card"*, naming a
# button that only appears on a booking summary. A correct statement became an incorrect one.
#
# Subtracted the same way negations are, rather than by licensing claims on a read tool's result: a
# read proves nothing about a write, and using one to unlock the other would weaken the control on the
# path that moves money to fix a wording problem on the path that does not.
#
# Deliberately narrow. These are *framing* phrases — the sentence attributes the state to a record
# rather than to the agent's own action. "I have booked" and "your booking is confirmed" carry no such
# frame and still match.
_REPORTED = re.compile(
    r"""
    \b(?:
        (?:trip|itinerary|booking|reservation|record|records|file)\s+shows
      | shows\s+(?:that\s+)?you
      | (?:you|it)\s+(?:already\s+)?have\s+(?:your|a|an|the)\b
      | according\s+to
      | on\s+file
      | (?:is|are)\s+on\s+record
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

BOOKING_REPLACEMENT = (
    "I have not booked anything yet — the summary above is a hold, not a booking. "
    "Tap **Confirm booking** on the card and I will book it straight away."
)

# **The same correction without the instruction, for when there is no button to press.**
#
# `BOOKING_REPLACEMENT` directs the traveller to a control that exists only on a booking summary. A
# claim can be suppressed when no hold was prepared this turn — a bare "the outbound flight is booked"
# about an existing trip carries no reporting frame, so `_REPORTED` cannot tell it from a claim — and
# in that case the instruction named a button that was not on screen. Correcting a true statement is
# bad; correcting it by pointing at something that does not exist is worse.
#
# This wording is accurate in both remaining cases: a model that invented a booking has indeed booked
# nothing, and a model reporting a stored booking did not make it in this conversation either.
BOOKING_REPLACEMENT_NO_HOLD = (
    "I have not booked anything in this conversation, and nothing has been charged. "
    "Tell me what you would like to book and I will prepare it for you to confirm."
)

CANCELLATION_REPLACEMENT = (
    "I have not cancelled the booking. Review the cancellation terms on the card, then tap "
    "**Cancel booking** if you still want to continue."
)

REPLACEMENTS: dict[ClaimKind, str] = {
    "booking": BOOKING_REPLACEMENT,
    "cancellation": CANCELLATION_REPLACEMENT,
}

_SUCCESS_FACTS: dict[str, tuple[ClaimKind, str]] = {
    "confirm_booking": ("booking", "booked"),
    "cancel_reservation": ("cancellation", "cancelled"),
}


@dataclass(frozen=True)
class CompletionClaim:
    kind: ClaimKind
    start: int
    end: int


def _sentence_start(text: str, index: int) -> int:
    """Where the sentence containing `index` begins.

    **Held text has to start at a sentence boundary, or a replacement splices.** A claim rarely opens
    its own sentence — "The outbound flight is booked" matches at "flight", so releasing everything
    before the match emits "The outbound " and the substituted statement lands on the end of it:
    *"The outbound I have not booked anything yet"*. Seen in a browser; the API checks never render
    prose, so nothing else would have caught it.
    """
    boundary = max(text.rfind(mark, 0, index) for mark in ".!?")
    start = 0 if boundary < 0 else boundary + 1
    while start < index and text[start].isspace():
        start += 1
    return start


def _sentence_containing(text: str, index: int) -> str:
    """The sentence around `index`, used to subtract negated completion phrases."""
    left = max(text.rfind(mark, 0, index) for mark in ".!?")
    rights = [position for mark in ".!?" if (position := text.find(mark, index)) >= 0]
    right = min(rights) + 1 if rights else len(text)
    return text[left + 1 : right]


def completion_claim(text: str) -> CompletionClaim | None:
    """The earliest claim of a completed action, ignoring negations and reports of stored state."""
    found: list[CompletionClaim] = []
    for kind, pattern in _CLAIM_PATTERNS.items():
        for match in pattern.finditer(text or ""):
            sentence = _sentence_containing(text, match.start())
            # Both subtractions read the whole sentence, because that is the unit carrying the
            # negation or the reporting frame — the matched phrase alone cannot show either.
            if _NEGATED[kind].search(sentence) or _REPORTED.search(sentence):
                continue
            # "You're all set" alone says nothing about a booking — see `_BOOKING_NOUN`.
            if match.groupdict().get("all_set") and not _BOOKING_NOUN.search(sentence):
                continue
            found.append(CompletionClaim(kind, match.start(), match.end()))
            break
    return min(found, key=lambda claim: claim.start) if found else None


def claims_completion(text: str) -> bool:
    """Whether this prose asserts that a booking or cancellation has already happened.

    Offers and questions are not claims: *"shall I confirm?"*, *"tap confirm and I'll book it"* and
    *"I can cancel that"* all pass through untouched, because they are exactly what the agent should say
    when no tool has run.
    """
    return completion_claim(text) is not None


class ClaimGuard:
    """Holds back prose that claims a completed action until the claim is checked.

    Usage per turn: `record_result` for parsed tool-result envelopes, `text` for each chunk (it returns
    what may be sent now), and `flush` at the end (it returns any pending text or a correction).

    **Fails toward truth, not toward activity.** A tool starting, returning transport success, or
    returning cancellation terms proves no state change. Only the matching structured success fact
    licenses a completion claim.
    """

    def __init__(self) -> None:
        self._successful: set[ClaimKind] = set()
        self._pending = ""
        self._claim: CompletionClaim | None = None
        self._rewrote = False
        self._rewritten_kind: ClaimKind | None = None
        # Whether a tool ran since the last prose chunk — see `tool_boundary`.
        self._resumed = False
        # Whether a confirmable hold was prepared this turn, so a correction knows whether the
        # **Confirm booking** control it would name is on screen. Never licenses a claim.
        self._held = False

    @property
    def rewrote(self) -> bool:
        """Whether a false claim was replaced. Logged by the caller as a real defect having occurred."""
        return self._rewrote

    @property
    def rewritten_kind(self) -> ClaimKind | None:
        return self._rewritten_kind

    def tool_boundary(self) -> None:
        """Note that a tool just ran, so the next prose opens a new paragraph.

        **The frontend cannot do this, and that is why it lives here.** The model narrates, calls a
        tool, then resumes with a fresh sentence carrying no leading space — so the two runs need a
        separator. A client can only insert one *between* chunks, and short narration never reaches
        the client as its own chunk: "Let me look that up." is 21 characters, well inside `LOOKBEHIND`,
        so it stays retained until the post-tool text arrives and both leave together in one emission.
        Measured in a browser as *"…trip for you.Your Singapore trip…"*.

        Only the boundary is recorded. The separator is inserted in `text()`, once it can be compared
        against what actually sits on either side of it.
        """
        self._resumed = True

    def record_result(self, name: str, payload: dict[str, Any], *, ok: bool) -> None:
        """Record a successful state change from one parsed tool-result envelope."""
        facts = payload.get("facts") if isinstance(payload, dict) else None
        if not ok or not isinstance(facts, dict):
            return

        # A prepared hold licenses nothing — it is not a booking. It is noted only so a correction
        # can tell whether the confirm button it would point at is actually on screen.
        if name == "prepare_booking" and facts.get("booking_ref"):
            self._held = bool(facts.get("can_confirm_in_chat"))

        expected = _SUCCESS_FACTS.get(name)
        if not expected:
            return
        kind, fact = expected
        if facts.get(fact) is True:
            self._successful.add(kind)

    def _release(self) -> str:
        released = self._pending
        self._pending = ""
        self._claim = None
        return released

    def text(self, chunk: str) -> str:
        """What may be sent now, retaining only text that has never been emitted.

        Once a claim is found, everything from the claim onward stays pending: a claim followed by
        "…and here are the details" must not have its second half arrive without its first.
        """
        # Bridge the gap a tool call leaves, and only that gap: both sides must already lack
        # whitespace, so an ordinary mid-word chunk split is never touched.
        if self._resumed and chunk:
            self._resumed = False
            if self._pending and not self._pending[-1].isspace() and not chunk[0].isspace():
                self._pending += "\n\n"

        self._pending += chunk

        if self._claim:
            if self._claim.kind in self._successful:
                return self._release()
            return ""

        if claim := completion_claim(self._pending):
            # Held from the start of the claim's *sentence*, not from the claim. See
            # `_sentence_start`: releasing up to the match leaves that sentence's opening words on
            # screen for a replacement to be spliced onto.
            boundary = _sentence_start(self._pending, claim.start)
            safe = self._pending[:boundary]
            self._pending = self._pending[boundary:]
            self._claim = CompletionClaim(claim.kind, claim.start - boundary, claim.end - boundary)
            if claim.kind in self._successful:
                return safe + self._release()
            return safe

        safe_length = _word_boundary(self._pending, len(self._pending) - LOOKBEHIND)
        safe = self._pending[:safe_length]
        self._pending = self._pending[safe_length:]
        return safe

    def flush(self) -> str:
        """All remaining text, rewritten only for an unverified completion claim."""
        if not self._claim:
            return self._release()

        if self._claim.kind in self._successful:
            return self._release()

        # **The claim was false, so it is replaced rather than annotated.** Appending a correction
        # would leave both statements on screen and the traveller would have to decide which to
        # believe — and the wrong one is the confident one.
        kind = self._claim.kind
        held = self._pending
        self._pending = ""
        self._claim = None
        self._rewrote = True
        self._rewritten_kind = kind
        log.error(
            "suppressed an unverified %s completion claim: %r",
            kind,
            held[:200],
        )
        if kind == "booking" and not self._held:
            return BOOKING_REPLACEMENT_NO_HOLD
        return REPLACEMENTS[kind]


# --- the human-handoff claim -----------------------------------------------------------------
#
# A second, smaller guard rather than a third `ClaimKind` on the one above. The two differ on the
# signal that licenses a claim: a booking is licensed by a *fact* in a tool result
# (`facts["booked"] is True`), because `confirm_booking` can succeed while returning no card at all.
# A handoff is licensed by a *card* — `main.py` already treats `card_type == "escalation"` as the
# one true signal that a handoff happened, because the tool itself returns a message with no card
# when a tenant has no support queue configured, and that refusal must not count. Reusing
# `ClaimKind`/`_SUCCESS_FACTS` for a fact that does not exist would be the wrong abstraction wearing
# the right name.

_HANDOFF_CLAIMED = re.compile(
    r"""
    \b(?:
        (?:i(?:'m|\s+am)\s+(?:now\s+)?connecting\s+you)
      | (?:connecting\s+you\s+(?:now|to\s+a\s+(?:human|person|(?:travel\s+)?agent)))
      | (?:i(?:'ve|\s+have)\s+(?:now\s+)?(?:connected|transferred)\s+you)
      | (?:you(?:'re|\s+are)\s+(?:now\s+)?(?:connected|being\s+connected|transferred)\s+to)
      | (?:\b(?:human|travel\s+desk|travel\s+consultant)\b[^.!?]{0,40}\bwill\s+be\s+with\s+you\b)
      | (?:i(?:'ve|\s+have)\s+(?:now\s+)?(?:escalated|handed\s+(?:this|you)\s+(?:off|over)))
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# A statement that no handoff happened, or that one is only being offered — subtracted the same way
# `_NEGATED["booking"]` is. "I can't transfer you to a person from here" (the tool's own no-queue
# refusal, relayed verbatim) must never be rewritten into itself.
_HANDOFF_NEGATED = re.compile(
    r"\b(?:not|isn't|is\s+not|hasn't|has\s+not|haven't|can't|cannot|couldn't|unable\s+to)\b"
    r"[^.!?]{0,40}\b(?:connect|transfer|reach|escalat)",
    re.IGNORECASE,
)

# An offer or a question is not a claim: "would you like me to connect you?" and "shall I get
# someone?" are exactly right before the tool has run.
_HANDOFF_OFFERED = re.compile(
    r"\b(?:would\s+you\s+like|shall\s+i|(?:can|should)\s+i|want\s+me\s+to)\b[^.!?]{0,60}"
    r"\b(?:connect|transfer|escalat|get\s+(?:you\s+)?someone)",
    re.IGNORECASE,
)


HANDOFF_REPLACEMENT = (
    "I haven't actually connected you to anyone yet — let me do that properly. "
    "Tell me again what you'd like help with and I'll hand it to your travel desk with the details."
)


class HumanHandoffGuard:
    """Holds back prose that claims a human handoff until an escalation card actually arrives.

    Usage per turn: `note_card` when a tool result's cards are inspected (mirrors `main.py`'s own
    `any(c.get("card_type") == "escalation" ...)` check — same signal, read once), `text` for each
    chunk, and `flush` at the end. The shape is `ClaimGuard`'s on purpose: one reviewer who has
    understood one of these two classes has understood both.
    """

    def __init__(self) -> None:
        self._escalated = False
        self._pending = ""
        self._claim_start: int | None = None
        self.rewrote = False

    def note_card(self, built: list[dict[str, Any]]) -> None:
        """Record that this turn's tool results included a real escalation card."""
        if any(c.get("card_type") == "escalation" for c in built):
            self._escalated = True

    def _find_claim(self, text: str) -> int | None:
        for match in _HANDOFF_CLAIMED.finditer(text):
            sentence = _sentence_containing(text, match.start())
            if _HANDOFF_NEGATED.search(sentence) or _HANDOFF_OFFERED.search(sentence):
                continue
            return match.start()
        return None

    def _release(self) -> str:
        released = self._pending
        self._pending = ""
        self._claim_start = None
        return released

    def text(self, chunk: str) -> str:
        """What may be sent now. Mirrors `ClaimGuard.text` without the tool-boundary bridging,
        which belongs to the write path's narrate-then-call-then-resume shape and has no equivalent
        here: a handoff claim is not preceded by a tool call, it is supposed to be followed by one.
        """
        self._pending += chunk

        if self._claim_start is not None:
            return self._release() if self._escalated else ""

        if (index := self._find_claim(self._pending)) is not None:
            boundary = _sentence_start(self._pending, index)
            safe = self._pending[:boundary]
            self._pending = self._pending[boundary:]
            self._claim_start = index - boundary
            if self._escalated:
                return safe + self._release()
            return safe

        safe_length = _word_boundary(self._pending, len(self._pending) - LOOKBEHIND)
        safe = self._pending[:safe_length]
        self._pending = self._pending[safe_length:]
        return safe

    def flush(self) -> str:
        """All remaining text, rewritten only for a handoff claim with no matching card."""
        if self._claim_start is None or self._escalated:
            return self._release()

        held = self._pending
        self._pending = ""
        self._claim_start = None
        self.rewrote = True
        log.error("suppressed an unverified human-handoff claim: %r", held[:200])
        return HANDOFF_REPLACEMENT
