"""
Property Search Agent - Strands Implementation

This agent provides property search capabilities for real estate listings.
It can be run locally or deployed to Bedrock AgentCore.
"""

import os
import sys
import time
import json
from typing import Optional, List, Dict
from strands import Agent, tool
from strands.multiagent.a2a import A2AServer

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from common.utils.logging_config import (
    setup_logging,
    generate_request_id,
    log_tool_execution,
    log_error
)

# Configure structured logging
logger = setup_logging("property_search_agent", level=os.getenv("LOG_LEVEL", "INFO"), use_json=True)

# Mock property database
MOCK_PROPERTIES = [
    {
        "id": "PROP001",
        "title": "Modern Downtown Apartment",
        "location": "New York, NY",
        "price": 3500,
        "property_type": "apartment",
        "bedrooms": 2,
        "bathrooms": 2,
        "square_feet": 1200,
        "amenities": ["gym", "parking", "doorman"],
        "available": True,
        "description": "Beautiful modern apartment in the heart of downtown with stunning city views."
    },
    {
        "id": "PROP002",
        "title": "Cozy Suburban House",
        "location": "Austin, TX",
        "price": 2800,
        "property_type": "house",
        "bedrooms": 3,
        "bathrooms": 2.5,
        "square_feet": 2000,
        "amenities": ["garden", "garage", "pool"],
        "available": True,
        "description": "Spacious family home with large backyard and modern kitchen."
    },
    {
        "id": "PROP003",
        "title": "Luxury Penthouse",
        "location": "San Francisco, CA",
        "price": 8500,
        "property_type": "apartment",
        "bedrooms": 3,
        "bathrooms": 3,
        "square_feet": 2500,
        "amenities": ["gym", "concierge", "rooftop terrace", "parking"],
        "available": True,
        "description": "Exclusive penthouse with panoramic bay views and premium finishes."
    },
    {
        "id": "PROP004",
        "title": "Charming Studio Downtown",
        "location": "Boston, MA",
        "price": 1800,
        "property_type": "apartment",
        "bedrooms": 1,
        "bathrooms": 1,
        "square_feet": 600,
        "amenities": ["laundry", "heating"],
        "available": True,
        "description": "Perfect studio apartment for young professionals, close to public transit."
    },
    {
        "id": "PROP005",
        "title": "Beachfront Villa",
        "location": "Miami, FL",
        "price": 12000,
        "property_type": "house",
        "bedrooms": 5,
        "bathrooms": 4,
        "square_feet": 4000,
        "amenities": ["beach access", "pool", "garage", "smart home"],
        "available": True,
        "description": "Stunning beachfront property with direct ocean access and luxury amenities."
    },
    {
        "id": "PROP006",
        "title": "Mountain Cabin Retreat",
        "location": "Denver, CO",
        "price": 2200,
        "property_type": "house",
        "bedrooms": 2,
        "bathrooms": 2,
        "square_feet": 1400,
        "amenities": ["fireplace", "deck", "mountain views"],
        "available": False,
        "description": "Cozy mountain retreat perfect for nature lovers and outdoor enthusiasts."
    },
    {
        "id": "PROP007",
        "title": "Urban Loft",
        "location": "Seattle, WA",
        "price": 3200,
        "property_type": "apartment",
        "bedrooms": 2,
        "bathrooms": 1.5,
        "square_feet": 1100,
        "amenities": ["exposed brick", "high ceilings", "parking"],
        "available": True,
        "description": "Industrial-style loft in trendy neighborhood with modern updates."
    },
    {
        "id": "PROP008",
        "title": "Family Home with Yard",
        "location": "Portland, OR",
        "price": 3000,
        "property_type": "house",
        "bedrooms": 4,
        "bathrooms": 3,
        "square_feet": 2400,
        "amenities": ["garden", "garage", "playroom"],
        "available": True,
        "description": "Spacious family home with large yard and excellent school district."
    }
]


