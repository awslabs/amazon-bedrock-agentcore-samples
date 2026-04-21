"""Data Retrieval Agent — returns static financial data for POC."""

METADATA = {
    "name": "data_retrieval_agent",
    "description": "Agent for retrieving financial data from databases, APIs, and data lakes",
    "protocol": "HTTP",
    "entrypoint": "data_retrieval_agent.py",
    "version": "1.0.0",
    "team": "Data Engineering",
    "capabilities": ["earnings-data", "price-history", "sec-filings"],
    "tools": [
        {"name": "query_earnings", "description": "Retrieve quarterly earnings data for a ticker"},
        {"name": "query_price_history", "description": "Retrieve recent price history"},
        {"name": "query_sec_filings", "description": "Retrieve recent SEC filings"},
    ],
}

from strands import Agent, tool  # noqa: E402
from strands.models import BedrockModel  # noqa: E402
from bedrock_agentcore.runtime import BedrockAgentCoreApp  # noqa: E402

app = BedrockAgentCoreApp()


@tool
def query_earnings(ticker: str, quarter: str) -> str:
    """Retrieve quarterly earnings data for a ticker."""
    return f"""{{"ticker": "{ticker}", "quarter": "{quarter}",
"revenue": "$14.2B", "eps": "$3.87", "revenue_growth": "5.5%",
"net_income": "$3.1B", "gross_margin": "44.8%",
"guidance": "Q2 revenue $13.5-14.5B"}}"""


@tool
def query_price_history(ticker: str, days: int = 30) -> str:
    """Retrieve recent price history for a ticker."""
    return f"""{{"ticker": "{ticker}", "period": "{days}d",
"current": "$78.42", "high_30d": "$82.15", "low_30d": "$73.60",
"avg_volume": "12.8M", "change_30d": "+4.8%"}}"""


@tool
def query_sec_filings(ticker: str) -> str:
    """Retrieve recent SEC filings for a ticker."""
    return f"""{{"ticker": "{ticker}",
"filings": [{{"type": "10-Q", "date": "2025-01-30", "summary": "Quarterly report filed"}},
{{"type": "8-K", "date": "2025-01-28", "summary": "Earnings press release"}}]}}"""


agent = Agent(
    model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0"),
    tools=[query_earnings, query_price_history, query_sec_filings],
    system_prompt="You are a data retrieval specialist. Use your tools to fetch financial data.",
)


@app.entrypoint
def invoke(payload, context=None):
    result = agent(payload.get("prompt", "Get NVTK earnings data"))
    return {"result": str(result)}


if __name__ == "__main__":
    app.run()
