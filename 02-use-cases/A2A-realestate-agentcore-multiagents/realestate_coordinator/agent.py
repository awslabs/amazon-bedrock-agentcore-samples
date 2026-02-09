"""
Real Estate Coordinator Agent - Strands Implementation with A2A Protocol

This coordinator agent orchestrates property search and booking operations by
coordinating between specialized Property Search and Property Booking agents
using the A2A (Agent-to-Agent) protocol with OAuth bearer token authentication.

The coordinator uses the A2A client library to communicate with sub-agents
deployed on Amazon Bedrock AgentCore Runtime with OAuth 2.0 authentication.
"""

import os
import sys
import logging
import asyncio
import json
from typing import Optional
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import Message, Part, Role, TextPart

from strands import Agent, tool

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from common.utils.logging_config import setup_logging

# Configure structured logging
logger = setup_logging("realestate_coordinator", level=os.getenv("LOG_LEVEL", "INFO"), use_json=True)

# Configuration
DEFAULT_TIMEOUT = 300  # 5 minutes for A2A calls

# Global cache for A2A clients (bearer token is per-request, not cached)
_cache = {
    'search_client': None,
    'booking_client': None,
    'httpx_client': None
}

# Context variable for request-specific bearer token (works with async)
import contextvars
_bearer_token_var = contextvars.ContextVar('bearer_token', default=None)

# Also store in a simple dict as backup (for debugging)
_bearer_token_store = {'current': None}

def get_bearer_token_from_cognito():
    """Get OAuth bearer token from Cognito using client credentials flow."""
    import json
    
    # Try to get from environment variables first
    token_url = os.getenv('COGNITO_TOKEN_ENDPOINT')
    client_id = os.getenv('COGNITO_CLIENT_ID')
    client_secret = os.getenv('COGNITO_CLIENT_SECRET')
    
    if not all([token_url, client_id, client_secret]):
        # Try to load from config file as fallback
        config_file = os.path.join(os.path.dirname(__file__), '../cognito_config.json')
        if not os.path.exists(config_file):
            logger.error(f"Cognito config not found in env vars or file: {config_file}")
            raise ValueError("Cognito configuration not found")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        token_url = config['token_endpoint']
        client_id = config['client_id']
        client_secret = config['client_secret']
    
    import base64
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    
    headers = {
        'Authorization': f'Basic {credentials}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    data = {
        'grant_type': 'client_credentials',
        'scope': 'a2a-agents/invoke'
    }
    
    import requests
    response = requests.post(token_url, headers=headers, data=data, timeout=30)
    
    if response.status_code == 200:
        token_data = response.json()
        logger.info("Successfully obtained bearer token from Cognito")
        return token_data['access_token']
    else:
        logger.error(f"Failed to get token from Cognito: {response.status_code} - {response.text}")
        raise ValueError(f"Failed to obtain bearer token from Cognito: {response.status_code}")

def set_request_bearer_token(token: str):
    """Set bearer token for the current request context."""
    _bearer_token_var.set(token)
    _bearer_token_store['current'] = token  # Also store in dict as backup
    logger.info(f"Bearer token set in request context: {token[:20]}...")

def get_bearer_token():
    """Get OAuth bearer token from request context - MUST be passed from incoming request."""
    # ONLY use the bearer token from request context (passed from incoming request)
    # Do NOT generate new tokens - just pass through what we received
    if hasattr(_request_context, 'bearer_token') and _request_context.bearer_token:
        logger.info("Using bearer token from request context (passed through)")
        return _request_context.bearer_token
    
    # If no token in context, this is an error - we should always have one
    logger.error("No bearer token in request context! Token must be passed from client.")
    raise ValueError("Bearer token not found in request context. Ensure Authorization header is provided.")