@tool
def search_properties(
    location: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    property_type: Optional[str] = None,
    min_bedrooms: Optional[int] = None,
    max_bedrooms: Optional[int] = None
) -> str:
    """
    Search for properties based on specified criteria.
    
    Args:
        location: City or area to search in (e.g., 'New York', 'Austin')
        min_price: Minimum monthly rent/price
        max_price: Maximum monthly rent/price
        property_type: Type of property ('apartment', 'house', 'condo')
        min_bedrooms: Minimum number of bedrooms
        max_bedrooms: Maximum number of bedrooms
    
    Returns:
        Formatted list of matching properties
    """
    request_id = generate_request_id()
    start_time = time.time()
    
    try:
        logger.info(
            f"Executing property search",
            extra={
                "event": "tool_execution_start",
                "tool_name": "search_properties",
                "agent_name": "property_search_agent",
                "request_id": request_id,
                "location": location,
                "min_price": min_price,
                "max_price": max_price,
                "property_type": property_type,
                "min_bedrooms": min_bedrooms,
                "max_bedrooms": max_bedrooms
            }
        )
        
        # Filter properties based on criteria
        filtered_properties = []
        
        for prop in MOCK_PROPERTIES:
            # Skip unavailable properties
            if not prop.get("available", False):
                continue
            
            # Apply filters
            if location and location.lower() not in prop["location"].lower():
                continue
            
            if min_price and prop["price"] < min_price:
                continue
            
            if max_price and prop["price"] > max_price:
                continue
            
            if property_type and prop["property_type"].lower() != property_type.lower():
                continue
            
            if min_bedrooms and prop["bedrooms"] < min_bedrooms:
                continue
            
            if max_bedrooms and prop["bedrooms"] > max_bedrooms:
                continue
            
            filtered_properties.append(prop)
        
        duration_ms = (time.time() - start_time) * 1000
        
        if not filtered_properties:
            log_tool_execution(
                logger,
                tool_name="search_properties",
                agent_name="property_search_agent",
                request_id=request_id,
                duration_ms=duration_ms,
                success=True
            )
            return "No properties found matching your criteria. Please try adjusting your search parameters."
        
        # Format results
        results = [f"Found {len(filtered_properties)} properties matching your criteria:\n"]
        
        for i, prop in enumerate(filtered_properties, 1):
            amenities_str = ", ".join(prop["amenities"][:3])
            if len(prop["amenities"]) > 3:
                amenities_str += f" + {len(prop['amenities']) - 3} more"
            
            result_text = (
                f"\n{i}. {prop['title']} (ID: {prop['id']})\n"
                f"   Location: {prop['location']}\n"
                f"   Price: ${prop['price']}/month\n"
                f"   Type: {prop['property_type'].title()}\n"
                f"   Bedrooms: {prop['bedrooms']} | Bathrooms: {prop['bathrooms']}\n"
                f"   Size: {prop['square_feet']} sq ft\n"
                f"   Amenities: {amenities_str}\n"
                f"   Description: {prop['description']}\n"
            )
            results.append(result_text)
        
        log_tool_execution(
            logger,
            tool_name="search_properties",
            agent_name="property_search_agent",
            request_id=request_id,
            duration_ms=duration_ms,
            success=True
        )
        
        return "".join(results)
    
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(
            logger,
            error=e,
            context="tool_execution",
            agent_name="property_search_agent",
            request_id=request_id,
            tool_name="search_properties",
            duration_ms=duration_ms
        )
        return f"Error searching for properties: {str(e)}"


