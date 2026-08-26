"""The guard that stops the agent claiming a booking it did not make.

Two failure directions, and both matter:

* **A missed claim ships a lie.** The traveller reads "your flight is confirmed", books nothing
else,
  and turns up at the airport without a ticket.
* **A false positive breaks the normal flow.** "Shall I confirm?" and "tap confirm and I'll book it"
  are exactly right with no tool call, and rewriting those would replace a working conversation to
  fix
  a rare defect.

So the offer cases below carry as much weight as the claim cases. Run:

    uv run --with pytest python -m pytest agent/tests/test_unclaimed.py -q
"""

import sys
from pathlib import Path

import pytest

AGENT_DIR = Path(__file__).resolve().parents[1] / "MultiTenantTravel" / "app" / "MultiTenantTravel"
sys.path.insert(0, str(AGENT_DIR))

from unclaimed import (  # noqa: E402
    BOOKING_REPLACEMENT,
    BOOKING_REPLACEMENT_NO_HOLD,
    CANCELLATION_REPLACEMENT,
    HANDOFF_REPLACEMENT,
    LOOKBEHIND,
    ClaimGuard,
    HumanHandoffGuard,
    _word_boundary,
    claims_completion,
)


class TestReportsOfStoredState:
    """A statement attributing a booking to a record is not a claim about this turn.

    All verbatim or near-verbatim from browser runs of "tell me about my Singapore trip", where the
    trip's flight was genuinely booked and retrieved by `get_trips`.
    """

    @pytest.mark.parametrize(
        "text",
        [
            "The trip shows you have your flight booked, but no hotel yet.",
            "Your itinerary shows the hotel is booked.",
            "According to your records the flight is booked.",
            "That trip shows a booked flight and no hotel on file.",
            "You already have a hotel booked for those nights.",
        ],
    )
    def test_a_report_is_not_a_claim(self, text):
        assert not claims_completion(text)

    @pytest.mark.parametrize(
        "text",
        [
            "Your flight is confirmed. Aer Lingus EI 631.",
            "I've confirmed your booking.",
            "I have booked that for you.",
            "Your booking is confirmed and you'll receive an email shortly.",
            "That reservation is now cancelled.",
        ],
    )
    def test_a_claim_without_a_reporting_frame_still_matches(self, text):
        """The exclusion must not swallow the failure the guard exists for."""
        assert claims_completion(text)

    def test_a_bare_statement_of_stored_state_is_still_treated_as_a_claim(self):
        """**The limit of this fix, asserted rather than left for someone to discover.**

        "The outbound flight is booked" carries no frame attributing it to a record, so nothing
        distinguishes it from a claim. It is still suppressed — deliberately, since the
        alternative is releasing a real false claim — and the correction is worded for that case.
        """
        assert claims_completion("The outbound flight is booked.")


class TestDetection:
    @pytest.mark.parametrize(
        "text",
        [
            # Verbatim from live runs — these are what the agent actually said with no tool call.
            "Your flight is confirmed. Aer Lingus EI 631, Dublin to Atlanta on September 15.",
            "Your flight is confirmed. **Aer Lingus EI 631**, economy, $557.75.",
            "Your booking is confirmed and you'll receive a confirmation email shortly.",
            "The booking has been confirmed.",
            "I've confirmed your booking.",
            "I have booked that for you.",
            "That reservation is now cancelled.",
            "Cancellation complete.",
            "Your hotel is booked.",
            "You're all set — the flight is booked.",
            "Booking complete.",
        ],
    )
    def test_a_completion_claim_is_detected(self, text):
        assert claims_completion(text), f"missed a claim: {text!r}"

    @pytest.mark.parametrize(
        "text",
        [
            # **Every one of these is correct to say with no tool call**, and must pass through.
            "Shall I confirm the booking?",
            "Tap Confirm booking on the card and I'll book it straight away.",
            "Would you like me to confirm this now?",
            "I can cancel that for you — shall I show you the penalty first?",
            "Ready to book: Aer Lingus EI 631, $557.75 total. In policy.",
            "Nothing is booked yet. The summary above is a hold.",
            "This will be charged to your Globex corporate Visa once you confirm.",
            "I'll need to confirm before it's booked.",
            "Five flights, one in policy. The cheapest is Aer Lingus EI 631 at $557.75.",
            "Your hotel nightly cap is $250.00 USD.",
            # The honest failure message — must not be mistaken for a claim about a *booking*.
            "That hold is no longer valid. Nothing has been charged.",
            # Verbatim from a live run, after the escalation prompt guidance was added: "all set"
            # with no booking noun anywhere in the sentence is not a claim about a *booking* — it
            # was a sentence about a human handoff, and `HumanHandoffGuard` is what checks that one.
            "You're all set. Your travel desk will have everything we've discussed, "
            "including any trip details, and they'll be with you shortly.",
        ],
    )
    def test_an_offer_or_a_fact_is_not_a_claim(self, text):
        assert not claims_completion(text), f"false positive on: {text!r}"


