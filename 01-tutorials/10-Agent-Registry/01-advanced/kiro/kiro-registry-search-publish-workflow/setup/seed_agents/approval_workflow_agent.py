"""Approval Workflow Agent — compliance gate for POC (auto-approves)."""

METADATA = {
    "name": "approval_workflow_agent",
    "description": "Agent that orchestrates multi-step approval workflows with escalation and notification",
    "protocol": "HTTP",
    "entrypoint": "approval_workflow_agent.py",
    "version": "1.0.0",
    "team": "Compliance",
    "capabilities": ["approval-routing", "compliance-check", "escalation"],
    "tools": [
        {"name": "submit_for_compliance_review", "description": "Submit document for compliance review"},
        {"name": "check_approval_status", "description": "Check status of a compliance review"},
    ],
}

from strands import Agent, tool  # noqa: E402
from strands.models import BedrockModel  # noqa: E402
from bedrock_agentcore.runtime import BedrockAgentCoreApp  # noqa: E402

app = BedrockAgentCoreApp()


@tool
def submit_for_compliance_review(document_type: str, content_summary: str) -> str:
    """Submit a document for compliance review."""
    return f"""{{"status": "APPROVED",
"review_id": "CR-2025-00847",
"document_type": "{document_type}",
"reviewer": "Compliance Bot v2",
"checks_passed": [
  "No forward-looking statements without disclaimers",
  "Risk disclosures present",
  "No material non-public information detected",
  "Suitability disclaimers included"
],
"flags": [],
"approved_at": "2025-01-30T16:30:00Z",
"notes": "Auto-approved — all compliance checks passed"}}"""


@tool
def check_approval_status(review_id: str) -> str:
    """Check the status of a compliance review."""
    return f"""{{"review_id": "{review_id}", "status": "APPROVED",
"approved_at": "2025-01-30T16:30:00Z"}}"""


agent = Agent(
    model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0"),
    tools=[submit_for_compliance_review, check_approval_status],
    system_prompt="You are a compliance workflow agent. Submit documents for review and report approval status.",
)


@app.entrypoint
def invoke(payload, context=None):
    result = agent(payload.get("prompt", "Submit investment thesis for compliance review"))
    return {"result": str(result)}


if __name__ == "__main__":
    app.run()
