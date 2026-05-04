"""
Amazon Bedrock AgentCore Runtime entry point for the Role-Based HR Data Agent.

Reads configuration from SSM, then delegates to agent_task for async workflow.
"""

import os
import asyncio
import logging

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from agent_config.utils import get_ssm_parameter
from agent_config.agent_task import run_agent_task

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Enable OpenTelemetry console export for local debugging
os.environ.setdefault("STRANDS_OTEL_ENABLE_CONSOLE_EXPORT", "false")

app = BedrockAgentCoreApp()


@app.entrypoint
async def agent_invocation(payload: dict, context) -> dict:
    """
    AgentCore Runtime entry point.

    Reads gateway URL from SSM, validates session, then runs the agent task.
    """
    session_id = payload.get("sessionId") or (
        context.session_id if hasattr(context, "session_id") else None
    )
    if not session_id:
        return {"error": "Missing sessionId in payload"}

    gateway_url = get_ssm_parameter("/app/hrdlp/gateway-url")
    if not gateway_url:
        return {"error": "Gateway URL not found in SSM (/app/hrdlp/gateway-url)"}

    return await run_agent_task(payload, context, gateway_url, session_id)


app.run()  # nosemgrep: python.flask.security.audit.app-run-security-config.avoid_using_app_run_directly