def get_httpx_client():
    """Get or create httpx client with authentication headers.
    
    Uses BedrockAgentCoreContext to access the Authorization header from the incoming request
    and passes it through to sub-agent calls.
    """
    logger.info("=== get_httpx_client called ===")
    
    # Try to get Authorization header from BedrockAgentCoreContext
    try:
        from bedrock_agentcore.runtime import BedrockAgentCoreContext
        
        request_headers = BedrockAgentCoreContext.get_request_headers()
        logger.info(f"  Request headers from context: {list(request_headers.keys()) if request_headers else 'None'}")
        
        bearer_token = None
        if request_headers and 'authorization' in request_headers:
            auth_header = request_headers['authorization']
            if auth_header.startswith('Bearer '):
                bearer_token = auth_header[7:]
                logger.info(f"  ✓ Found bearer token in request context: {bearer_token[:20]}...")
        
        if not bearer_token:
            logger.warning("  No Authorization header in request context, generating from Cognito...")
            bearer_token = get_bearer_token_from_cognito()
            logger.info(f"  ✓ Generated bearer token from Cognito: {bearer_token[:20]}...")
            
    except Exception as e:
        logger.warning(f"  Could not access BedrockAgentCoreContext: {e}")
        logger.info("  Falling back to generating token from Cognito...")
        bearer_token = get_bearer_token_from_cognito()
        logger.info(f"  ✓ Generated bearer token from Cognito: {bearer_token[:20]}...")
    
    headers = {
        "Authorization": f"Bearer {bearer_token}"
    }
    
    # Create a new client each time
    client = httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT,
        headers=headers
    )
    logger.info(f"  ✓ Created httpx client with Authorization header")
    
    return client

def create_a2a_message(text: str) -> Message:
    """Create A2A message from text."""
    return Message(
        kind="message",
        role=Role.user,
        parts=[Part(TextPart(kind="text", text=text))],
        message_id=uuid4().hex,
    )

