"""Investment Thesis Generator — synthesizes all analysis into unified thesis. NEW agent built by Wealth Advisory."""

METADATA = {
    "name": "investment_thesis_generator",
    "description": "Synthesizes financial analysis, sentiment scores, and market context into a unified investment thesis with conviction ratings",
    "protocol": "HTTP",
    "entrypoint": "investment_thesis_generator.py",
    "version": "1.0.0",
    "team": "Wealth Advisory",
    "capabilities": ["multi-source-synthesis", "conviction-scoring", "risk-identification"],
    "tools": [
        {"name": "generate_thesis", "description": "Generate unified investment thesis from multiple analysis inputs"},
        {"name": "score_conviction", "description": "Calculate conviction rating based on cross-source alignment"},
    ],
}

from strands import Agent, tool  # noqa: E402
from strands.models import BedrockModel  # noqa: E402
from bedrock_agentcore.runtime import BedrockAgentCoreApp  # noqa: E402

app = BedrockAgentCoreApp()


@tool
def generate_thesis(ticker: str, financial_summary: str, sentiment_summary: str, market_context: str) -> str:
    """Generate unified investment thesis from multiple analysis inputs."""
    return f"""{{"ticker": "{ticker}",
"thesis": "NVTK presents a compelling risk-adjusted opportunity. Strong Q1 earnings beat (+5.5% revenue growth) combined with bullish sentiment (0.78 confidence) and expanding margins from services mix shift support a BUY thesis. The on-device AI strategy creates a durable competitive moat backed by 47 recent patent filings. Key risk: international revenue exposure (18%) amid geopolitical uncertainty.",
"conviction_rating": 8,
"conviction_rationale": "High cross-source alignment — financials, sentiment, and competitive position all point bullish. Deducted 2 points for international risk and elevated valuation.",
"recommendation": "BUY",
"time_horizon": "12-18 months",
"price_target": "$89",
"risk_factors": ["International revenue exposure (18%)", "Regulatory risk", "AI capex ramp impact on near-term margins"],
"supporting_evidence": ["Revenue beat consensus by 2.1%", "8/10 top analysts bullish", "Patent moat rated STRONG"]}}"""


@tool
def score_conviction(data_alignment: str) -> str:
    """Calculate conviction rating based on cross-source alignment."""
    return """{"score": 8, "max": 10,
"factors": {"financial_strength": 9, "sentiment_alignment": 8, "competitive_moat": 9, "risk_adjusted": 7},
"methodology": "Weighted average across 4 dimensions with risk penalty"}"""


agent = Agent(
    model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0"),
    tools=[generate_thesis, score_conviction],
    system_prompt="You are an investment thesis synthesizer. Combine financial analysis, sentiment data, and market context into a unified investment thesis with conviction ratings.",
)


@app.entrypoint
def invoke(payload, context=None):
    result = agent(payload.get("prompt", "Generate investment thesis for NVTK"))
    return {"result": str(result)}


if __name__ == "__main__":
    app.run()
