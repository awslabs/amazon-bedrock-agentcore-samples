"""
Strands-based agent for weather, time, and calculator queries.

This agent is designed to be deployed to Amazon Bedrock AgentCore Runtime
where it will receive automatic OpenTelemetry instrumentation.
"""

import logging
from typing import Any, Dict, List, Optional

from anthropic import Anthropic
from pydantic import BaseModel, Field


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


# Tool schemas (must match strands_agent_config.json)
TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "name": "get_weather",
        "description": "Get current weather information for a given city",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "The city name (e.g., 'Seattle', 'New York')"
                }
            },
            "required": ["city"]
        }
    },
    {
        "name": "get_time",
        "description": "Get current time for a given city or timezone",
        "input_schema": {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "Timezone name (e.g., 'America/New_York', 'Europe/London') or city name"
                }
            },
            "required": ["timezone"]
        }
    },
    {
        "name": "calculator",
        "description": "Perform mathematical calculations",
        "input_schema": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["add", "subtract", "multiply", "divide", "factorial"],
                    "description": "The mathematical operation to perform"
                },
                "a": {
                    "type": "number",
                    "description": "First number (or the number for factorial)"
                },
                "b": {
                    "type": "number",
                    "description": "Second number (not used for factorial)"
                }
            },
            "required": ["operation", "a"]
        }
    }
]


class WeatherTimeAgent:
    """
    Strands-based agent with weather, time, and calculator tools.

    This agent uses Claude with function calling to process user queries
    and invoke appropriate tools. When deployed to AgentCore Runtime,
    it receives automatic OTEL instrumentation.
    """

    def __init__(
        self,
        model_id: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        anthropic_api_key: Optional[str] = None
    ):
        """
        Initialize the agent.

        Args:
            model_id: Bedrock model ID to use
            anthropic_api_key: Anthropic API key (optional, uses env var if not provided)
        """
        self.model_id = model_id
        self.client = Anthropic(api_key=anthropic_api_key)
        self.system_prompt = (
            "You are a helpful assistant with access to weather, time, and calculator tools. "
            "Use these tools to accurately answer user questions. "
            "Always provide clear, concise responses based on the tool outputs."
        )

        logger.info(f"Initialized WeatherTimeAgent with model: {model_id}")


    def _execute_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a tool call.

        When deployed to AgentCore Runtime, tool calls are routed through
        AgentCore Gateway. In local testing, we import tools directly.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Tool input parameters

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool is not found
        """
        logger.info(f"Executing tool: {tool_name}")
        logger.debug(f"Tool input: {tool_input}")

        # Import tools (in AgentCore Runtime, these would be MCP tools via Gateway)
        from tools import get_weather, get_time, calculator

        try:
            if tool_name == "get_weather":
                result = get_weather(city=tool_input["city"])

            elif tool_name == "get_time":
                result = get_time(timezone=tool_input["timezone"])

            elif tool_name == "calculator":
                result = calculator(
                    operation=tool_input["operation"],
                    a=tool_input["a"],
                    b=tool_input.get("b")
                )

            else:
                raise ValueError(f"Unknown tool: {tool_name}")

            logger.info(f"Tool {tool_name} executed successfully")
            logger.debug(f"Tool result: {result}")

            return result

        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return {
                "error": str(e),
                "tool_name": tool_name,
                "tool_input": tool_input
            }


    def run(
        self,
        query: str,
        max_iterations: int = 5
    ) -> str:
        """
        Run the agent with a user query.

        Uses agentic loop:
        1. Send query to Claude with tools
        2. If Claude wants to use a tool, execute it
        3. Send tool result back to Claude
        4. Repeat until Claude provides final answer

        Args:
            query: User query
            max_iterations: Maximum number of iterations to prevent infinite loops

        Returns:
            Final agent response

        Raises:
            RuntimeError: If max iterations exceeded
        """
        logger.info(f"Agent run started with query: {query}")

        messages = [{"role": "user", "content": query}]
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            logger.debug(f"Iteration {iteration}/{max_iterations}")

            # Call Claude with tools
            response = self.client.messages.create(
                model=self.model_id,
                max_tokens=2048,
                system=self.system_prompt,
                messages=messages,
                tools=TOOL_SCHEMAS
            )

            # Check stop reason
            if response.stop_reason == "end_turn":
                # Final answer
                final_text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        final_text += block.text

                logger.info("Agent run completed successfully")
                return final_text

            elif response.stop_reason == "tool_use":
                # Execute tool calls
                assistant_message = {"role": "assistant", "content": response.content}
                messages.append(assistant_message)

                tool_results = []

                for block in response.content:
                    if block.type == "tool_use":
                        logger.info(f"Claude wants to use tool: {block.name}")

                        # Execute tool
                        tool_result = self._execute_tool(
                            tool_name=block.name,
                            tool_input=block.input
                        )

                        # Add tool result to messages
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(tool_result)
                        })

                # Add all tool results as a user message
                messages.append({"role": "user", "content": tool_results})

            else:
                # Unexpected stop reason
                logger.warning(f"Unexpected stop reason: {response.stop_reason}")
                return f"Unexpected stop reason: {response.stop_reason}"

        # Max iterations exceeded
        error_msg = f"Max iterations ({max_iterations}) exceeded"
        logger.error(error_msg)
        raise RuntimeError(error_msg)


def main():
    """
    Test the agent locally.

    For production deployment, use simple_observability.py which invokes
    the agent via AgentCore Runtime.
    """
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m agent.weather_time_agent <query>")
        print("\nExample:")
        print("  python -m agent.weather_time_agent \"What's the weather in Seattle?\"")
        sys.exit(1)

    query = " ".join(sys.argv[1:])

    agent = WeatherTimeAgent()
    response = agent.run(query)

    print("\n" + "=" * 80)
    print("AGENT RESPONSE:")
    print("=" * 80)
    print(response)
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