async def send_agent_message(message: str, agent_url: str, agent_name: str, cache_key: str) -> Optional[str]:
    """
    Send message to a sub-agent using A2A protocol with OAuth authentication.
    
    This uses the A2A client library with OAuth bearer token authentication
    following the A2A protocol specification.
    
    Args:
        message: The message to send
        agent_url: The agent's runtime URL
        agent_name: Name of the agent for logging
        cache_key: Cache key (not used, kept for compatibility)
        
    Returns:
        Agent's response text or error message
    """
    try:
        logger.info(f"=== send_agent_message START ===")
        logger.info(f"  Target: {agent_name}")
        logger.info(f"  Message: {message[:100]}...")
        
        # Get httpx client with bearer token from current request
        httpx_client = get_httpx_client()
        
        # Verify the Authorization header is set
        auth_header = httpx_client.headers.get('Authorization', '')
        if auth_header:
            logger.info(f"  ✓ httpx client has Authorization header: Bearer {auth_header[7:27]}...")
        else:
            logger.error(f"  ✗ httpx client missing Authorization header!")
        
        # Generate session ID for tracking
        session_id = str(uuid4())
        httpx_client.headers['X-Amzn-Bedrock-AgentCore-Runtime-Session-Id'] = session_id
        logger.info(f"  Session ID: {session_id}")
        
        # Get agent card
        logger.info(f"  Fetching agent card from {agent_url[:80]}...")
        resolver = A2ACardResolver(httpx_client=httpx_client, base_url=agent_url)
        agent_card = await resolver.get_agent_card()
        logger.info(f"  ✓ Retrieved agent card: {agent_card.name}")
        
        # Create A2A client with the httpx client that has the bearer token
        logger.info(f"  Creating A2A client...")
        config = ClientConfig(
            httpx_client=httpx_client,
            streaming=False
        )
        factory = ClientFactory(config)
        client = factory.create(agent_card)
        logger.info(f"  ✓ A2A client created")
        
        # Create A2A message
        msg = create_a2a_message(message)
        logger.info(f"  Message ID: {msg.message_id}")
        
        # Send message and get response
        logger.info(f"  Sending message to {agent_name}...")
        response_text = None
        async for event in client.send_message(msg):
            logger.info(f"  Received event type: {type(event).__name__}")
            
            if isinstance(event, Message):
                # Extract text from message parts
                logger.info(f"Received Message event from {agent_name}")
                for part in event.parts:
                    if hasattr(part, 'text'):
                        response_text = part.text
                        logger.info(f"Extracted text from Message: {response_text[:100]}...")
                        break
                
                if response_text:
                    return response_text
            
            elif isinstance(event, tuple) and len(event) == 2:
                # (Task, UpdateEvent) tuple
                task, update_event = event
                logger.info(f"Received Task/UpdateEvent tuple from {agent_name}")
                logger.debug(f"Task type: {type(task)}, Task: {task}")
                
                # Try multiple ways to extract the response
                # 1. Check if task has artifacts (this is the correct location for A2A responses)
                if hasattr(task, 'artifacts') and task.artifacts:
                    logger.debug(f"Task has {len(task.artifacts)} artifacts")
                    for artifact in task.artifacts:
                        if hasattr(artifact, 'parts') and artifact.parts:
                            for part in artifact.parts:
                                # Part is a Pydantic model with a root attribute
                                if hasattr(part, 'root') and hasattr(part.root, 'text'):
                                    response_text = part.root.text
                                    logger.info(f"Extracted from task.artifacts[].parts[].root.text")
                                    break
                                elif hasattr(part, 'text'):
                                    response_text = part.text
                                    logger.info(f"Extracted from task.artifacts[].parts[].text")
                                    break
                        if response_text:
                            break
                
                # 2. Check if task has result with text
                if not response_text and hasattr(task, 'result'):
                    result = task.result
                    logger.debug(f"Task has result: {type(result)}")
                    if hasattr(result, 'text'):
                        response_text = result.text
                        logger.info(f"Extracted from task.result.text")
                    elif hasattr(result, 'parts'):
                        for part in result.parts:
                            if hasattr(part, 'text'):
                                response_text = part.text
                                logger.info(f"Extracted from task.result.parts")
                                break
                
                # 3. Check if task has parts directly
                if not response_text and hasattr(task, 'parts'):
                    for part in task.parts:
                        if hasattr(part, 'text'):
                            response_text = part.text
                            logger.info(f"Extracted from task.parts")
                            break
                
                # 4. Check if task has text directly
                if not response_text and hasattr(task, 'text'):
                    response_text = task.text
                    logger.info(f"Extracted from task.text")
                
                # 5. Try to get from update_event
                if not response_text and update_event:
                    logger.debug(f"Checking update_event: {type(update_event)}")
                    if hasattr(update_event, 'text'):
                        response_text = update_event.text
                        logger.info(f"Extracted from update_event.text")
                
                if response_text:
                    logger.info(f"Successfully extracted response: {response_text[:100]}...")
                    return response_text
                else:
                    logger.warning(f"Could not extract text from task. Task attributes: {dir(task)}")
        
        # If no response extracted, return error
        if not response_text:
            logger.error(f"  ✗ No response text extracted from {agent_name} after processing all events")
            return f"Error: No response received from {agent_name}. The agent may have encountered an issue."
        
        logger.info(f"  ✓ Response received: {response_text[:100]}...")
        logger.info(f"=== send_agent_message END ===")
        return response_text
        
    except Exception as e:
        logger.error(f"=== send_agent_message ERROR ===")
        logger.error(f"  Agent: {agent_name}")
        logger.error(f"  Error: {e}", exc_info=True)
        return f"Error communicating with {agent_name}: {str(e)[:200]}"

@tool
async def search_properties(query: str) -> str:
    """
    Search for properties using the Property Search Agent via A2A protocol.
    
    Args:
        query: Search query (e.g., "apartments in New York under $4000")
        
    Returns:
        List of matching properties
    """
    logger.info(f"=== TOOL: search_properties called ===")
    logger.info(f"  Query: {query}")
    
    # Check if bearer token is available
    token = _bearer_token_var.get()
    backup_token = _bearer_token_store.get('current')
    logger.info(f"  Token in context var: {'YES' if token else 'NO'} ({token[:20] + '...' if token else 'None'})")
    logger.info(f"  Token in backup store: {'YES' if backup_token else 'NO'} ({backup_token[:20] + '...' if backup_token else 'None'})")
    
    search_agent_url = os.getenv("PROPERTY_SEARCH_AGENT_URL")
    
    if not search_agent_url:
        logger.error("  Property Search Agent URL not configured!")
        return "Error: Property Search Agent URL not configured. Set PROPERTY_SEARCH_AGENT_URL environment variable."
    
    logger.info(f"  Calling search agent at: {search_agent_url[:80]}...")
    
    result = await send_agent_message(
        query, 
        search_agent_url, 
        "Property Search Agent",
        'search_client'
    )
    
    logger.info(f"=== TOOL: search_properties completed ===")
    return result

