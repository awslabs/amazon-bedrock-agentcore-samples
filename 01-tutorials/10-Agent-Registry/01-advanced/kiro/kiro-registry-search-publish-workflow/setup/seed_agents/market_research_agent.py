"""Market Research Agent — returns static market context for POC."""

METADATA = {
    "name": "market_research_agent",
    "description": "Agent for conducting market research, competitor analysis, and industry trend reports",
    "protocol": "HTTP",
    "entrypoint": "market_research_agent.py",
    "version": "1.0.0",
    "team": "Strategy",
    "capabilities": ["market-research", "competitor-analysis", "trend-reports"],
    "tools": [
        {"name": "competitor_analysis", "description": "Analyze competitors in a sector"},
        {"name": "industry_trends", "description": "Get industry trend analysis"},
    ],
}

from strands import Agent, tool  # noqa: E402
from strands.models import BedrockModel  # noqa: E402
from bedrock_agentcore.runtime import BedrockAgentCoreApp  # noqa: E402

app = BedrockAgentCoreApp()


@tool
def competitor_analysis(sector: str) -> str:
    """Analyze competitors in a sector."""
    return f"""{{"sector": "{sector}",
"competitors": [
  {{"name": "Axiom Systems", "market_share": "19.4%", "trend": "stable"}},
  {{"name": "Pinnacle Digital", "market_share": "12.1%", "trend": "growing"}},
  {{"name": "Vertex Labs", "market_share": "8.7%", "trend": "growing"}}
],
"key_moves": ["Axiom expanding AI chip fab", "Pinnacle launching enterprise AI tier"]}}"""


@tool
def industry_trends(sector: str) -> str:
    """Get industry trend analysis."""
    return f"""{{"sector": "{sector}",
"trends": [
  {{"trend": "On-device AI", "impact": "HIGH", "timeline": "12-18 months"}},
  {{"trend": "Edge computing integration", "impact": "MEDIUM", "timeline": "24-36 months"}},
  {{"trend": "Sustainability regulations", "impact": "MEDIUM", "timeline": "6-12 months"}}
],
"macro_outlook": "Cautiously optimistic — enterprise spending resilient, AI adoption accelerating"}}"""


agent = Agent(
    model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0"),
    tools=[competitor_analysis, industry_trends],
    system_prompt="You are a market research analyst. Use your tools to provide market context and competitive intelligence.",
)


@app.entrypoint
def invoke(payload, context=None):
    result = agent(payload.get("prompt", "Analyze the tech sector"))
    return {"result": str(result)}


if __name__ == "__main__":
    app.run()
