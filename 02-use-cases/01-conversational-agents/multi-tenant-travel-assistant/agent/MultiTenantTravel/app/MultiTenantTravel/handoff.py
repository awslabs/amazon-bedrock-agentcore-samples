"""Hand a conversation to a human after the agent stops itself.

Separate from `main.py` so it can be tested without the runtime: `main.py` imports
`bedrock_agentcore` to declare the entrypoint, which is not installable in the environment the
test suite runs in. Putting the logic here means the budget handoff is exercised directly rather
than through a stub of the whole app — and this is the path that only ever runs when something has
already gone wrong, so it is the last one that should be verified by inspection.
"""

from __future__ import annotations

import logging
from typing import Any

import budget
import stream as ev
from ledger import Trajectory

log = logging.getLogger(__name__)

ESCALATION_TOOL = "escalation___escalate_to_human"

# What the traveller reads when the assistant stops itself. Deliberately does not blame them and
# does not promise a timescale the sample cannot keep.
OVER_BUDGET_MESSAGE = (
    "I've spent longer on this than I should without getting you an answer, so I'm handing this "
    "to a person on your travel desk with everything we've covered."
)
# Used only when the handoff itself could not be completed — a tenant with no support queue, or an
# unreachable gateway. Saying "I'm connecting you" into a void is the one outcome to avoid.
OVER_BUDGET_NO_HANDOFF = (
    "I've spent longer on this than I should without getting you an answer, and I can't reach your "
    "travel desk from here either. Your internal travel team will be able to help."
)


async def escalate_over_budget(client: Any, trajectory: Trajectory, breach: str) -> Any:
    """Hand off after a budget breach, through the ordinary escalation tool.

    **The same tool a traveller's own "get me a human" goes through**, so the tenant's queue lookup,
    its refusal when no queue is configured, and the card the traveller sees are identical on both
    paths. A second, code-only handoff would be a second thing to keep correct, and it is the one
    that would rot — nobody demonstrates the budget path in a browser.

    The reason is built from the ledger rather than generated, and nothing here raises: a failure to
    escalate must still leave the traveller with something true to act on.
    """
    reason = budget.reason_for_handoff(
        breach,
        steps=trajectory.steps_taken,
        usd=trajectory.cost().get("usd"),
        tools=trajectory.tools_tried,
    )
    try:
        result = await client.call_tool_async(
            tool_use_id=f"budget-{trajectory.session_id or 'session'}",
            name=ESCALATION_TOOL,
            arguments={"reason": reason},
        )
    except Exception:
        log.exception("could not escalate after a budget breach")
        yield ev.text(OVER_BUDGET_NO_HANDOFF)
        return

    cards = ev.cards_in(result) if isinstance(result, dict) else []
    # No card means the tool refused. The commonest cause is a tenant with no support queue, which
    # it reports as a message rather than as an error, so an absent card is the signal — not an
    # exception. Relayed as the honest version instead of a transfer that will not happen.
    yield ev.text(OVER_BUDGET_MESSAGE if cards else OVER_BUDGET_NO_HANDOFF)
    if cards:
        yield ev.cards(cards)
        log.info("escalated after a budget breach: %s", breach)
