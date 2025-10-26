"""
Strands-based agent for weather, time, and calculator queries.

This agent is designed to be deployed to Amazon Bedrock AgentCore Runtime
where it will receive automatic OpenTelemetry instrumentation.

Uses Strands framework with Amazon Bedrock models.

When Braintrust observability is enabled (via BRAINTRUST_API_KEY env var),
the agent initializes Strands telemetry to export traces to Braintrust.
"""

import logging
import os
from typing import Any, Dict

from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


# Initialize AgentCore Runtime App
app = BedrockAgentCoreApp()


@tool
def get_weather(city: str) -> Dict[str, Any]:
    """
    Get current weather information for a given city.

    Args:
        city: The city name (e.g., 'Seattle', 'New York')

    Returns:
        Weather information including temperature, conditions, and humidity
    """
    from tools.weather_tool import get_weather as weather_impl

    logger.info(f"Getting weather for city: {city}")
    result = weather_impl(city)
    logger.debug(f"Weather result: {result}")

    return result


@tool
def get_time(timezone: str) -> Dict[str, Any]:
    """
    Get current time for a given city or timezone.

    Args:
        timezone: Timezone name (e.g., 'America/New_York', 'Europe/London') or city name

    Returns:
        Current time, date, timezone, and UTC offset information
    """
    from tools.time_tool import get_time as time_impl

    logger.info(f"Getting time for timezone: {timezone}")
    result = time_impl(timezone)
    logger.debug(f"Time result: {result}")

    return result


@tool
def calculator(
    operation: str,
    a: float,
    b: float = None
) -> Dict[str, Any]:
    """
    Perform mathematical calculations.

    Args:
        operation: The mathematical operation (add, subtract, multiply, divide, factorial)
        a: First number (or the number for factorial)
        b: Second number (not used for factorial)

    Returns:
        Calculation result with operation details
    """
    from tools.calculator_tool import calculator as calc_impl

    logger.info(f"Performing calculation: {operation}({a}, {b})")
    result = calc_impl(operation, a, b)
    logger.debug(f"Calculator result: {result}")

    return result


# Initialize Bedrock model
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
model = BedrockModel(model_id=MODEL_ID)

logger.info(f"Initializing Strands agent with model: {MODEL_ID}")


def _initialize_agent() -> Agent:
    """
    Initialize the agent with proper telemetry configuration.

    This function is called lazily to ensure environment variables
    (especially Braintrust configuration) are set before telemetry
    initialization.

    Returns:
        Configured Strands Agent instance
    """
    # Initialize Braintrust telemetry if configured
    braintrust_api_key = os.getenv("BRAINTRUST_API_KEY")
    if braintrust_api_key:
        logger.info("Braintrust observability enabled - initializing telemetry")
        try:
            from strands.telemetry import StrandsTelemetry

            strands_telemetry = StrandsTelemetry()
            strands_telemetry.setup_otlp_exporter()
            logger.info("Strands telemetry initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize Strands telemetry: {e}")
            logger.warning("Continuing without Braintrust observability")
    else:
        logger.info("Braintrust observability not configured (CloudWatch only)")

    # Create and return the agent
    agent = Agent(
        model=model,
        tools=[get_weather, get_time, calculator],
        system_prompt=(
            "You are a helpful assistant with access to weather, time, and calculator tools. "
            "Use these tools to accurately answer user questions. Always provide clear, "
            "concise responses based on the tool outputs. When using tools:\n"
            "- For weather: Use the city name directly\n"
            "- For time: Use timezone format like 'America/New_York' or city names\n"
            "- For calculator: Use operations like 'add', 'subtract', 'multiply', 'divide', or 'factorial'\n"
            "Be friendly and helpful in your responses."
        )
    )

    logger.info("Agent initialized with tools: get_weather, get_time, calculator")

    return agent


@app.entrypoint
def strands_agent_bedrock(payload: Dict[str, Any]) -> str:
    """
    Entry point for AgentCore Runtime invocation.

    This function is decorated with @app.entrypoint which makes it the entry point
    for the AgentCore Runtime. When deployed, the Runtime will automatically:
    - Add OpenTelemetry instrumentation
    - Create spans for agent execution, model calls, and tool usage
    - Export traces to CloudWatch X-Ray (always) and Braintrust (if configured)

    Args:
        payload: Input payload containing the user prompt

    Returns:
        Agent response text
    """
    user_input = payload.get("prompt", "")

    logger.info(f"Agent invoked with prompt: {user_input}")

    # Initialize agent with proper configuration (lazy initialization)
    agent = _initialize_agent()

    # Invoke the Strands agent
    response = agent(user_input)

    # Extract response text
    response_text = response.message['content'][0]['text']

    logger.info("Agent invocation completed successfully")
    logger.debug(f"Response: {response_text}")

    return response_text


if __name__ == "__main__":
    # When deployed to AgentCore Runtime, this will start the HTTP server
    # listening on port 8080 with /invocations and /ping endpoints
    app.run()
