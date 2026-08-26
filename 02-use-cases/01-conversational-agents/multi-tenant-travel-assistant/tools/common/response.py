"""The response contract every tool returns.

    {cards, facts, message, provenance}

Four fields, each with one job, because the alternative — a tool that returns
whatever shape suits it — puts the model in the position of interpreting structure,
which is exactly what it is bad at.

**`cards`** — typed, tool-authored UI components. The frontend renders them
directly; the model never writes them. That is an XSS boundary and keeps
presentation separate from the machine-readable answer in `facts`.

**`facts`** — computed values the model may *narrate but never derive*. Counts,
caps, verdicts, arithmetic. A model that can compute a policy verdict can compute
it wrong, so the code computes and the model phrases.

**`message`** — prose for the cases where there is nothing to render: an empty
result, a refusal, an error. Deliberately **not** a summary of the cards. An earlier
draft had the tool write "3 in-policy hotels under your €180 cap", which is a
sentence the user may never have asked for; `facts` lets the model decide what is
worth saying.

**`provenance`** — where the answer came from, so a claim can be traced to a source
rather than trusted because it sounded confident.
"""

from __future__ import annotations

from typing import Any


def tool_response(
    *,
    cards: list[dict[str, Any]] | None = None,
    facts: dict[str, Any] | None = None,
    message: str | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble a response, omitting the fields that have nothing to say.

    Empty keys are dropped rather than sent as `null`/`[]`: every unused field is
    context the model pays for on this step and on every step after it, and a
    `"cards": []` invites the model to comment on an absence that is not
    meaningful.
    """
    response: dict[str, Any] = {}
    if cards:
        response["cards"] = cards
    if facts:
        response["facts"] = facts
    if message:
        response["message"] = message
    if provenance:
        response["provenance"] = provenance
    return response


def refusal(message: str, *, provenance: dict[str, Any] | None = None) -> dict[str, Any]:
    """A clean "I can't answer that", with no cards and no facts.

    A refusal must be indistinguishable in *shape* from a normal response so the
    model handles it as an answer rather than a malfunction — but it carries no
    facts, because inventing a plausible-looking one is the failure this prevents.
    """
    return tool_response(message=message, provenance=provenance)
