#!/usr/bin/env python3
"""
Insurance Agent with AgentCore Services

This agent demonstrates all AgentCore primitives:
- Runtime: Serverless deployment and scaling
- Memory: Persistent conversation context
- Identity: Secure authentication (inbound & outbound)
- Gateway: MCP tool integration
- Observability: OpenTelemetry tracing
"""

import logging
import os
import uuid
from typing import Dict, List, Optional
from datetime import datetime
from dotenv import load_dotenv

# Strands Agent Framework
from strands import Agent
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client

# AgentCore Services
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore.services.identity import IdentityClient

# Observability
from opentelemetry import baggage, context

# Load environment variables
load_dotenv()

# ============================================================================
# AGENTCORE RUNTIME - Initialize the app
# ============================================================================
app = BedrockAgentCoreApp()

# ============================================================================
# CONFIGURATION
# ============================================================================
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL")
MODEL_NAME = os.getenv("MODEL_NAME", "us.anthropic.claude-3-7-sonnet-20250219-v1:0")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("InsuranceAgent")

# ============================================================================
# AGENTCORE IDENTITY - Setup authentication
# ============================================================================
def setup_identity():
    """Initialize Identity service for secure authentication"""
    try:
        identity_client = IdentityClient(region_name=AWS_REGION)
        workload_identity_arn = os.getenv("WORKLOAD_IDENTITY_ARN")
        
        if workload_identity_arn:
            logger.info(f"✓ Identity configured: {workload_identity_arn}")
            return identity_client, workload_identity_arn
        else:
            logger.warning("⚠ Identity not configured (optional)")
            return None, None
    except Exception as e:
        logger.warning(f"⚠ Identity setup failed: {e}")
        return None, None

identity_client, workload_identity_arn = setup_identity()

# ============================================================================
# AGENTCORE MEMORY - Setup persistent memory
# ============================================================================
def setup_memory():
    """Initialize Memory service for conversation persistence"""
    try:
        memory_client = MemoryClient(region_name=AWS_REGION)
        
        # ALWAYS use MEMORY_ID from environment if set (recommended)
        memory_id = os.getenv("MEMORY_ID")
        if memory_id:
            logger.info(f"✓ Using memory from MEMORY_ID: {memory_id}")
            return memory_client, {"id": memory_id}
        
        # If no MEMORY_ID, search for existing memory
        logger.info("No MEMORY_ID set, searching for existing memory...")
        try:
            existing_memories = memory_client.list_memories()
            
            # Look for any memory with "InsuranceAgentMemory" in the name
            for memory in existing_memories:
                memory_name = memory.get('name', '')
                if 'InsuranceAgentMemory' in memory_name:
                    memory_id = memory.get('id')
                    logger.info(f"✓ Found existing memory: {memory_name} ({memory_id})")
                    logger.info(f"💡 Add to .env to avoid search: MEMORY_ID=\"{memory_id}\"")
                    return memory_client, {"id": memory_id}
            
            logger.info("No existing InsuranceAgentMemory found")
        except Exception as list_error:
            logger.warning(f"⚠ Could not list memories: {list_error}")
        
        # Create memory if it doesn't exist
        # Note: In production, set MEMORY_ID in .env to avoid this
        logger.info("Creating new memory resource...")
        try:
            memory_resource = memory_client.create_memory_and_wait(
                name="InsuranceAgentMemory",
                description="Insurance agent conversation memory",
                strategies=[{
                    "userPreferenceMemoryStrategy": {
                        "name": "CustomerPreferences",
                        "description": "Customer insurance preferences and history",
                        "namespaces": ["/insurance/customers/{actorId}"]
                    }
                }]
            )
            memory_id = memory_resource.get('id')
            logger.info(f"✓ Created memory: {memory_id}")
            logger.info(f"💡 Add to .env to avoid recreation: MEMORY_ID=\"{memory_id}\"")
            return memory_client, memory_resource
        except Exception as create_error:
            if "already exists" in str(create_error):
                # Race condition - another instance created it
                logger.info("Memory created by another instance, searching...")
                try:
                    existing_memories = memory_client.list_memories()
                    for memory in existing_memories:
                        if 'InsuranceAgentMemory' in memory.get('name', ''):
                            memory_id = memory.get('id')
                            logger.info(f"✓ Found memory: {memory_id}")
                            return memory_client, {"id": memory_id}
                except:
                    pass
            logger.warning(f"⚠ Could not create memory: {create_error}")
            return None, None
        
    except Exception as e:
        logger.warning(f"⚠ Memory setup failed: {e}")
        return None, None

memory_client, memory_resource = setup_memory()

# Log memory setup status
if memory_client and memory_resource:
    logger.info(f"✓ Memory initialized: {memory_resource.get('id')}")
else:
    logger.warning("⚠ Memory not initialized - conversations will not be persisted")

# ============================================================================
# AGENTCORE GATEWAY - Setup MCP client
# ============================================================================
def get_mcp_token():
    """Get MCP access token (supports Identity integration in future)"""
    token = os.getenv("MCP_ACCESS_TOKEN")
    if not token:
        logger.warning("⚠ MCP_ACCESS_TOKEN not set")
    return token

