"""A small AgentCore agent that Welt can drive.

Receives Welt's payload, feeds it to a Strands agent, and yields the
renderable subset of its `stream_async` events — the AgentCore Runtime SDK
emits each one as SSE, which Welt (https://github.com/iwamot/welt) renders
into Slack. The payload carries one of two envelopes: Converse-shaped
`messages` for a conversation turn, or `interrupt_responses` when a human
answered the approval buttons of an interrupted run.

This example is a standalone deployable; Welt drives it only through the
JSON wire contract, which welt-io-strands adapts in both directions.
"""

import os
import tempfile
from collections.abc import AsyncIterator

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, ToolContext, tool
from strands_tools import current_time, generate_image

from welt_io_strands import (
    decode_interrupt_responses,
    decode_messages,
    interrupt_reason,
    renderable_events,
)

# generate_image saves each image under ./output as a side effect, and the
# temp dir is the writable path in the AgentCore Runtime container.
os.chdir(tempfile.gettempdir())

app = BedrockAgentCoreApp()

# Where an interrupted Agent waits for its answers. One slot is enough:
# AgentCore Runtime runs each session in its own microVM, so this process
# never serves two sessions. Resume only: a normal turn always builds a
# fresh Agent from the messages Welt sends (the Slack thread is the source
# of truth for conversation history, so the slot must not stand in for
# it). No persistence either — the slot lives and dies with the session's
# microVM (recycled on idle timeout, 8 hours at most).
_interrupted_agent: Agent | None = None


@tool(context=True)
def sample_dangerous_action(tool_context: ToolContext, action: str) -> str:
    """
    Pretend to run a dangerous or irreversible action the user asked for.

    A sample of the approval round trip: the interrupt below pauses the
    run until someone answers in the Slack thread — with the buttons, or
    by typing an instruction into the text field. Nothing is actually
    executed.

    Args:
        tool_context (ToolContext): The Strands tool context.
        action (str): The action to pretend to run.

    Returns:
        str: The outcome of the action.
    """
    answer = tool_context.interrupt(
        "example-dangerous-action-approval",
        reason=interrupt_reason(
            f"May I run this dangerous action? — {action}",
            [
                {"value": "y", "label": "Approve", "style": "primary"},
                {"value": "n", "label": "Cancel"},
            ],
            input={"label": "Or tell me what to do instead"},
        ),
    )
    if answer == "y":
        return f"Ran: {action}. (This example doesn't actually run anything.)"
    if answer == "n":
        return "The action was cancelled by the user."
    return f"The action was not run. The user said instead: {answer}"


@app.entrypoint
async def invoke(payload: dict) -> AsyncIterator[dict]:
    """
    Stream a reply to the conversation or approval answers Welt sent.

    Args:
        payload (dict): The invocation payload: Converse-shaped `messages`
            built by Welt from the Slack thread (file blocks
            base64-encoded), or `interrupt_responses` carrying the button
            answers that resume an interrupted run.

    Yields:
        dict: The renderable subset of Strands `stream_async` events.
    """
    global _interrupted_agent

    if "interrupt_responses" in payload:
        agent = _interrupted_agent
        _interrupted_agent = None
        if agent is None:  # The microVM was recycled while the buttons waited.
            # The SDK reports the raise as an `error` event, and Welt renders
            # its resume-failure notice.
            raise RuntimeError("No interrupted agent to resume in this session.")
        stream = agent.stream_async(decode_interrupt_responses(payload["interrupt_responses"]))
    else:
        messages = payload.get("messages")
        if not isinstance(messages, list) or not messages:
            yield {"data": "I received an empty conversation, so there is nothing to reply to."}
            return
        messages = decode_messages(messages)  # base64 file bytes -> raw bytes
        agent = Agent(
            # Any Converse model; unset falls back to the Strands default.
            model=os.environ.get("MODEL_ID"),
            tools=[current_time, generate_image, sample_dangerous_action],
            callback_handler=None,
        )
        stream = agent.stream_async(messages)

    interrupted = False
    # Reduce the stream to the JSON-serializable events Welt renders
    async for event in renderable_events(stream):
        if "interrupt" in event:
            interrupted = True
        yield event

    if interrupted:
        # Re-stashed on every interrupted stop, so a resume that interrupts
        # again keeps working.
        _interrupted_agent = agent


if __name__ == "__main__":
    app.run()
