"""
Cost Optimization Agent - LLM-Powered Version
AWS cost monitoring, analysis, and optimization agent with intelligent tool selection
"""

import logging
import os
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel
from tools.cost_explorer_tools import (
    get_cost_and_usage,
    get_cost_forecast,
    detect_cost_anomalies,
    get_service_costs,
)
from tools.budget_tools import get_all_budgets

# Configuration - can be overridden via environment variables
MODEL_ID = os.getenv("MODEL_ID", "us.anthropic.claude-3-5-sonnet-20241022-v2:0")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the AgentCore Runtime App
app = BedrockAgentCoreApp()


# Define tools with proper decorators for LLM
@tool
def analyze_cost_anomalies(days: int = 7) -> str:
    """
    Detect unusual cost spikes or anomalies in AWS spending.

    Args:
        days: Number of days to analyze (default: 7)

    Returns:
        str: Detailed anomaly detection results
    """
    logger.info(f"Detecting cost anomalies for last {days} days...")
    return detect_cost_anomalies(days)


@tool
def get_budget_information() -> str:
    """
    Retrieve all AWS budgets and their current status.
    Shows budget limits, actual spend, and forecasted spend.

    Returns:
        str: Comprehensive budget status information
    """
    logger.info("Fetching budget status...")
    return get_all_budgets()


@tool
def forecast_future_costs(days_ahead: int = 30) -> str:
    """
    Predict future AWS costs using machine learning.

    Args:
        days_ahead: Number of days to forecast (default: 30)

    Returns:
        str: Cost forecast with confidence intervals
    """
    from datetime import datetime, timedelta

    logger.info(f"Generating cost forecast for next {days_ahead} days...")
    forecast_start = datetime.now().strftime("%Y-%m-%d")
    forecast_end = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    return get_cost_forecast(forecast_start, forecast_end)


@tool
def get_service_cost_breakdown(service_name: str = None, time_period: str = "LAST_30_DAYS") -> str:
    """
    Get detailed cost breakdown for AWS services.

    Args:
        service_name: Specific service name (e.g., "Amazon Bedrock", "Amazon EC2").
                     If None, returns all services.
        time_period: Time period to analyze (default: "LAST_30_DAYS")

    Returns:
        str: Service cost breakdown with totals
    """
    logger.info(f"Fetching costs for service: {service_name or 'all services'}...")
    if service_name:
        return get_service_costs(service_name, time_period)
    else:
        # Get all services and return top 10
        from datetime import datetime, timedelta
        import json

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        costs_raw = get_cost_and_usage(
            start_date, end_date, "MONTHLY", [{"Type": "DIMENSION", "Key": "SERVICE"}]
        )

        try:
            costs_data = json.loads(costs_raw)
            all_services = {}

            for result in costs_data.get("results", []):
                for group in result.get("groups", []):
                    service_name = group["keys"][0]
                    cost = group["cost"]
                    all_services[service_name] = all_services.get(service_name, 0) + cost

            sorted_services = sorted(all_services.items(), key=lambda x: x[1], reverse=True)
            top_10 = sorted_services[:10]

            response = "Top 10 Most Expensive AWS Services (Last 30 Days):\n\n"
            for i, (service, cost) in enumerate(top_10, 1):
                response += f"{i}. {service}: ${cost:.2f}\n"

            total = sum(all_services.values())
            response += f"\nTotal Cost: ${total:.2f}"
            return response
        except Exception as e:
            logger.error(f"Error parsing cost data: {e}")
            return costs_raw


@tool
def get_current_month_costs() -> str:
    """
    Get detailed daily cost breakdown for the current month.

    Returns:
        str: Daily cost breakdown with service-level details
    """
    from datetime import datetime

    logger.info("Fetching current month costs...")

    start_of_month = datetime.now().replace(day=1).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")

    return get_cost_and_usage(
        start_of_month, end_date, "DAILY", [{"Type": "DIMENSION", "Key": "SERVICE"}]
    )


# Initialize the Strands Agent with Amazon Bedrock model
# Use inference profile for cross-region access
model = BedrockModel(model_id=MODEL_ID)

agent = Agent(
    model=model,
    tools=[
        analyze_cost_anomalies,
        get_budget_information,
        forecast_future_costs,
        get_service_cost_breakdown,
        get_current_month_costs,
    ],
    system_prompt="""You are an AWS Cost Optimization Expert Assistant. Your role is to help users understand, monitor, and optimize their AWS spending.

You have access to powerful tools to:
- Detect cost anomalies and unusual spending patterns
- Retrieve budget status and forecasts
- Analyze service-level cost breakdowns
- Predict future costs using ML
- Provide current month spending details

Guidelines:
1. Always use the appropriate tools to get real data - never make up numbers
2. Provide clear, actionable insights based on the data
3. When users ask about costs, be specific about time periods and services
4. If you detect high costs or anomalies, proactively suggest optimization strategies
5. Be conversational and helpful, explaining technical concepts in simple terms
6. When multiple tools are needed, use them in logical order

Cost Optimization Best Practices to recommend:
- Review and terminate idle resources (EC2, EBS, RDS)
- Right-size over-provisioned instances based on utilization
- Use Savings Plans or Reserved Instances for predictable workloads
- Implement auto-scaling to match demand
- Move infrequently accessed data to cheaper storage tiers
- Set up budget alerts to catch cost spikes early
- Use AWS Cost Explorer regularly for trend analysis

Always be proactive in identifying cost-saving opportunities!""",
)


@app.entrypoint
async def process_request(payload):
    """
    AgentCore Runtime handler function with LLM-powered tool selection

    Args:
        payload: Event payload containing 'prompt', 'message', 'query', or 'inputText'

    Yields:
        dict: Response chunks for streaming
    """
    logger.info(f"Received request with payload keys: {payload.keys()}")

    # Extract prompt from various possible fields
    prompt = (
        payload.get("prompt")
        or payload.get("message")
        or payload.get("query")
        or payload.get("inputText")
        or payload.get("input")
    )

    if not prompt:
        yield {"error": "No prompt provided. Please include a query in your request."}
        return

    # Get user/session context
    user_id = payload.get("user_id", "default_user")
    session_id = payload.get("session_id", "default_session")

    logger.info(f"Processing query for user {user_id}, session {session_id}: {prompt}")

    try:
        # Let the LLM decide which tools to use and how to respond!
        async for event in agent.stream_async(prompt):
            if "data" in event:
                # Stream text chunks to the client
                yield {"type": "chunk", "data": event["data"]}

        # Signal completion
        yield {"type": "complete"}

    except Exception as e:
        logger.error(f"Error processing query: {str(e)}", exc_info=True)
        yield {
            "error": f"Error processing your request: {str(e)}\n\nPlease try rephrasing your question or contact support if the issue persists."
        }


# Run the AgentCore Runtime App
if __name__ == "__main__":
    logger.info(f"Starting Cost Optimization Agent with model: {MODEL_ID}")
    app.run()