# Create MCP client for insurance tools
insurance_mcp_client = MCPClient(
    lambda: streamablehttp_client(
        MCP_SERVER_URL,
        headers={"Authorization": f"Bearer {get_mcp_token()}"}
    )
)

# ============================================================================
# AGENT CONFIGURATION
# ============================================================================
SYSTEM_PROMPT = """
You are an auto insurance assistant that helps customers understand their insurance options.

Your goal is to provide helpful, accurate information about auto insurance products, 
customer details, vehicle information, and insurance quotes.

Use the available tools to retrieve information from the insurance database.
When providing quotes or information, be professional but conversational.
Explain insurance terms in simple language and highlight key benefits of different options.

Available tools:
x_amz_bedrock_agentcore_search - A special tool that returns a trimmed down list of tools given a context. 
Use this tool only when there are many tools available and you want to get a subset that matches the provided context.

Always verify the information with the customer and ask for clarification when needed.
Keep your responses concise and focused on answering the user's questions.

Remember previous context from the conversation when responding.
"""

# ============================================================================
# CORE AGENT LOGIC
# ============================================================================
def get_memory_context(actor_id: str, query: str) -> str:
    """Retrieve relevant memories for context"""
    if not memory_client or not memory_resource:
        return ""
    
    try:
        memories = memory_client.retrieve_memories(
            memory_id=memory_resource.get("id"),
            namespace=f"/insurance/customers/{actor_id}",
            query=query,
            max_results=3
        )
        
        if memories:
            context = "\n".join([m.get("content", "") for m in memories])
            logger.info(f"✓ Retrieved {len(memories)} memories")
            return f"\n\nPrevious context:\n{context}"
        
    except Exception as e:
        logger.warning(f"⚠ Memory retrieval failed: {e}")
    
    return ""

def save_to_memory(actor_id: str, session_id: str, user_input: str, response: str):
    """Save conversation to memory"""
    if not memory_client or not memory_resource:
        logger.warning(f"⚠ Memory not configured - skipping save (client: {memory_client is not None}, resource: {memory_resource is not None})")
        return
    
    try:
        logger.info(f"💾 Saving to memory: actor={actor_id}, session={session_id}")
        memory_client.create_event(
            memory_id=memory_resource.get("id"),
            actor_id=actor_id,
            session_id=session_id,
            messages=[
                (user_input, "USER"),
                (response, "ASSISTANT")
            ]
        )
        logger.info("✓ Saved to memory")
    except Exception as e:
        logger.warning(f"⚠ Memory save failed: {e}")

def run_agent(user_input: str, actor_id: str, session_id: str) -> str:
    """Run the insurance agent with MCP tools"""
    
    # Get memory context
    memory_context = get_memory_context(actor_id, user_input)
    enhanced_prompt = SYSTEM_PROMPT + memory_context
    
    # Connect to MCP server and get tools
    with insurance_mcp_client:
        tools = insurance_mcp_client.list_tools_sync()
        logger.info(f"✓ Connected to MCP server ({len(tools)} tools)")
        
        # Create agent with tools
        agent = Agent(
            model=MODEL_NAME,
            tools=tools,
            system_prompt=enhanced_prompt
        )
        
        # Get response
        response = agent(user_input)
        
        # Extract response text
        if isinstance(response, dict):
            response_text = response.get("content") or response.get("message", {}).get("content", str(response))
        else:
            response_text = str(response)
        
        # Save to memory
        save_to_memory(actor_id, session_id, user_input, response_text)
        
        return response_text

# ============================================================================
# AGENTCORE RUNTIME - Main entrypoint
# ============================================================================
@app.entrypoint
def main(payload: Dict) -> str:
    """
    Main entrypoint for AgentCore Runtime
    
    Args:
        payload: Request payload with user_input, actor_id, session_id
        
    Returns:
        Agent response as string
    """
    logger.info("=" * 60)
    logger.info("Insurance Agent Request")
    logger.info("=" * 60)
    
    try:
        # Extract request parameters
        user_input = payload.get("user_input", "")
        actor_id = payload.get("actor_id", "anonymous")
        session_id = payload.get("session_id", str(uuid.uuid4()))
        
        logger.info(f"User: {user_input}")
        logger.info(f"Actor: {actor_id}")
        logger.info(f"Session: {session_id}")
        
        # IDENTITY: Verify authentication (if configured)
        if workload_identity_arn:
            logger.info(f"✓ Authenticated via: {workload_identity_arn}")
        
        # OBSERVABILITY: Set session context for tracing
        ctx = baggage.set_baggage("session.id", session_id)
        context.attach(ctx)
        
        # Run the agent
        response = run_agent(user_input, actor_id, session_id)
        
        logger.info(f"Response: {response[:100]}...")
        logger.info("=" * 60)
        
        return response
        
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        logger.error(error_msg)
        return f"I'm sorry, I encountered an error. Please try again later."

# ============================================================================
# AGENTCORE RUNTIME - Start the app
# ============================================================================
if __name__ == "__main__":
    app.run()
