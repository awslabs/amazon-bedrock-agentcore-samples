#!/usr/bin/env python3
"""Quick start example for Claude Code SDK."""

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

app = BedrockAgentCoreApp()


async def basic_example(prompt):
    """Basic example - simple question."""
    print("=== Basic Example ===")

    async for message in query(prompt=prompt):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"Claude: {block.text}")
        yield message
    print()


async def with_options_example(prompt):
    """Example with custom options."""
    print("=== With Options Example ===")

    options = ClaudeAgentOptions(
        system_prompt="You are a helpful assistant that explains things simply.",
        max_turns=1,
    )

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"Claude: {block.text}")
        yield message
    print()


async def with_tools_example(prompt):
    """Example using tools."""
    print("=== With Tools Example ===")

    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write"],
        system_prompt="You are a helpful file assistant.",
    )

    async for message in query(
        prompt=prompt,
        options=options,
    ):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"Claude: {block.text}")
        elif isinstance(message, ResultMessage) and message.total_cost_usd > 0:
            print(f"\nCost: ${message.total_cost_usd:.4f}")
        yield message
    print()


async def main(prompt, mode):
    """Run the right example based on mode."""

    if mode == 1:
        async for message in basic_example(prompt):
            yield message
    elif mode == 2:
        async for message in with_options_example(prompt):
            yield message
    elif mode == 3:
        async for message in with_tools_example(prompt):
            yield message
    else:
        yield "Input prompt and mode in [1,2,3]"


@app.entrypoint
async def run_main(payload):
    print("received payload")
    print(payload)

    print("sending to agent:")
    async for message in main(payload["prompt"], payload["mode"]):
        yield message


if __name__ == "__main__":
    app.run()