class TestGuard:
    def test_a_claim_without_a_tool_is_replaced(self):
        """The whole point. No booking tool ran, so the claim never reaches the traveller."""
        guard = ClaimGuard()
        sent = guard.text("Your flight is confirmed. $557.75 charged to your Visa.")
        assert sent == "", "a claim must not stream before it has been checked"
        assert guard.flush() == BOOKING_REPLACEMENT_NO_HOLD
        assert guard.rewrote is True
        assert guard.rewritten_kind == "booking"

    def test_the_same_claim_with_a_successful_result_is_left_alone(self):
        """A real booking makes the sentence true, so it must arrive byte-for-byte."""
        guard = ClaimGuard()
        assert guard.text("Your flight is confirmed.") == ""
        guard.record_result("confirm_booking", {"facts": {"booked": True}}, ok=True)
        # Released on the next chunk, without waiting for the end of the turn.
        released = guard.text(" Reference TRVA9BF6C.")
        assert released == "Your flight is confirmed. Reference TRVA9BF6C."
        assert guard.flush() == ""
        assert guard.rewrote is False

    def test_a_successful_result_after_the_claim_still_counts(self):
        """Order within a turn does not matter — the held claim is released at flush."""
        guard = ClaimGuard()
        assert guard.text("Your booking is confirmed.") == ""
        guard.record_result("confirm_booking", {"facts": {"booked": True}}, ok=True)
        assert guard.flush() == "Your booking is confirmed."
        assert guard.rewrote is False

    def test_a_claim_split_across_chunks_is_caught(self):
        """**The case a naive per-chunk check misses.** Streaming splits mid-phrase.

        "Your flight is" and " confirmed." each match nothing on their own, so a per-chunk test
        would
        pass the lie straight through.
        """
        guard = ClaimGuard()
        chunks = ["Your flight is", " confirmed.", " Enjoy the trip."]
        outputs = [guard.text(chunk) for chunk in chunks]
        assert outputs == ["", "", ""], f"a split claim prefix leaked: {outputs!r}"
        assert guard.flush() == BOOKING_REPLACEMENT_NO_HOLD

    def test_the_rolling_window_catches_a_claim_split_across_four_chunks(self):
        """The look-behind is a rolling suffix, not merely the previous chunk."""
        guard = ClaimGuard()
        prefix = "A safe introductory sentence. " * 5
        chunks = [prefix + "Your ", "flight ", "is ", "confirmed."]
        visible = "".join(guard.text(chunk) for chunk in chunks)
        assert len(prefix) > LOOKBEHIND
        assert visible == prefix
        assert guard.flush() == BOOKING_REPLACEMENT_NO_HOLD

    def test_everything_after_a_claim_is_held_too(self):
        """A claim's second half must not arrive without its first, or the reply is
        truncated."""
        guard = ClaimGuard()
        guard.text("Your flight is confirmed.")
        assert guard.text(" You'll get an email shortly.") == ""
        assert guard.flush() == BOOKING_REPLACEMENT_NO_HOLD

    def test_ordinary_prose_is_byte_identical_after_flush(self):
        """The common case may trail by 80 characters but cannot change or lose text."""
        guard = ClaimGuard()
        chunks = [
            "Five flights, ",
            "one in policy. ",
            "The cheapest is Aer Lingus EI 631 at $557.75. ",
            "Shall I prepare it?",
        ]
        visible = "".join(guard.text(chunk) for chunk in chunks) + guard.flush()
        assert visible == "".join(chunks)
        assert guard.rewrote is False

    def test_the_rolling_window_never_splits_a_word(self):
        """**Measured live**, not hypothesised. Asked about business class to Singapore, the
        transcript read as two `<p>` elements: "I'll check your travel policy to see if yo" /
        "u're eligible on your Singapore trip." — split inside "you're" because a raw
        `len(pending) - LOOKBEHIND` slice does not know where a word ends. No claim is present
        anywhere in this prose; the release point must still land on whitespace.
        """
        guard = ClaimGuard()
        chunks = [
            "I'll check your travel policy to see if yo",
            "u're eligible for business class on your Singapore trip.",
        ]
        visible = "".join(guard.text(chunk) for chunk in chunks) + guard.flush()
        assert visible == "".join(chunks)
        for released in (guard.text(chunk) for chunk in chunks):
            # Every non-empty release ends at a word boundary: either the very end of what has
            # arrived so far, or immediately after a space.
            assert released == "" or released[-1].isspace() or released == visible[: len(released)]

    def test_a_release_point_never_lands_inside_a_word(self):
        """Direct check on many chunk shapes, not just the one browser measurement above."""
        guard = ClaimGuard()
        pending_before = ""
        released_so_far = ""
        # A long run of short chunks forces many rolling-window releases, each one a chance for
        # the old fixed-offset slice to land mid-word.
        words = ("Good news, I found your Singapore trip. " * 6).split(" ")
        for i in range(0, len(words), 2):
            chunk = " ".join(words[i : i + 2]) + " "
            released = guard.text(chunk)
            released_so_far += released
            pending_before += chunk
            if released:
                # The character immediately after the release is never a lowercase continuation
                # of the word the release ended on — i.e. the release did not end mid-token.
                assert released[-1].isspace() or len(released) == len(pending_before)
        released_so_far += guard.flush()
        assert released_so_far == pending_before


