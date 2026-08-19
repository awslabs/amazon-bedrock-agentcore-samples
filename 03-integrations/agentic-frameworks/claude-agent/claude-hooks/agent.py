#!/usr/bin/env python3
"""Claude Agent SDK - Hooks pattern for tool governance and audit logging."""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    HookContext,
    HookMatcher,
    ResultMessage,
    TextBlock,
    query,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()

# Patterns to block in Bash commands
BLOCKED_COMMANDS = ["rm -rf /", "rm -rf /*", "mkfs.", ":(){:|:&};:", "dd if=/dev/zero"]

# Paths where writes are denied
BLOCKED_WRITE_PATHS = ["/etc/", "/usr/", "/sys/", "/proc/", "/boot/"]


async def pre_tool_guard(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: HookContext,
) -> dict[str, Any]:
    """Validate tool calls before execution. Block dangerous operations."""
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # Guard: block dangerous Bash commands
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        for blocked in BLOCKED_COMMANDS:
            if blocked in command:
                logger.warning("BLOCKED dangerous command: %s", command)
                return {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": f"Blocked: '{blocked}' is not allowed",
                    }
                }

    # Guard: block writes to sensitive paths
    if tool_name in ("Write", "Edit"):
        file_path = tool_input.get("file_path", "")
        for blocked_path in BLOCKED_WRITE_PATHS:
            if file_path.startswith(blocked_path):
                logger.warning("BLOCKED write to restricted path: %s", file_path)
                return {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": f"Blocked: writes to '{blocked_path}' are not allowed",
                    }
                }

    logger.info("ALLOWED: %s", tool_name)
    return {}


async def post_tool_audit(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: HookContext,
) -> dict[str, Any]:
    """Log tool usage after execution for audit trail."""
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    timestamp = datetime.now(timezone.utc).isoformat()

    audit_entry = {
        "timestamp": timestamp,
        "tool": tool_name,
        "input_summary": _summarize_input(tool_name, tool_input),
        "tool_use_id": tool_use_id,
    }

    logger.info("AUDIT: %s", json.dumps(audit_entry))
    return {}


def _summarize_input(tool_name: str, tool_input: dict) -> str:
    """Create a concise summary of tool input for audit logs."""
    if tool_name == "Bash":
        return tool_input.get("command", "")[:200]
    if tool_name in ("Write", "Edit", "Read"):
        return tool_input.get("file_path", "")
    if tool_name == "Grep":
        return f"pattern='{tool_input.get('pattern', '')}'"
    if tool_name == "Glob":
        return f"pattern='{tool_input.get('pattern', '')}'"
    return str(tool_input)[:200]


@app.entrypoint
async def main(payload):
    """Agent with hook-based governance.

    PreToolUse hooks validate and block dangerous operations.
    PostToolUse hooks log all tool usage for audit.
    """
    prompt = payload["prompt"]

    options = ClaudeAgentOptions(
        system_prompt=(
            "You are a helpful assistant with access to file and shell tools. "
            "Use them to accomplish the user's request."
        ),
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        permission_mode="acceptEdits",
        hooks={
            "PreToolUse": [
                HookMatcher(
                    matcher="Bash|Write|Edit",
                    hooks=[pre_tool_guard],
                ),
            ],
            "PostToolUse": [
                HookMatcher(hooks=[post_tool_audit]),
            ],
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
