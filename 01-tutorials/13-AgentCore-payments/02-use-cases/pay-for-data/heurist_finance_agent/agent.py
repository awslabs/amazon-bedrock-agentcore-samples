#!/usr/bin/env python3
"""Heurist finance agent using AgentCorePaymentsPlugin for automatic x402 payments.

The agent uses the built-in http_request tool from strands-agents-tools to call
paid Heurist endpoints. The AgentCorePaymentsPlugin intercepts HTTP 402 responses,
generates payment proofs via AgentCore payments, and retries automatically.

No manual payment logic is needed.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import boto3
from strands import Agent, tool
from strands.models import BedrockModel
from strands_tools import http_request
from strands_tools.code_interpreter import AgentCoreCodeInterpreter

from bedrock_agentcore.payments.integrations.strands import (
    AgentCorePaymentsPlugin,
    AgentCorePaymentsPluginConfig,
)

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from heurist_finance_agent.artifact_export import (
    ARTIFACTS_DIR,
    export_code_interpreter_file,
    safe_artifact_path,
)
from heurist_finance_agent.catalog import format_catalog_for_prompt, get_tools_for_agents
from heurist_finance_agent.config import get_config, load_environment

load_environment()
CFG = get_config()
CODE_INTERPRETER = AgentCoreCodeInterpreter(
    region=CFG.aws_region,
    session_name=CFG.code_interpreter_session_name,
)
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

# --- Load Heurist catalog for the system prompt ---
HEURIST_TOOLS = get_tools_for_agents(CFG.heurist_tool_agent_ids)
CATALOG_REFERENCE = format_catalog_for_prompt(HEURIST_TOOLS)


# --- Artifact helper tools ---

@tool
def export_code_interpreter_artifact(
    remote_path: str, local_filename: str | None = None, session_name: str | None = None
) -> dict[str, Any]:
    """Export a file from AgentCore Code Interpreter to the local workspace."""
    active_session = session_name or CFG.code_interpreter_session_name
    return export_code_interpreter_file(
        CODE_INTERPRETER,
        remote_path=remote_path,
        session_name=active_session,
        local_filename=local_filename,
    )


@tool
def list_exported_artifacts(limit: int = 50) -> dict[str, Any]:
    """List files already exported into the local artifacts directory."""
    items = []
    for path in sorted(ARTIFACTS_DIR.glob("*")):
        if path.is_file():
            items.append({"name": path.name, "path": str(path), "size_bytes": path.stat().st_size})
    return {"total": len(items), "items": items[:limit]}


@tool
def save_text_artifact(filename: str, content: str) -> dict[str, Any]:
    """Save text content directly into the local artifacts directory."""
    output_path = safe_artifact_path(filename)
    output_path.write_text(content)
    return {"status": "success", "path": str(output_path), "size_bytes": output_path.stat().st_size}


# --- System prompt ---

SYSTEM_PROMPT = f"""You are a finance research and data visualization agent.

You have access to paid financial data endpoints via the Heurist network. To fetch data,
use the `http_request` tool to call the endpoint URLs listed below. All endpoints accept
POST requests with JSON bodies.

**Payment is handled automatically.** When an endpoint returns HTTP 402 (Payment Required),
the system processes the payment and retries your request. You do not need to handle
payments yourself — just make the http_request call and you will receive the data.

{CATALOG_REFERENCE}

## Working Rules

- Use http_request to call the Heurist endpoints above. Always use method="POST" and
  pass the parameters as a JSON body string.
- Use AgentCore Code Interpreter to analyze data with pandas/matplotlib.
- If you create a chart or report in code_interpreter, export it with export_code_interpreter_artifact.
- For text reports, use save_text_artifact directly.
- Parallelize data fetches when possible (call multiple http_requests in the same round).
- Never fabricate or simulate market data. Only use data returned by the tools.
- If a tool call fails, report the error and stop. Do not invent fallback data.

## Code Interpreter Usage

- Start with initSession when the session is not ready.
- Use writeFiles for datasets so your code stays readable.
- Use pandas/matplotlib for analysis and plotting.
- Export every user-facing artifact to the local workspace.

Code interpreter action examples:
- init session:
  {{"action": {{"type": "initSession", "session_name": "{CFG.code_interpreter_session_name}", "description": "analysis session"}}}}
- write file:
  {{"action": {{"type": "writeFiles", "session_name": "{CFG.code_interpreter_session_name}", "content": [{{"path": "data.json", "text": "{{...}}"}}]}}}}
- execute python:
  {{"action": {{"type": "executeCode", "session_name": "{CFG.code_interpreter_session_name}", "language": "python", "code": "print(1)"}}}}

## Context

- Model: {CFG.bedrock_model_id}
- Code interpreter session: {CFG.code_interpreter_session_name}
- Export directory: {str(ARTIFACTS_DIR)!r}
- Today's date: {datetime.now().strftime("%Y-%m-%d")}
"""


def create_agent() -> Agent:
    """Build and return the Strands agent with the payments plugin."""
    bedrock_session = boto3.Session(profile_name=CFG.bedrock_profile, region_name=CFG.aws_region)
    model = BedrockModel(
        boto_session=bedrock_session,
        model_id=CFG.bedrock_model_id,
        temperature=0,
        max_tokens=CFG.agent_max_tokens,
    )

    # Configure the AgentCore payments plugin — handles x402 automatically
    payment_plugin = AgentCorePaymentsPlugin(
        config=AgentCorePaymentsPluginConfig(
            payment_manager_arn=CFG.payment_manager_arn,
            user_id=CFG.user_id,
            payment_instrument_id=CFG.payment_instrument_id,
            payment_session_id=CFG.payment_session_id,
            region=CFG.aws_region,
        )
    )

    agent = Agent(
        system_prompt=SYSTEM_PROMPT,
        model=model,
        tools=[
            http_request,
            list_exported_artifacts,
            save_text_artifact,
            export_code_interpreter_artifact,
            CODE_INTERPRETER.code_interpreter,
        ],
        plugins=[payment_plugin],
    )

    return agent


def invoke_agent(prompt: str):
    """Create an agent and run a single prompt to completion."""
    agent = create_agent()
    return agent(prompt)


def main() -> None:
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        print(invoke_agent(prompt))
        return

    agent = create_agent()
    while True:
        try:
            prompt = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not prompt or prompt.lower() in {"quit", "exit", "q"}:
            return
        print(agent(prompt))


if __name__ == "__main__":
    main()