class TestWordBoundary:
    """`_word_boundary` in isolation — the helper both guards' rolling window now uses."""

    def test_backs_off_to_the_previous_space(self):
        assert _word_boundary("I'll check your travel policy to see if you're eligible", 44) == 40

    def test_returns_the_target_unchanged_when_it_already_sits_on_a_boundary(self):
        assert _word_boundary("one two three", 8) == 8

    def test_returns_zero_when_no_space_precedes_the_target(self):
        # One long unbroken token: nothing is releasable without cutting it, so nothing releases.
        assert _word_boundary("supercalifragilisticexpialidocious", 10) == 0

    def test_clamps_a_non_positive_target_to_zero(self):
        assert _word_boundary("anything", -5) == 0

    def test_clamps_a_target_past_the_end_to_the_full_length(self):
        assert _word_boundary("short", 999) == 5

    def test_already_streamed_text_is_not_duplicated_after_success(self):
        """Retained look-behind contains only text that has never been sent."""
        guard = ClaimGuard()
        prefix = "I will handle that carefully. " * 6
        first = guard.text(prefix)
        guard.record_result("confirm_booking", {"facts": {"booked": True}}, ok=True)
        second = guard.text("Your booking is confirmed.")
        assert first + second + guard.flush() == prefix + "Your booking is confirmed."

    def test_safe_text_before_a_false_claim_is_preserved_once(self):
        guard = ClaimGuard()
        visible = guard.text("Okay. Your booking is confirmed.")
        assert visible == "Okay. "
        assert guard.flush() == BOOKING_REPLACEMENT_NO_HOLD

    def test_a_correction_names_the_confirm_button_only_when_a_hold_exists(self):
        """The instruction points at a control that only a booking summary carries.

        A claim can be suppressed on a turn where nothing was prepared — a bare "the outbound
        flight is booked" about an existing trip reads exactly like a claim — and the correction
        then named a button that was not on screen.
        """
        guard = ClaimGuard()
        guard.text("The outbound flight is booked.")
        assert guard.flush() == BOOKING_REPLACEMENT_NO_HOLD

        prepared = ClaimGuard()
        prepared.record_result(
            "prepare_booking",
            {"facts": {"booking_ref": "off_abc", "can_confirm_in_chat": True}},
            ok=True,
        )
        prepared.text("Your booking is confirmed.")
        assert prepared.flush() == BOOKING_REPLACEMENT

    def test_a_prepared_hold_does_not_license_a_booking_claim(self):
        """A hold is not a booking, so noting it must not unlock the claim it sits next to."""
        guard = ClaimGuard()
        guard.record_result(
            "prepare_booking",
            {"facts": {"booking_ref": "off_abc", "can_confirm_in_chat": True}},
            ok=True,
        )
        guard.text("Your flight is confirmed.")
        assert guard.flush() == BOOKING_REPLACEMENT
        assert guard.rewrote

    def test_a_tool_boundary_separates_the_prose_either_side_of_it(self):
        """Short narration is retained as look-behind, so both runs leave in one emission.

        Verbatim from a browser run: *"…for you.Your Singapore trip…"*. The client cannot
        the break, because it never receives the two runs as separate chunks.

        **Asserted on everything emitted, not on `flush()` alone.** The first version of this test
        checked only the flush and passed while the separator was landing in a `text()` return — a
        test that could not observe what it claimed to.
        """
        guard = ClaimGuard()
        emitted = [guard.text("Let me get the details on that Singapore trip for you.")]
        assert emitted == [""], "short narration should still be retained as look-behind"
        guard.tool_boundary()
        emitted.append(guard.text("Your Singapore trip runs from November 3rd."))
        emitted.append(guard.flush())
        whole = "".join(emitted)
        assert "for you.Your" not in whole
        assert "for you.\n\nYour" in whole

    def test_a_replacement_does_not_splice_onto_its_sentence_opening(self):
        """A claim rarely starts its own sentence, and the words before it must not be emitted.

        Verbatim from a browser run: the agent said "The outbound flight is booked", the match began
        at "flight", and releasing everything before it put *"The outbound I have not booked
        anything yet"* on screen. The API suites never render prose, so only a browser saw it.
        """
        guard = ClaimGuard()
        visible = guard.text(
            "You're flying Singapore Airlines flight 35 from Chicago O'Hare to Singapore. "
            "The outbound flight is booked."
        )
        assert visible.endswith("to Singapore. ")
        assert "The outbound" not in visible
        assert guard.flush() == BOOKING_REPLACEMENT_NO_HOLD

    def test_a_cancellation_claim_needs_a_successful_cancellation(self):
        guard = ClaimGuard()
        guard.text("That reservation is now cancelled.")
        guard.record_result("cancel_reservation", {"facts": {"cancelled": False}}, ok=True)
        assert guard.flush() == CANCELLATION_REPLACEMENT
        assert guard.rewritten_kind == "cancellation"

        allowed = ClaimGuard()
        allowed.text("That reservation is now cancelled.")
        allowed.record_result("cancel_reservation", {"facts": {"cancelled": True}}, ok=True)
        assert allowed.flush() == "That reservation is now cancelled."

    def test_a_transport_error_does_not_license_a_claim(self):
        guard = ClaimGuard()
        guard.text("Your booking is confirmed.")
        guard.record_result("confirm_booking", {"facts": {"booked": True}}, ok=False)
        assert guard.flush() == BOOKING_REPLACEMENT_NO_HOLD

    def test_a_clean_tool_refusal_does_not_license_a_claim(self):
        guard = ClaimGuard()
        guard.text("Your booking is confirmed.")
        guard.record_result("confirm_booking", {"facts": {"booked": False}}, ok=True)
        assert guard.flush() == BOOKING_REPLACEMENT_NO_HOLD

    def test_cancellation_terms_do_not_license_a_cancellation_claim(self):
        guard = ClaimGuard()
        guard.text("That reservation is now cancelled.")
        guard.record_result(
            "cancel_reservation",
            {"facts": {"cancelled": False, "fully_refundable": True}},
            ok=True,
        )
        assert guard.flush() == CANCELLATION_REPLACEMENT

    def test_success_for_the_other_action_does_not_license_a_claim(self):
        booking = ClaimGuard()
        booking.text("Your booking is confirmed.")
        booking.record_result("cancel_reservation", {"facts": {"cancelled": True}}, ok=True)
        assert booking.flush() == BOOKING_REPLACEMENT_NO_HOLD

        cancellation = ClaimGuard()
        cancellation.text("That reservation is now cancelled.")
        cancellation.record_result("confirm_booking", {"facts": {"booked": True}}, ok=True)
        assert cancellation.flush() == CANCELLATION_REPLACEMENT

    def test_a_read_or_prepare_result_does_not_license_a_claim(self):
        """Preparing holds a price; neither it nor a read changes booking state."""
        for tool, facts in [
            ("prepare_booking", {"prepared": True}),
            ("get_traveler_profile", {"traveler": "Priya"}),
        ]:
            guard = ClaimGuard()
            guard.text("Your booking is confirmed.")
            guard.record_result(tool, {"facts": facts}, ok=True)
            assert guard.flush() == BOOKING_REPLACEMENT_NO_HOLD

    def test_all_set_with_no_booking_noun_is_not_a_booking_claim(self):
        """Verbatim from a live run. `ClaimGuard` must let this through untouched — it is
        `HumanHandoffGuard`'s sentence, not this guard's, and the two must not fight over it."""
        guard = ClaimGuard()
        sentence = (
            "You're all set. Your travel desk will have everything we've discussed, "
            "including any trip details, and they'll be with you shortly."
        )
        visible = guard.text(sentence)
        assert visible + guard.flush() == sentence
        assert guard.rewrote is False

    def test_all_set_with_a_booking_noun_is_still_caught(self):
        """The fixture this guarded against originally must still fail without a tool result."""
        guard = ClaimGuard()
        guard.text("You're all set — the flight is booked.")
        assert guard.flush() == BOOKING_REPLACEMENT_NO_HOLD


