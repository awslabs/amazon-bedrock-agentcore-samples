"""
Shopping Tools MCP Server

Exposes shopping/product search tools via MCP protocol using SerpAPI.
No agent logic - just pure tool implementations.
"""

import os
import logging
from typing import Dict, Any
from mcp.server import FastMCP
from serp_tools import search_products, generate_packing_list

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REGION = os.getenv("AWS_REGION")
if not REGION:
    raise ValueError("AWS_REGION environment variable is required")

# Create MCP server
mcp = FastMCP(
    "Shopping Tools", host="0.0.0.0", stateless_http=True
)  # nosec B104:standard pattern for containerized MCP servers


# =============================================================================
# MCP TOOLS - Raw tool exposure
# =============================================================================


@mcp.tool()
def single_productsearch(user_id: str, question: str) -> Dict[str, Any]:
    """
    Search for products on Amazon based on user query using SerpAPI.

    Args:
        user_id: User identifier
        question: Product search query (e.g., "waterproof hiking boots")

    Returns:
        Product search results with ASINs, product details, and formatted answer
    """
    return search_products(user_id, question)


@mcp.tool()
def generate_packinglist_with_productASINS(
    user_id: str, question: str
) -> Dict[str, Any]:
    """
    Generate a packing list with product recommendations for a trip using SerpAPI.

    Args:
        user_id: User identifier
        question: Trip details for packing list (e.g., "5-day beach vacation in Hawaii")

    Returns:
        Packing list with product recommendations, ASINs, and formatted answer
    """
    return generate_packing_list(user_id, question)


# =============================================================================
# SERVER STARTUP
# =============================================================================

if __name__ == "__main__":
    logger.info("Starting Shopping Tools MCP Server...")
    mcp.run(transport="streamable-http")
