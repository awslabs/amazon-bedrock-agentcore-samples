"""
Shopping Subagent

A subagent that handles product search and shopping-related queries by connecting
to shopping tools via the gateway. Exposed as a tool for the main supervisor agent.
"""

import os
import logging
from strands import Agent, tool
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

from gateway_client import get_gateway_client

logger = logging.getLogger(__name__)

REGION = os.getenv("AWS_REGION", "us-east-1")

# =============================================================================
# SHOPPING AGENT SYSTEM PROMPT
# =============================================================================

SHOPPING_AGENT_PROMPT = """
You are a shopping assistant designed to help users find products.
For reference, today's date is December 3rd, 2025.

Your primary responsibilities include:
1. Searching for products based on user queries
2. Providing product information including product IDs and links
3. Helping users find the right products for their needs

You have access to the following tools:
- `search_products_tool`: Search for products via Google Shopping using Serp API

IMPORTANT GUIDELINES:

1. When users ask about products or shopping, use the search_products_tool
2. Always include product links when available - products come from various retailers via Google Shopping
3. Provide clear product descriptions and recommendations
4. Ask clarifying questions if the user's request is unclear

RETRY STRATEGY:
- If a search returns no results or irrelevant results, retry with a refined query
- For product searches, try broader or more specific terms
- Try adding or removing brand names, sizes, or features
- Make up to 3 attempts before reporting no results found

When responding:
- Be clear and helpful
- Include product details like names, descriptions, prices, and links
- Format responses in an easy-to-read manner
- Products are sourced from various retailers via Google Shopping

Your goal is to help users find the right products for their needs.
"""


# =============================================================================
# GATEWAY CLIENT FOR SHOPPING TOOLS
# =============================================================================


def get_shopping_tools_client() -> MCPClient:
    """
    Get MCPClient connected to shopping tools via gateway.
    """
    return get_gateway_client("^shoppingtools___")


# =============================================================================
# BEDROCK MODEL
# =============================================================================

bedrock_model = BedrockModel(
    model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    region_name=REGION,
    temperature=0.2,
)


# =============================================================================
# SHOPPING SUBAGENT TOOL
# =============================================================================


@tool
async def shopping_assistant(query: str, user_id: str = "", session_id: str = ""):
    """
    Handle product search and shopping queries.

    AVAILABLE TOOLS:
    - search_products_tool(user_id, question): Search Google Shopping for products matching query

    ROUTE HERE FOR:
    - Product searches: "Find me a backpack", "Search for waterproof jackets", "Look for wireless headphones"
    - Shopping recommendations: "What are good running shoes?", "Show me laptops under $1000"

    IMPORTANT: Results include product IDs and links from various retailers via Google Shopping.
    Will retry searches with refined queries if initial results are insufficient.

    Args:
        query: The shopping/product request.
        user_id: User identifier for personalization.
        session_id: Session identifier for context.

    Returns:
        Product recommendations with product IDs, prices, and links from various retailers.
    """
    try:
        logger.info(f"Shopping subagent (async) processing: {query[:100]}...")

        shopping_client = get_shopping_tools_client()

        agent = Agent(
            name="shopping_agent",
            model=bedrock_model,
            tools=[shopping_client],
            system_prompt=SHOPPING_AGENT_PROMPT,
            trace_attributes={
                "user.id": user_id,
                "session.id": session_id,
                "agent.type": "shopping_subagent",
            },
        )

        result = ""
        async for event in agent.stream_async(query):
            if "data" in event:
                yield {"data": event["data"]}
            if "current_tool_use" in event:
                yield {"current_tool_use": event["current_tool_use"]}
            if "result" in event:
                result = str(event["result"])

        yield {"result": result}

    except Exception as e:
        logger.error(f"Shopping subagent async error: {e}", exc_info=True)
        yield {"error": str(e)}
