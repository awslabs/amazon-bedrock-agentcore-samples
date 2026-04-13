"""Financial Analysis Agent — returns static financial analysis for POC."""

METADATA = {
    "name": "financial_analysis_agent",
    "description": "Agent that performs financial analysis including portfolio valuation, risk metrics, and trend analysis",
    "protocol": "HTTP",
    "entrypoint": "financial_analysis_agent.py",
    "version": "1.0.0",
    "team": "Finance",
    "capabilities": ["portfolio-valuation", "risk-assessment", "trend-analysis"],
    "tools": [
        {"name": "portfolio_valuation", "description": "Calculate valuation metrics"},
        {"name": "risk_assessment", "description": "Compute risk metrics"},
        {"name": "trend_analysis", "description": "Analyze earnings and revenue trends"},
    ],
}

from strands import Agent, tool  # noqa: E402
from strands.models import BedrockModel  # noqa: E402
from bedrock_agentcore.runtime import BedrockAgentCoreApp  # noqa: E402

app = BedrockAgentCoreApp()


@tool
def portfolio_valuation(ticker: str) -> str:
    """Calculate valuation metrics for a stock."""
    return f"""{{"ticker": "{ticker}",
"pe_ratio": 31.2, "forward_pe": 28.5, "peg_ratio": 1.8,
"price_to_book": 5.4, "ev_ebitda": 24.1,
"dcf_fair_value": "$85.00", "current_price": "$78.42",
"upside_potential": "6.5%",
"valuation_signal": "SLIGHTLY_UNDERVALUED"}}"""


@tool
def risk_assessment(ticker: str) -> str:
    """Compute risk metrics for a stock."""
    return f"""{{"ticker": "{ticker}",
"beta": 1.24, "sharpe_ratio": 1.45, "max_drawdown": "-12.3%",
"var_95": "-3.2%", "volatility_30d": "22.1%",
"risk_rating": "MODERATE",
"risk_factors": ["International revenue exposure (18%)", "Regulatory scrutiny", "AI capex ramp"]}}"""


@tool
def trend_analysis(ticker: str) -> str:
    """Analyze earnings and revenue trends."""
    return f"""{{"ticker": "{ticker}",
"revenue_trend": "5 consecutive quarters of growth",
"eps_trend": "Accelerating — 8.2% YoY growth",
"margin_trend": "Expanding — services mix shift driving gross margin improvement",
"guidance_vs_consensus": "In-line to slightly above",
"analyst_consensus": "BUY (32 buy, 8 hold, 2 sell)"}}"""


agent = Agent(
    model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0"),
    tools=[portfolio_valuation, risk_assessment, trend_analysis],
    system_prompt="You are a financial analyst. Use your tools to provide comprehensive financial analysis.",
)


@app.entrypoint
def invoke(payload, context=None):
    result = agent(payload.get("prompt", "Analyze NVTK financials"))
    return {"result": str(result)}


if __name__ == "__main__":
    app.run()
