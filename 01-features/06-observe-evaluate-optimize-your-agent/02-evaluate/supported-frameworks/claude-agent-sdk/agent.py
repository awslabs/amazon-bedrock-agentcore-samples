"""
HR Assistant Agent — Claude Agent SDK on Bedrock AgentCore Runtime.

Demonstrates an agent built with the Claude Agent SDK (Anthropic), instrumented
for AgentCore Evaluations via openinference-instrumentation-claude-agent-sdk.

Tools (deterministic mock data for reproducible evaluations):
  get_pto_balance        - remaining PTO days for an employee
  submit_pto_request     - request time off
  lookup_hr_policy       - company policy documents
  get_benefits_summary   - health, dental, vision, 401k, life insurance details
  get_pay_stub           - pay stub for a given period

Instrumentation:
  The openinference-instrumentation-claude-agent-sdk library is auto-discovered
  by ADOT at startup — no explicit tracer code needed. Just add it to
  requirements.txt and deploy to AgentCore Runtime.
"""

import json
import logging
import os
import sys
from pathlib import Path

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from claude_agent_sdk import Agent, tool

# Add shared module to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.mock_data import (
    BENEFITS,
    HR_POLICIES,
    PAY_STUBS,
    PTO_BALANCES,
    SYSTEM_PROMPT,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()

_PTO_REQUEST_COUNTER = {"n": 0}

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool
def get_pto_balance(employee_id: str) -> str:
    """
    Return the current PTO balance for an employee.

    Args:
        employee_id: Employee identifier (e.g. EMP-001)
    """
    balance = PTO_BALANCES.get(employee_id)
    if balance:
        return json.dumps({"employee_id": employee_id, **balance})
    return json.dumps({"employee_id": employee_id, "error": f"Employee {employee_id} not found."})


@tool
def submit_pto_request(
    employee_id: str,
    start_date: str,
    end_date: str,
    reason: str = "Personal time off",
) -> str:
    """
    Submit a PTO request for an employee.

    Args:
        employee_id: Employee identifier (e.g. EMP-001)
        start_date:  First day of leave in YYYY-MM-DD format
        end_date:    Last day of leave in YYYY-MM-DD format
        reason:      Optional reason for the request
    """
    _PTO_REQUEST_COUNTER["n"] += 1
    request_id = f"PTO-2026-{_PTO_REQUEST_COUNTER['n']:03d}"
    return json.dumps({
        "request_id": request_id,
        "employee_id": employee_id,
        "start_date": start_date,
        "end_date": end_date,
        "reason": reason,
        "status": "APPROVED",
        "message": f"PTO request {request_id} approved for {employee_id} from {start_date} to {end_date}.",
    })


@tool
def lookup_hr_policy(topic: str) -> str:
    """
    Look up a company HR policy document by topic.

    Args:
        topic: Policy topic. Supported: pto, remote_work, parental_leave, code_of_conduct
    """
    key = topic.lower().replace(" ", "_").replace("-", "_")
    text = HR_POLICIES.get(key)
    if text:
        return json.dumps({"topic": topic, "policy_text": text})
    return json.dumps({
        "topic": topic,
        "error": f"Policy '{topic}' not found. Available: {list(HR_POLICIES.keys())}",
    })


@tool
def get_benefits_summary(benefit_type: str) -> str:
    """
    Return a summary of a specific employee benefit.

    Args:
        benefit_type: Type of benefit. Supported: health, dental, vision, 401k, life_insurance
    """
    key = benefit_type.lower().replace(" ", "_").replace("-", "_")
    text = BENEFITS.get(key)
    if text:
        return json.dumps({"benefit_type": benefit_type, "summary": text})
    return json.dumps({
        "benefit_type": benefit_type,
        "error": f"Benefit '{benefit_type}' not found. Available: {list(BENEFITS.keys())}",
    })


@tool
def get_pay_stub(employee_id: str, period: str) -> str:
    """
    Retrieve a pay stub for an employee for a specific pay period.

    Args:
        employee_id: Employee identifier (e.g. EMP-001)
        period:      Pay period in YYYY-MM format (e.g. 2026-01)
    """
    stub = PAY_STUBS.get((employee_id, period))
    if stub:
        return json.dumps({"employee_id": employee_id, **stub})
    return json.dumps({
        "employee_id": employee_id,
        "period": period,
        "error": f"Pay stub not found for {employee_id} period {period}.",
    })


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")

_TOOLS = [
    get_pto_balance,
    submit_pto_request,
    lookup_hr_policy,
    get_benefits_summary,
    get_pay_stub,
]


@app.entrypoint
async def invoke(payload, context):
    """Handle an agent invocation from AgentCore Runtime."""
    prompt = payload.get("prompt", "")
    session_id = context.session_id
    logger.info("Received prompt (session=%s): %s", session_id, prompt[:80])

    agent = Agent(
        model=MODEL_ID,
        tools=_TOOLS,
        system=SYSTEM_PROMPT,
    )

    response = await agent.run(prompt)
    return response.text


if __name__ == "__main__":
    app.run()
