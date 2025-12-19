"""
Travel Subagent

A subagent that handles travel-related queries by connecting to travel tools
via the gateway. Exposed as a tool for the main supervisor agent.
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
# TRAVEL AGENT SYSTEM PROMPT
# =============================================================================

TRAVEL_AGENT_PROMPT = """
You are a travel assistant designed to help users plan trips and prepare for travel.
For reference, today's date is December 3rd, 2025.

Your primary responsibilities include:
1. Providing destination information and itinerary recommendations
2. Finding flights and hotels
3. Searching for restaurants and attractions
4. Providing up-to-date travel information via internet search

You have access to the following tools:
- `travel_search`: Find up-to-date information from the internet (including weather)
- `travel_flight_search`: Search for flights (departure_id, arrival_id, outbound_date, optional return_date)
- `travel_hotel_search`: Search for hotels (query, check_in_date, check_out_date)
- `travel_places_search`: Search for restaurants, attractions, and locations via Google Places

IMPORTANT GUIDELINES:

1. Focus on the current query - maintain context from conversation history when relevant
2. For weather questions, use travel_search to find current weather information
3. For flight searches, ask for origin, destination, and dates if not provided
4. For hotel searches, ask for city, check-in/check-out dates if not provided
5. Categorize event/attraction results by type (cultural, sports, dining, etc.)
6. Include dates, times, and locations for events and attractions
7. Provide specific, actionable recommendations

ITINERARY REQUIREMENTS (CRITICAL):
- ALWAYS include at least 2-3 restaurant recommendations per day in multi-day itineraries
- EVERY location-based item (hotels, restaurants, activities, attractions) MUST include a Google Maps link
- Google Maps link format: https://www.google.com/maps/search/?api=1&query=PLACE_NAME,CITY
- For restaurants, use travel_places_search to find specific options with addresses
- Store the Google Maps link in the "location" field as: "Address - https://www.google.com/maps/search/?api=1&query=..."
- When displaying to users, format links as markdown: [Address](https://www.google.com/maps/search/?api=1&query=...)

RETRY STRATEGY:
- If a search returns no results or irrelevant results, retry with a refined query
- Try different query phrasings (e.g., "restaurants in Tokyo" vs "best dining Tokyo")
- For places search, try broader or more specific terms
- For flights/hotels, verify airport codes and date formats are correct
- Make up to 3 attempts before reporting no results found

When responding:
- Be clear and concise
- Include relevant details like prices, ratings, and locations
- Cite sources when using internet search results
- Ask clarifying questions when needed
- Format responses in an easy-to-read manner

Your goal is to help users plan successful and enjoyable trips.
"""


# =============================================================================
# GATEWAY CLIENT FOR TRAVEL TOOLS
# =============================================================================


def get_travel_tools_client() -> MCPClient:
    """Get MCPClient filtered for travel tools only."""
    return get_gateway_client("^traveltools___")


# =============================================================================
# BEDROCK MODEL
# =============================================================================

bedrock_model = BedrockModel(
    model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    region_name=REGION,
    temperature=0.2,
)


# =============================================================================
# TRAVEL SUBAGENT TOOL
# =============================================================================


@tool
async def travel_assistant(query: str, user_id: str = "", session_id: str = ""):
    """
    Process travel planning queries using specialized travel tools.

    AVAILABLE TOOLS:
    - travel_search: Internet search for travel info (query)
    - travel_places_search: Find restaurants, attractions via Google Places (query)
    - travel_hotel_search: Search hotels (query, check_in_date YYYY-MM-DD, check_out_date YYYY-MM-DD)
    - travel_flight_search: Search flights (departure_id, arrival_id as airport codes, outbound_date YYYY-MM-DD, optional return_date)

    ROUTE HERE FOR:
    - Flight searches: "Find flights from BOS to PAR on 2025-12-20"
    - Hotel searches: "Hotels in Rome from 2025-12-20 to 2025-12-25"
    - Restaurant/attraction searches: "Best sushi restaurants in Tokyo"
    - General travel info: "What to do in Barcelona", "Travel tips for Japan"
    - Trip planning: "Plan a 3-day itinerary for Madrid"

    IMPORTANT: Include specific dates (YYYY-MM-DD format) and airport codes when available.
    For flights, use 3-letter airport codes (BOS, JFK, CDG, NRT, etc.).

    Args:
        query: The travel request with as much detail as possible.
        user_id: User identifier for personalization.
        session_id: Session identifier for context.

    Returns:
        Travel information, search results, or recommendations.
        Will retry searches with refined queries if initial results are insufficient.
    """
    try:
        logger.info(f"Travel subagent (async) processing: {query[:100]}...")

        travel_client = get_travel_tools_client()

        agent = Agent(
            name="travel_agent",
            model=bedrock_model,
            tools=[travel_client],
            system_prompt=TRAVEL_AGENT_PROMPT,
            trace_attributes={
                "user.id": user_id,
                "session.id": session_id,
                "agent.type": "travel_subagent",
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
        logger.error(f"Travel subagent async error: {e}", exc_info=True)
        yield {"error": str(e)}
