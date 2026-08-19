#!/usr/bin/env python3
"""Claude Agent SDK - Orchestrator-Workers pattern with subagents."""

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

app = BedrockAgentCoreApp()


@app.entrypoint
async def main(payload):
    """Orchestrator agent that delegates to specialized subagents.

    The orchestrator receives a prompt and decides which subagent(s) to invoke:
    - code-analyzer: reads and analyzes code (read-only tools)
    - reporter: writes structured reports from analysis findings
    """
    prompt = payload["prompt"]

    options = ClaudeAgentOptions(
        system_prompt=(
            "You are an orchestrator agent. Your job is to coordinate specialized "
            "subagents to accomplish the user's request.\n\n"
            "Available subagents:\n"
            "- code-analyzer: Use this to examine and analyze code files. "
            "It has read-only access (Read, Grep, Glob).\n"
            "- reporter: Use this to write structured reports or summaries. "
            "It can read files and write new ones (Read, Write).\n\n"
            "Delegate tasks to the appropriate subagent using the Task tool. "
            "You can run subagents in parallel when their tasks are independent."
        ),
        allowed_tools=["Read", "Glob", "Grep", "Task"],
        agents={
            "code-analyzer": AgentDefinition(
                description=(
                    "Code analysis specialist. Use for examining code quality, "
                    "finding patterns, identifying issues, or understanding "
                    "code structure. Has read-only access."
                ),
                prompt=(
                    "You are a code analysis specialist. Examine code thoroughly "
                    "and report your findings clearly. Focus on:\n"
                    "- Code structure and organization\n"
                    "- Potential issues or bugs\n"
                    "- Patterns and best practices\n"
                    "- Dependencies and imports\n\n"
                    "Be concise and factual in your analysis."
                ),
                tools=["Read", "Grep", "Glob"],
            ),
            "reporter": AgentDefinition(
                description=(
                    "Report writing specialist. Use after analysis is complete "
                    "to produce structured summaries or documentation. "
                    "Can read existing files and write new ones."
                ),
                prompt=(
                    "You are a report writing specialist. Take analysis findings "
                    "and produce clear, structured summaries. Your reports should:\n"
                    "- Start with a brief overview\n"
                    "- Organize findings by category\n"
                    "- Highlight key issues or recommendations\n"
                    "- Be concise and actionable"
                ),
                tools=["Read", "Write"],
            ),
        },
    )

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"Claude: {block.text}")
        elif isinstance(message, ResultMessage) and message.total_cost_usd > 0:
            print(f"\nCost: ${message.total_cost_usd:.4f}")
        yield message


if __name__ == "__main__":
    app.run()
