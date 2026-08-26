"""Forcing a tool call when the click already decided which tool answers.

**Why this exists at all.** A card button becomes a user turn (see `conversation-api/app/actions.py`),
and the model then re-derives which tool the turn wants. That indirection is deliberate — one entrance
to the capability layer means one set of controls — but it leaves the *decision* to a model, and on the
write path a wrong decision is a stall: about one run in three, *"I'd like hotel option opt_x"* was
answered with *"good choice — shall I prepare it?"*, which is a reasonable reply to what was said and no
tool call at all. Imperative phrasing that names the tool fixed the observed failures, but phrasing is
persuasion; a prompt edit or a model version can quietly undo it.

So on the write path the choice is removed rather than discouraged: Bedrock's `toolChoice` accepts
`{"tool": {"name": ...}}`, and the model must then call that tool.

**What forcing does not do.** It decides *that* the tool runs, never *what it returns*. The tool still
re-derives ownership from the handle, re-checks the hold has not expired, and reads the tenant's
`booking_mode`. A confirm on a lapsed hold still fails — the refusal simply comes from the tool, where it
belongs, rather than from a model declining to try. Cedar, the gateway interceptor and the guardrail are
all downstream of this and untouched.

**Two failure modes this guards against, both worse than the stall it fixes.**

1. *A name Bedrock does not recognise* aborts the whole request with a validation error, so an unknown
   tool degrades to no forcing rather than to a broken turn. The names are gateway-prefixed
   (`booking___prepare_booking`) because that is what the model is shown.
2. *Forcing every model call in the turn* is an infinite loop: the event loop invokes the model again
   with the tool result, and a still-forced `toolChoice` obliges it to call the tool a second time,
   forever. So forcing applies to the **first** call only — recognised the way the SDK's own injection
   policy recognises a fresh ask, by the latest message being a plain user turn with no tool result in
   it.

**`strands._middleware` is a private module.** The public seams — hooks — fire around the model call but
cannot rewrite its arguments, and `tool_choice` is only otherwise plumbed from structured output, which
this is not. The import is guarded so a version that moves it costs the forcing and nothing else; the
click still works, on the phrasing alone.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any

logger = logging.getLogger(__name__)


# **The only tools a caller may force, stated here rather than inferred from what the turn offers.**
#
# `force_tool` arrives in the runtime payload, and the payload is a channel the *client* controls. The
# BFF only ever sends one of these four — they mirror `FORCED_TOOLS` in `conversation-api/app/actions.py`
# — but the runtime is reachable by anything holding a valid token, so "what the BFF sends" is not a
# constraint the agent can rely on. Checking only that the name is among the turn's tools accepted any
# tool at all, including every write tool.
#
# Not a privilege escalation, and worth being precise about why: a caller who can reach the runtime can
# reach the gateway too, and there the interceptor injects tenancy from verified claims, Cedar decides,
# and the tool re-checks ownership. Forcing grants no capability. What it does grant is *initiative* —
# choosing which write tool a turn invokes, on a channel the model was never meant to arbitrate. That is
# a seam a reviewer of this sample will look at, so it is closed rather than explained.
#
# Gateway-prefixed, because that is the name the model is shown and the only form `toolChoice` accepts.
FORCEABLE = frozenset(
    {
        "booking___prepare_booking",
        "booking___confirm_booking",
        "booking___cancel_reservation",
    }
)


def _tool_names(tools: list[Any]) -> set[str]:
    """The names the model is shown, which are the names `toolChoice` must use."""
    return {name for tool in tools if (name := getattr(tool, "tool_name", None))}


def _is_first_call(messages: list[dict[str, Any]]) -> bool:
    """Whether this model call is the turn's first — a plain user ask, not a tool-result loop.

    The same test the SDK uses for its `"userTurn"` injection trigger: a `user` message carrying a
    `toolResult` is the event loop coming back with an answer, and forcing that call is the infinite
    loop described in the module docstring.
    """
    if not messages:
        return False
    last = messages[-1]
    return last.get("role") == "user" and not any(
        "toolResult" in block for block in last.get("content", [])
    )


def force(agent: Any, tool_name: str, tools: list[Any]) -> bool:
    """Make this turn's first model call use `tool_name`. Returns whether forcing was installed.

    `False` means the turn proceeds unforced — an unrecognised tool name or an SDK without the
    middleware seam. Both are logged, because the symptom otherwise is invisible: the click still works
    most of the time, which is exactly the intermittency this was built to remove.
    """
    # Refused before the tool list is consulted: whether the name is on offer this turn is a
    # different question from whether it may be forced at all. See `FORCEABLE`.
    if tool_name not in FORCEABLE:
        logger.error(
            "refused to force %r: not in the forceable set %s",
            tool_name,
            sorted(FORCEABLE),
        )
        return False

    available = _tool_names(tools)
    if tool_name not in available:
        # The BFF's registry and the gateway's target names have drifted. Not fatal — but it means the
        # write path is back to persuasion, and nobody would notice from the outside.
        logger.error(
            "cannot force %s: not among the %d tool(s) this turn offers", tool_name, len(available)
        )
        return False

    try:
        from strands._middleware import InvokeModelStage
    except ImportError:
        logger.warning("this strands version has no middleware seam; not forcing %s", tool_name)
        return False

    choice = {"tool": {"name": tool_name}}

    async def handler(context: Any) -> Any:
        if not _is_first_call(context.messages):
            return context
        if context.tool_choice is not None:
            # Structured output set it, and that is a stronger claim on the call than ours.
            return context
        return replace(context, tool_choice=choice)

    agent._middleware_registry.add_middleware(InvokeModelStage.Input, handler)
    return True