@tool
def get_property_details(property_id: str) -> str:
    """
    Get detailed information about a specific property.
    
    Args:
        property_id: The unique identifier of the property (e.g., 'PROP001')
    
    Returns:
        Detailed property information
    """
    request_id = generate_request_id()
    start_time = time.time()
    
    try:
        logger.info(
            f"Fetching property details",
            extra={
                "event": "tool_execution_start",
                "tool_name": "get_property_details",
                "agent_name": "property_search_agent",
                "request_id": request_id,
                "property_id": property_id
            }
        )
        
        # Find property by ID
        property_data = None
        for prop in MOCK_PROPERTIES:
            if prop["id"].upper() == property_id.upper():
                property_data = prop
                break
        
        duration_ms = (time.time() - start_time) * 1000
        
        if not property_data:
            log_tool_execution(
                logger,
                tool_name="get_property_details",
                agent_name="property_search_agent",
                request_id=request_id,
                duration_ms=duration_ms,
                success=False,
                error="Property not found"
            )
            return f"Error: Property with ID '{property_id}' not found. Please check the ID and try again."
        
        # Format detailed property information
        amenities_list = "\n   - ".join(property_data["amenities"])
        availability_status = "✓ Available" if property_data["available"] else "✗ Not Available"
        
        details = (
            f"Property Details - {property_data['title']}\n"
            f"{'=' * 60}\n\n"
            f"Property ID: {property_data['id']}\n"
            f"Location: {property_data['location']}\n"
            f"Status: {availability_status}\n\n"
            f"PRICING:\n"
            f"  Monthly Rent: ${property_data['price']}\n\n"
            f"SPECIFICATIONS:\n"
            f"  Type: {property_data['property_type'].title()}\n"
            f"  Bedrooms: {property_data['bedrooms']}\n"
            f"  Bathrooms: {property_data['bathrooms']}\n"
            f"  Square Feet: {property_data['square_feet']}\n\n"
            f"AMENITIES:\n"
            f"   - {amenities_list}\n\n"
            f"DESCRIPTION:\n"
            f"  {property_data['description']}\n"
        )
        
        log_tool_execution(
            logger,
            tool_name="get_property_details",
            agent_name="property_search_agent",
            request_id=request_id,
            duration_ms=duration_ms,
            success=True
        )
        
        return details
    
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(
            logger,
            error=e,
            context="tool_execution",
            agent_name="property_search_agent",
            request_id=request_id,
            tool_name="get_property_details",
            duration_ms=duration_ms
        )
        return f"Error retrieving property details: {str(e)}"


def create_property_search_agent() -> Agent:
    """
    Create and configure the Property Search Agent.
    
    Returns:
        Configured Strands Agent instance
    """
    model_id = os.getenv("MODEL_ID", "us.anthropic.claude-3-5-haiku-20241022-v1:0")
    agent_name = os.getenv("AGENT_NAME", "Property Search Agent")
    agent_description = os.getenv(
        "AGENT_DESCRIPTION",
        "Searches for real estate properties based on user criteria including location, price, type, and amenities"
    )
    
    logger.info(f"Creating agent: {agent_name}")
    logger.info(f"Using model: {model_id}")
    
    agent = Agent(
        name=agent_name,
        description=agent_description,
        tools=[search_properties, get_property_details],
        model=model_id
    )
    
    return agent


def create_a2a_server() -> A2AServer:
    """
    Create and configure the A2A server for the Property Search Agent.
    
    Returns:
        Configured A2AServer instance
    """
    agent = create_property_search_agent()
    
    host = os.getenv("AGENT_HOST", "0.0.0.0")  # nosec B104 - required for container deployment
    port = int(os.getenv("AGENT_PORT", "5002"))
    version = os.getenv("AGENT_VERSION", "1.0.0")
    
    logger.info(f"Creating A2A server on {host}:{port}")
    
    # Create A2A server with agent
    a2a_server = A2AServer(
        agent=agent,
        host=host,
        port=port,
        version=version
    )
    
    return a2a_server


if __name__ == "__main__":
    # Create and start A2A server for local testing
    server = create_a2a_server()
    
    logger.info("Starting Property Search Agent A2A server...")
    logger.info(f"Agent card available at: http://{server.host}:{server.port}/.well-known/agent-card.json")
    
    # Start the server
    server.serve()