class TestHumanHandoffGuard:
    """The same defence as `ClaimGuard`, for a claimed human handoff with no escalation card.

    Verbatim (first two cases) from a browser run of "I'd rather talk to a person about this":
    the agent answered *"I'm connecting you to a human agent now who can help you with your policy
    question about conference travel."* and `escalate_to_human` was never invoked — confirmed
    against CloudWatch, which showed no log stream for the tool in that window.
    """

    def test_a_claim_without_an_escalation_card_is_replaced(self):
        guard = HumanHandoffGuard()
        sent = guard.text("I'm connecting you to a human agent now who can help with that.")
        assert sent == "", "a handoff claim must not stream before it has been checked"
        assert guard.flush() == HANDOFF_REPLACEMENT
        assert guard.rewrote is True

    def test_the_same_claim_with_a_real_escalation_card_is_left_alone(self):
        guard = HumanHandoffGuard()
        assert guard.text("I'm connecting you to a human agent now") == ""
        guard.note_card([{"card_type": "escalation", "data": {"status": "prepared"}}])
        released = guard.text(" who can help with that.")
        assert released == "I'm connecting you to a human agent now who can help with that."
        assert guard.flush() == ""
        assert guard.rewrote is False

    def test_a_card_noted_before_the_claim_still_counts(self):
        """Order within a turn does not matter, same as `ClaimGuard`."""
        guard = HumanHandoffGuard()
        guard.note_card([{"card_type": "escalation", "data": {}}])
        visible = guard.text("I'm connecting you to a human agent now.")
        assert visible + guard.flush() == "I'm connecting you to a human agent now."
        assert guard.rewrote is False

    def test_a_claim_split_across_chunks_is_caught(self):
        guard = HumanHandoffGuard()
        chunks = ["I'm connec", "ting you to a human agent now."]
        outputs = [guard.text(chunk) for chunk in chunks]
        assert outputs == ["", ""], f"a split claim leaked: {outputs!r}"
        assert guard.flush() == HANDOFF_REPLACEMENT

    def test_an_offer_or_question_is_not_a_claim(self):
        """Exactly what the agent should say before the tool has run."""
        for phrase in [
            "Would you like me to connect you to a human agent?",
            "Shall I get someone from your travel desk?",
            "Can I connect you to a person to help with this?",
        ]:
            guard = HumanHandoffGuard()
            visible = guard.text(phrase)
            tail = guard.flush()
            assert visible + tail == phrase, (phrase, visible, tail)
            assert guard.rewrote is False

    def test_the_tools_own_no_queue_refusal_is_not_rewritten(self):
        """The tool's own message when a tenant has no support queue configured — relayed
        verbatim, it must never be rewritten into a claim of the very thing it refused."""
        guard = HumanHandoffGuard()
        message = (
            "I can't transfer you to a person from here — your company hasn't set up a "
            "travel desk queue for this assistant."
        )
        visible = guard.text(message)
        tail = guard.flush()
        assert visible + tail == message
        assert guard.rewrote is False

    def test_a_report_that_a_human_will_be_with_you_needs_a_card_too(self):
        guard = HumanHandoffGuard()
        guard.text("A human agent from your travel desk will be with you shortly.")
        assert guard.flush() == HANDOFF_REPLACEMENT

    def test_the_rolling_window_catches_a_claim_split_across_four_chunks(self):
        guard = HumanHandoffGuard()
        prefix = "A safe introductory sentence. " * 5
        chunks = [prefix + "I'm ", "connect", "ing you ", "now."]
        visible = "".join(guard.text(chunk) for chunk in chunks)
        assert len(prefix) > LOOKBEHIND
        assert visible == prefix
        assert guard.flush() == HANDOFF_REPLACEMENT

    def test_ordinary_prose_is_byte_identical_after_flush(self):
        guard = HumanHandoffGuard()
        chunks = [
            "Your company's policy says that documented rate inflation ",
            "does not require pre-approval. ",
            "Let me know if you'd like anything else.",
        ]
        visible = "".join(guard.text(chunk) for chunk in chunks) + guard.flush()
        assert visible == "".join(chunks)
        assert guard.rewrote is False

    def test_the_rolling_window_never_splits_a_word(self):
        """Same defect as `ClaimGuard`'s equivalent test, and the same fix: both guards' rolling
        window used to release a raw `len(pending) - LOOKBEHIND` slice with no regard for where a
        word ended.
        """
        guard = HumanHandoffGuard()
        chunks = [
            "Your company's policy says that documented rate infla",
            "tion does not require pre-approval, so nothing further is needed here.",
        ]
        visible = "".join(guard.text(chunk) for chunk in chunks) + guard.flush()
        assert visible == "".join(chunks)
        assert guard.rewrote is False

    def test_one_real_card_licenses_every_claim_for_the_rest_of_the_turn(self):
        """`main.py` builds one guard per turn, and a turn escalates at most once in practice — so
        once a real card has landed, later handoff-shaped prose in the same turn is not re-checked.
        Stated explicitly, since it is a consequence of `_escalated` never resetting rather than
        something asserted anywhere else.
        """
        guard = HumanHandoffGuard()
        first_visible = guard.text("I'm connecting you to a human agent now.")
        guard.note_card([{"card_type": "escalation", "data": {}}])
        assert first_visible + guard.flush() == "I'm connecting you to a human agent now."

        second_visible = guard.text("As I mentioned, you're being connected to that agent.")
        assert (
            second_visible + guard.flush()
            == "As I mentioned, you're being connected to that agent."
        )
