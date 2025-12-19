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
You are a shopping assistant designed to help users find products and create packing lists for travel.
For reference, today's date is December 3rd, 2025.

Your primary responsibilities include:
1. Searching for products based on user queries
2. Generating packing lists with product recommendations
3. Providing product information including ASINs (Amazon Standard Identification Numbers)
4. Helping users find the right products for their travel needs

You have access to the following tools:
- `search_products_tool`: Search for products via Serp API Amazon search
- `generate_packing_list_tool`: Generate packing lists with product recommendations

IMPORTANT GUIDELINES:

1. When users ask about products or shopping, use the appropriate tool
2. For general product searches, use search_products_tool
3. For packing list generation, use generate_packing_list_tool
4. Always include product ASINs when available, but not in the form of raw ASINs, instead display a link to the Amazon product page, like so: https://www.amazon.com/dp/B08T1MQZRH/?th=1
5. Provide clear product descriptions and recommendations
6. Ask clarifying questions if the user's request is unclear


RETRY STRATEGY:
- If a search returns no results or irrelevant results, retry with a refined query
- For product searches, try broader or more specific terms
- Try adding or removing brand names, sizes, or features
- Make up to 3 attempts before reporting no results found

When responding:
- Be clear and helpful
- Include product details like names, descriptions, and ASINs
- Organize packing lists by category (clothing, electronics, toiletries, etc.)
- Provide context-appropriate recommendations based on the user's travel plans
- Format responses in an easy-to-read manner

Your goal is to help users find the right products for their travel needs.
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
    - search_products_tool(user_id, question): Search Amazon for products matching query
    - generate_packing_list_tool(user_id, question): Generate packing list with product recommendations

    ROUTE HERE FOR:
    - Product searches: "Find me a travel backpack", "Search for waterproof jackets"
    - Packing lists: "What do I need for a beach vacation?", "Generate packing list for Europe trip"
    - Shopping recommendations: "What products should I buy for hiking?"

    IMPORTANT: Results include ASINs and product links for adding to cart.
    Will retry searches with refined queries if initial results are insufficient.

    Args:
        query: The shopping/product request.
        user_id: User identifier for personalization.
        session_id: Session identifier for context.

    Returns:
        Product recommendations with ASINs, prices, and Amazon links.
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
