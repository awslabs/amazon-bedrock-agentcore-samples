"""The agent entrypoint.

Three things happen per invocation, in this order:

1. **Read the traveller's bearer token** from the request headers. Runtime already
   validated it against Cognito; we forward it to the Gateway unchanged so the request
   interceptor can verify it again at the tool boundary and inject tenant context. The
   agent never asserts who is asking to a *tool* — the one place it reads identity itself
   is memory, which must name an actor; see `memory.py`.
2. **Build the agent** with a tenant-invariant system prompt and the Gateway's tools.
3. **Stream typed events**, not bare text — so tool status reaches the UI and token usage
   reaches the ledger. The scaffold yielded `event["data"]` and discarded both.

**The agent is built per invocation, not cached in a module global.** The scaffold cached
one; here the MCP client carries *this traveller's* credential, so a shared instance would
mean acting for whoever warmed the container.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent

import budget as budget_config
import handoff
import metrics
import stream as ev
import tool_choice
import unclaimed
from ledger import Trajectory
from mcp_client.client import get_gateway_client, list_tools
from memory import conversation_memory, identity, session_context
from model.load import guardrail_id, load_model, model_id
from pricing import price
from prompts.manager import prompt_version, system_blocks

app = BedrockAgentCoreApp()
log = app.logger

# Exported beside the tool schemas and copied into the bundle at deploy time.
ev.load_labels(os.path.join(os.path.dirname(__file__), "tool-labels.json"))

NO_TOOLS_MESSAGE = (
    "I can't reach your travel information right now, so I'd rather not guess. "
    "Please try again in a moment."
)


def _bearer(context: Any) -> str | None:
    """The traveller's access token, from the allowlisted Authorization header.

    Absent means the runtime's `requestHeaderAllowlist` omits `Authorization` — a
    configuration fault, not a user error, and one that silently removes every tool.
    """
    headers = getattr(context, "request_headers", None) or {}
    if hasattr(headers, "items"):
        for key, value in headers.items():
            if str(key).lower() == "authorization":
                token = str(value)
                return token[7:].strip() if token.lower().startswith("bearer ") else token
    return None


def _session_id(context: Any) -> str | None:
    for attr in ("session_id", "runtime_session_id"):
        if value := getattr(context, attr, None):
            return str(value)
    return None


def _today_block() -> str:
    """Today's date, as a post-cache-breakpoint system block.

    **Why the model needs telling at all:** it defaults to its training-era year whenever it writes a
    date it was not given. Measured — asked to prepare a booking from a December 2026 search, it sent
    `2024-12-05`, the backend regenerated a different option set, and the hold was refused. A travel
    assistant that cannot place "next Tuesday" is wrong about the one thing it is for.

    **A system block after the cache breakpoint, not a prefix on the user message** — and that move is
    the point. It joins the session-identity block in the uncached suffix (see
    `prompts.manager.system_blocks`): the stable prefix is still read from cache, while this is re-sent
    fresh every turn, so it can never go stale. Unlike the old per-turn user prefix, it also never
    enters the transcript stored in Memory, so a reopened conversation shows what the traveller typed
    rather than an internal `[Today is …]` annotation.

    UTC rather than a traveller's local zone: the date is a reference point for resolving relative
    phrases, and the tools take explicit `YYYY-MM-DD` values anyway. A per-traveller timezone would be
    a second source of truth for "now" with no question that needs it.
    """
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    return (
        f"<today>Today's date is {today} (UTC). "
        'Use it to resolve relative dates such as "next Tuesday" or "10 November".</today>'
    )


def _post_cache_context(bearer: str | None) -> str:
    """The uncached system suffix: today's date, plus who the turn is for when the claims are present.

    Both pieces sit after the cache breakpoint, so the stable prefix still cache-hits. Joined here so
    the date is always supplied even on a turn with no verified identity (where `session_context`
    returns `None`).
    """
    return "\n".join(block for block in (_today_block(), session_context(bearer)) if block)


def _tool_result_blocks(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Tool results carried on a message event.

    Strands formats completed tool calls into a conversation message, and *that* is what
    reaches `stream_async` — `ToolResultEvent` itself is marked `is_callback_event = False`
    and never arrives. Content blocks look like
    `{"toolResult": {"toolUseId": ..., "status": ...}}`.
    """
    message = event.get("message")
    if not isinstance(message, dict):
        return []
    return [
        block["toolResult"]
        for block in message.get("content", [])
        if isinstance(block, dict) and isinstance(block.get("toolResult"), dict)
    ]


