"""Client Communication Agent — generates personalized briefs. NEW agent built by Wealth Advisory."""

METADATA = {
    "name": "client_communication_agent",
    "description": "Generates personalized client briefs tailored to risk profile, portfolio holdings, and communication preferences",
    "protocol": "HTTP",
    "entrypoint": "client_communication_agent.py",
    "version": "1.0.0",
    "team": "Wealth Advisory",
    "capabilities": ["audience-segmentation", "tone-adaptation", "portfolio-aware-messaging"],
    "tools": [
        {"name": "generate_client_brief", "description": "Generate personalized investment brief for a client segment"},
    ],
}

from strands import Agent, tool  # noqa: E402
from strands.models import BedrockModel  # noqa: E402
from bedrock_agentcore.runtime import BedrockAgentCoreApp  # noqa: E402

app = BedrockAgentCoreApp()


@tool
def generate_client_brief(thesis: str, client_segment: str) -> str:
    """Generate personalized investment brief for a client segment."""
    briefs = {
        "conservative": """{
"segment": "conservative",
"subject": "NVTK Quarterly Update — Steady Growth with Managed Risk",
"tone": "reassuring",
"key_message": "NovaTech continues to deliver consistent, predictable growth. The 5.5% revenue increase and expanding margins from services provide a stable foundation. We recommend maintaining your current position.",
"risk_emphasis": "HIGH — detailed risk section with downside scenarios",
"action": "HOLD — maintain current allocation, no changes recommended",
"portfolio_impact": "Your NVTK position (4.2% of portfolio) remains within target allocation range"}""",
        "growth": """{
"segment": "growth",
"subject": "NVTK — Strong Conviction BUY on AI Catalyst",
"tone": "opportunity-focused",
"key_message": "NovaTech's Q1 beat signals the beginning of an AI-driven growth cycle. With conviction rating 8/10 and $89 price target (14% upside), this is an opportunity to increase exposure before the market fully prices in the AI strategy.",
"risk_emphasis": "MODERATE — risks noted but framed as entry opportunities",
"action": "BUY — consider increasing allocation by 1-2%",
"portfolio_impact": "Increasing NVTK from 6.1% to 7.5% keeps portfolio within growth mandate"}""",
        "institutional": """{
"segment": "institutional",
"subject": "NVTK Q1 FY2025 — Comprehensive Analysis & Thesis",
"tone": "technical",
"key_message": "Full quantitative analysis attached. DCF fair value $85 vs current $78.42. Conviction 8/10 driven by cross-source alignment across fundamentals, sentiment, and IP moat assessment.",
"risk_emphasis": "FULL — complete risk matrix with probability-weighted scenarios",
"action": "OVERWEIGHT — increase by 50bps relative to benchmark",
"portfolio_impact": "Appendix includes full attribution analysis and tracking error impact"}"""
    }
    return briefs.get(client_segment, briefs["growth"])


agent = Agent(
    model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0"),
    tools=[generate_client_brief],
    system_prompt="You are a client communications specialist. Generate personalized investment briefs tailored to different client segments (conservative, growth, institutional).",
)


@app.entrypoint
def invoke(payload, context=None):
    result = agent(payload.get("prompt", "Generate briefs for all client segments for NVTK"))
    return {"result": str(result)}


if __name__ == "__main__":
    app.run()