@tool
async def book_property(booking_request: str) -> str:
    """
    Book a property using the Property Booking Agent via A2A protocol.
    
    Args:
        booking_request: Booking details (e.g., "Book PROP001 for John Doe, email john@example.com, phone 555-1234, move-in 2025-12-01")
        
    Returns:
        Booking confirmation or status
    """
    booking_agent_url = os.getenv("PROPERTY_BOOKING_AGENT_URL")
    
    if not booking_agent_url:
        return "Error: Property Booking Agent URL not configured. Set PROPERTY_BOOKING_AGENT_URL environment variable."
    
    return await send_agent_message(
        booking_request, 
        booking_agent_url, 
        "Property Booking Agent",
        'booking_client'
    )

@tool
async def check_booking_status(query: str) -> str:
    """
    Check booking status using the Property Booking Agent via A2A protocol.
    
    Args:
        query: Booking query (e.g., "Check status of booking BOOK-123" or "List bookings for john@example.com")
        
    Returns:
        Booking status or list of bookings
    """
    booking_agent_url = os.getenv("PROPERTY_BOOKING_AGENT_URL")
    
    if not booking_agent_url:
        return "Error: Property Booking Agent URL not configured. Set PROPERTY_BOOKING_AGENT_URL environment variable."
    
    return await send_agent_message(
        query, 
        booking_agent_url, 
        "Property Booking Agent",
        'booking_client'
    )

def create_realestate_coordinator():
    """
    Create the Real Estate Coordinator Agent.
    
    Returns:
        Configured Strands Agent instance
    """
    model_id = os.getenv("MODEL_ID", "us.anthropic.claude-3-5-haiku-20241022-v1:0")
    agent_name = os.getenv("AGENT_NAME", "Real Estate Coordinator")
    agent_description = os.getenv(
        "AGENT_DESCRIPTION",
        "Coordinates property search and booking operations by orchestrating specialized agents via A2A protocol with OAuth"
    )
    
    system_prompt = """You are a Real Estate Coordinator Agent that helps users find and book properties.

You coordinate between two specialized agents using A2A protocol with OAuth authentication:
1. **Property Search Agent**: Searches for properties based on criteria (location, price, type, bedrooms)
2. **Property Booking Agent**: Handles bookings, reservations, and booking status checks

Your role:
- Understand user requests about real estate
- Route requests to the appropriate agent(s) via A2A protocol
- Combine information from multiple agents when needed
- Provide clear, helpful responses

Guidelines:
- For property searches, use the search_properties tool
- For booking properties, use the book_property tool
- For checking bookings, use the check_booking_status tool
- You can use multiple tools in sequence (e.g., search then book)
- Always provide clear, actionable information to users

Example workflows:
- User wants to find apartments → Use search_properties
- User wants to book a property → Use book_property
- User wants to check their bookings → Use check_booking_status
- User wants to find and book → Use search_properties first, then book_property

All communication with sub-agents uses A2A protocol with OAuth bearer token authentication.
"""
    
    logger.info(f"Creating agent: {agent_name}")
    logger.info(f"Using model: {model_id}")
    
    agent = Agent(
        system_prompt=system_prompt,
        description=agent_description,
        tools=[search_properties, book_property, check_booking_status],
        model=model_id
    )
    
    return agent

# Cleanup on shutdown
async def cleanup():
    """Clean up resources."""
    if _cache.get('httpx_client'):
        await _cache['httpx_client'].aclose()
    
    _cache['bearer_token'] = None
    _cache['search_client'] = None
    _cache['booking_client'] = None
    _cache['httpx_client'] = None
    logger.info("A2A clients and resources cleaned up")
