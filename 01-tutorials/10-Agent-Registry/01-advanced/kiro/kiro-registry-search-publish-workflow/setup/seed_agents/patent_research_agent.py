"""Patent Research Agent — returns static IP intelligence for POC."""

METADATA = {
    "name": "patent_research_agent",
    "description": "Agent for searching patents, prior art, and intellectual property databases",
    "protocol": "HTTP",
    "entrypoint": "patent_research_agent.py",
    "version": "1.0.0",
    "team": "R&D / Legal",
    "capabilities": ["patent-search", "prior-art-analysis", "ip-landscape"],
    "tools": [
        {"name": "search_patents", "description": "Search patent filings for a company"},
        {"name": "ip_landscape", "description": "Generate IP landscape report"},
    ],
}

from strands import Agent, tool  # noqa: E402
from strands.models import BedrockModel  # noqa: E402
from bedrock_agentcore.runtime import BedrockAgentCoreApp  # noqa: E402

app = BedrockAgentCoreApp()


@tool
def search_patents(company: str, domain: str) -> str:
    """Search patent filings for a company in a technology domain."""
    return f"""{{"company": "{company}", "domain": "{domain}",
"recent_filings": 47, "granted_last_year": 31,
"top_areas": ["neural engine architectures", "on-device ML inference", "privacy-preserving computation"],
"notable_patents": [
  {{"id": "US-2025-0012345", "title": "Efficient transformer inference on edge SoC", "filed": "2024-11-15"}},
  {{"id": "US-2025-0012890", "title": "Federated learning with differential privacy", "filed": "2024-10-22"}}
]}}"""


@tool
def ip_landscape(domain: str) -> str:
    """Generate IP landscape report for a technology area."""
    return f"""{{"domain": "{domain}",
"total_patents_filed_2024": 12840,
"top_assignees": ["NovaTech (1,247)", "Axiom Systems (1,102)", "Pinnacle Digital (987)", "Vertex Labs (834)"],
"emerging_areas": ["neuromorphic computing", "quantum-classical hybrid ML"],
"moat_assessment": "STRONG — deep patent portfolio in on-device AI creates significant barriers to entry"}}"""


agent = Agent(
    model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0"),
    tools=[search_patents, ip_landscape],
    system_prompt="You are an IP research analyst. Use your tools to assess patent landscapes and competitive tech moats.",
)


@app.entrypoint
def invoke(payload, context=None):
    result = agent(payload.get("prompt", "Analyze NovaTech's patent portfolio in AI"))
    return {"result": str(result)}


if __name__ == "__main__":
    app.run()
