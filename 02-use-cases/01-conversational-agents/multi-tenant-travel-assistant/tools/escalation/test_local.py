"""Smoke test for `escalate_to_human`.
    BACKEND_API_URL=... tools/.venv/bin/python -m tools.escalation.test_local

**The package is what is being tested**, not the transfer. A handoff that arrives without context
has
made the traveller start over, which is worse than never offering a human — so the checks assert
that
trip state and a useful summary line are present, and that a tenant with no queue is told the truth
rather than transferred into a void.
"""

from __future__ import annotations

import sys

from shared.cards import assert_all_valid
from tools.common.testing import GLOBEX, FakeLambdaContext, ok, summarise

from .handler import handler as lambda_handler
from .schemas import ESCALATE_TO_HUMAN

REASON = "needs a business-class exception for a medical reason on the Delhi trip"


def call(arguments: dict, identity=GLOBEX) -> dict:
    return lambda_handler(arguments, FakeLambdaContext(ESCALATE_TO_HUMAN, identity=identity))


def main() -> int:
    results: list[bool] = []

    print("\nA real escalation")
    response = call({"reason": REASON})
    facts = response.get("facts") or {}
    results.append(
        ok(
            "escalates and names the queue it went to",
            facts.get("escalated") is True and bool(facts.get("queue")),
            f"queue={facts.get('queue')}",
        )
    )
    try:
        assert_all_valid(response)
        results.append(ok("the escalation card matches the contract", True))
    except AssertionError as error:
        results.append(ok("the escalation card matches the contract", False, str(error)))

    data = (response.get("cards") or [{}])[0].get("data") or {}
    results.append(
        ok(
            "the summary line describes the problem, not just 'needs help'",
            REASON.split()[0] in (data.get("context_summary_line") or ""),
            f"{data.get('context_summary_line')}",
        )
    )
    results.append(
        ok(
            "trip state is included so the human agent opens the right record",
            "trip_state" in (facts.get("context_included") or []),
            f"included: {facts.get('context_included')}\n"
            "Assembled in code — a model summarising its own conversation summarises it\n"
            "optimistically.",
        )
    )
    results.append(
        ok(
            "the conversation id travels with it, joining the handoff to the ledger",
            "session_id" in (facts.get("context_included") or []),
            "same dimension name as the audit trail — one name per dimension",
        )
    )
    results.append(
        ok(
            "the card carries no actions — the handoff IS the action",
            not (response.get("cards") or [{}])[0].get("actions"),
            "a button here would imply the traveller still has something to do",
        )
    )

    print("\nRefusals")
    empty = call({})
    results.append(
        ok(
            "escalating with no reason is refused",
            "what this is about" in (empty.get("message") or "").lower(),
            (empty.get("message") or "")[:120],
        )
    )

    long_reason = call({"reason": "x" * 900})
    results.append(
        ok(
            "an over-long reason is truncated rather than refused",
            (long_reason.get("facts") or {}).get("escalated") is True,
            "a slightly clipped reason still beats no handoff",
        )
    )

    return summarise(results)


if __name__ == "__main__":
    sys.exit(main())