@app.entrypoint
async def invoke(payload: dict[str, Any], context: Any):
    """Handle one turn, yielding typed stream events."""
    prompt = (payload or {}).get("prompt") or ""
    # **A tool the BFF says this turn must call, or `None`.** Only a write-path *click* sets it: the
    # traveller has already chosen, so which tool answers is not a judgement the model needs to make.
    # See `tool_choice.py` for how it is applied and why persuasion was not enough.
    force_tool = (payload or {}).get("force_tool") or None
    session_id = _session_id(context)
    token = _bearer(context)

    model = load_model()
    # **Stamped here after all, reversing the earlier choice, and the reason is specific.** This
    # used to be left absent on the argument that the interceptor's record is the copy an auditor
    # can check without trusting this process — which is still true, and still where an *audit*
    # should read it from. But a CloudWatch metric takes its dimensions at publication time, so
    # "which tenant is expensive?" as a dimension on a graph or an alarm cannot be recovered by
    # joining logs afterwards. The values come from the same runtime-verified token `memory.py`
    # already reads, on a path the model cannot reach, so this is not the model naming a tenant.
    # The interceptor's copy remains authoritative for audit, and if the two ever disagree that is
    # itself a signal worth having rather than a dimension worth losing.
    tenant_id, traveler_id = identity(token)
    trajectory = Trajectory(
        tenant_id=tenant_id,
        traveler_id=traveler_id,
        session_id=session_id,
        model_id=model_id(model),
        prompt_version=prompt_version(),
        guardrail_id=guardrail_id(),
        # Supplied here rather than defaulted inside the ledger, so the ledger stays a record of
        # facts and this is the one line that decides a trajectory gets a dollar figure at all.
        pricer=price,
    )

    # The session id travels to the tools so a DynamoDB row read lands in CloudTrail tagged with
    # the conversation that caused it — the same value the ledger records, so cost and audit join
    # on one dimension instead of needing a mapping.
    client = get_gateway_client(token, session_id)
    if client is None:
        yield ev.text(NO_TOOLS_MESSAGE)
        # **Recorded as an outcome, not dropped.** A turn that never reached a tool still consumed
        # a traveller's question, and leaving it out of the ledger would remove it from the
        # denominator of cost per resolved task — flattering the resolution rate by hiding the
        # failures rather than by resolving anything.
        trajectory.outcome = "failed_no_gateway"
        metrics.publish_trajectory(log, trajectory.emit(log))
        yield ev.done()
        return

    # A context manager: the MCP session lives for this turn only, because it carries this
    # traveller's credential.
    with client:
        try:
            tools = list_tools(client)
        except Exception:
            log.exception("could not list gateway tools")
            yield ev.text(NO_TOOLS_MESSAGE)
            trajectory.outcome = "failed_no_tools"
            metrics.publish_trajectory(log, trajectory.emit(log))
            yield ev.done()
            return

        log.info(
            "agent ready: %d tool(s), prompt %s, session %s",
            len(tools),
            trajectory.prompt_version,
            session_id,
        )

        # **AgentCore Memory: this conversation's history, and this traveller's preferences.**
        # Without it a booking cannot complete — "book the first one" only means something if the
        # previous turn's search is still in context, and the write path is three turns by design.
        #
        # The token is passed because memory is the one place the agent must name *who* it is acting
        # for; see `memory.py` for why reading a runtime-verified claim is not the model choosing a
        # tenant.
        # **The system prompt is two blocks with a cache breakpoint between them**, so this session's
        # identity costs its own tokens and nothing more: the stable prefix is still read from cache.
        # Measured — three travellers across two tenants each read the same 1042 cached tokens.
        #
        # The turn's date rides in that same uncached suffix (`_post_cache_context`), not on the user
        # message: the post-breakpoint block is re-sent every request, so the date stays current, and
        # it never lands in the stored transcript the way a message prefix would.
        agent = Agent(
            model=model,
            system_prompt=system_blocks(_post_cache_context(token)),
            tools=tools,
            session_manager=conversation_memory(session_id, token),
        )

        # **Force the tool when the click already decided it.** Only the BFF's write-path clicks set
        # this, so a typed turn is untouched and ordinary conversation is unchanged. Registered per
        # invocation because the agent is too — see `tool_choice.py` for why phrasing alone was not
        # enough and what forcing deliberately does *not* decide.
        if force_tool and tool_choice.force(agent, force_tool, tools):
            log.info("forcing %s on this turn", force_tool)

        open_tools: dict[str, str] = {}
        # Cached per container, so this is a dict lookup rather than an SSM call per turn.
        caps = budget_config.budget()
        breach: str | None = None
        trajectory.start_step()

        # **Refuses to relay a booking the agent did not make.** Measured: asked "yes, confirm it" after
        # a prepared booking, the model answered *"your flight is confirmed… charged to your Visa"* with
        # no tool call at all, in 4 of 6 runs. The prompt already forbids exactly that, and four attempts
        # to strengthen the wording moved the number around without fixing it — one made it worse. So the
        # claim is checked rather than requested. See `unclaimed.py`.
        guard = unclaimed.ClaimGuard()

        # **The same defence for "I'm connecting you now."** Found in the same browser sweep that
        # redeployed the SigV4 fix: asked for a human, the agent claimed a handoff with
        # `escalate_to_human` never invoked — confirmed against CloudWatch, which showed no log
        # stream for the tool. See `unclaimed.py` for why this is a card-gated guard rather than a
        # third `ClaimKind` on the one above.
        handoff_guard = unclaimed.HumanHandoffGuard()

        async for event in agent.stream_async(prompt):
            if isinstance(event.get("data"), str):
                # May return "" while a possible claim is buffered; `flush` below releases or rewrites it.
                if visible := guard.text(event["data"]):
                    if visible := handoff_guard.text(visible):
                        yield ev.text(visible)

            # `current_tool_use` repeats while the model streams the tool's arguments, so
            # emit `tool_start` only the first time an id appears.
            if use := event.get("current_tool_use"):
                use_id = use.get("toolUseId")
                raw_name = use.get("name") or ""
                if use_id and raw_name and use_id not in open_tools:
                    name = ev.strip_target_prefix(raw_name)
                    open_tools[use_id] = name
                    trajectory.record_tool(name)
                    yield ev.tool_start(name, use_id)

            # Completion comes from the **message** event, not `ToolResultEvent`: that one
            # sets `is_callback_event = False`, so it never reaches `stream_async` at all.
            # Watching for it produced a pill that started and never cleared.
            for block in _tool_result_blocks(event):
                use_id = block.get("toolUseId")
                if name := open_tools.pop(use_id, None):
                    ok = block.get("status") != "error"
                    for payload in ev.payloads_in(block):
                        guard.record_result(name, payload, ok=ok)
                    # A tool that refuses still returns cleanly, so `ok` reflects transport
                    # success — the refusal text is the model's to relay.
                    yield ev.tool_end(name, use_id, ok=ok)
                    # The model resumes with a fresh sentence and no leading space. Told to the
                    # guard rather than handled downstream: short pre-tool narration never reaches
                    # the client as its own chunk, so this boundary is invisible from there.
                    guard.tool_boundary()
                # **Cards must be forwarded here or they reach nothing.** The tool response
                # terminates at the model, so a card the frontend never receives is a tile that
                # cannot be drawn — the UI would render prose where an option list belongs.
                # Only the `cards` array travels; the rest of the envelope stays the model's.
                if built := ev.cards_in(block):
                    yield ev.cards(built)
                    handoff_guard.note_card(built)
                    # **A handoff the model asked for is an escalation too.** Only the budget path
                    # set this before, so a traveller saying "get me a person" was recorded as an
                    # ordinary completed turn — and cost per resolved task cannot tell a clean
                    # handoff from an answer if the ledger does not distinguish them. Found by the
                    # eval suite's first real run, not by reading this file.
                    #
                    # Keyed on the card rather than on the tool call, because the escalation tool
                    # refuses a tenant with no support queue by returning a message and *no* card.
                    # That refusal is not an escalation, and counting it as one would report a
                    # handoff to a queue that does not exist.
                    if any(c.get("card_type") == "escalation" for c in built):
                        trajectory.outcome = "escalated"

            metadata = (event.get("event") or {}).get("metadata") or {}

            # The guardrail's own verdict, on the same metadata event as usage. Recorded
            # because a blocked turn otherwise looks exactly like the model choosing to
            # decline — and a control whose firing leaves no trace cannot be shown to work,
            # nor shown to stop working.
            if guardrail := (metadata.get("trace") or {}).get("guardrail"):
                before = list(trajectory.guardrail_blocked)
                trajectory.record_guardrail(guardrail)
                if fired := [c for c in trajectory.guardrail_blocked if c not in before]:
                    log.warning("guardrail intervened: %s", ", ".join(fired))
                    yield ev.guardrail(fired)

            # Cache counters come straight from the SDK, so the hit rate is observed
            # rather than inferred.
            if usage := metadata.get("usage"):
                trajectory.record_usage(usage)

                # **Checked here, between steps, because anywhere else is too late.** A check after
                # the loop would report a runaway that had already finished paying for itself. This
                # is the first moment the new totals exist, and breaking out of `stream_async` is
                # what actually stops the next model call from being made.
                if breach := caps.breach(
                    steps=trajectory.steps_taken, usd=trajectory.cost().get("usd")
                ):
                    trajectory.outcome = "escalated_budget"
                    log.error("budget breach, stopping the turn: %s", breach)
                    break

                trajectory.start_step()

        # **The handoff, fired by code rather than asked of the model.** The model is what just
        # overran, so asking it to escalate would be asking it to notice its own loop — and it has
        # already demonstrated it did not. Calling the real tool rather than writing a message keeps
        # one escalation path: the same tenant queue lookup, the same refusal when no queue exists,
        # the same card the traveller sees when they ask for a person themselves.
        if trajectory.outcome == "escalated_budget":
            async for event in handoff.escalate_over_budget(client, trajectory, breach):
                yield event

        summary = trajectory.emit(log)
        # From the line just written, so the graph and the log cannot disagree.
        metrics.publish_trajectory(log, summary)
        # **Before `done`, because the client settles the turn on it.** Text arriving after `done` is
        # text the transcript has already finished rendering.
        if tail := guard.flush():
            if guard.rewrote:
                log.error(
                    "replaced a fabricated %s completion claim; no successful matching tool result",
                    guard.rewritten_kind,
                )
            # Chained through the second guard rather than yielded directly: a booking claim that
            # survived the first guard could still be, in the same sentence, an unverified handoff
            # claim — the two defences compose the same way their sources do.
            if tail := handoff_guard.text(tail):
                yield ev.text(tail)
        if tail := handoff_guard.flush():
            yield ev.text(tail)

        yield ev.done(
            {
                "input": summary["input_tokens"],
                "output": summary["output_tokens"],
                "cache_read": summary["cache_read_tokens"],
                "cache_write": summary["cache_write_tokens"],
            },
            steps=summary["steps"],
            outcome=summary["outcome"],
        )


if __name__ == "__main__":
    app.run()
