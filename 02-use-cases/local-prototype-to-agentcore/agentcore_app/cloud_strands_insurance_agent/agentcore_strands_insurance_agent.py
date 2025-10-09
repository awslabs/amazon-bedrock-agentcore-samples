#!/usr/bin/env python3
"""
Insurance Agent with AWS Bedrock AgentCore

This demonstrates how to build production-ready agents using AgentCore services:
- Runtime: Serverless deployment with auto-scaling
- Memory: Persistent conversation history
- Identity: Secure credential management
- Gateway: MCP tool integration
- Observability: Built-in tracing and monitoring
"""

import logging
import os
import uuid
from typing import Dict
from dotenv import load_dotenv

# Strands Agent Framework
from strands import Agent
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client

# AgentCore Services - Import the services you need
from bedrock_agentcore.runtime import BedrockAgentCoreApp  # Serverless deployment
from bedrock_agentcore.memory import MemoryClient          # Conversation persistence
from bedrock_agentcore.services.identity import IdentityClient  # Secure auth

# Observability - OpenTelemetry for distributed tracing
from opentelemetry import baggage, context

load_dotenv()

# ============================================================================
# AGENTCORE RUNTIME - Initialize the serverless app
# ============================================================================
# BedrockAgentCoreApp handles:
# - Lambda function deployment and scaling
# - Request/response handling
# - Integration with other AgentCore services
# - Automatic CloudWatch logging
app = BedrockAgentCoreApp()

# ============================================================================
# CONFIGURATION - Environment variables
# ============================================================================
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL")  # AgentCore Gateway endpoint
MODEL_NAME = os.getenv("MODEL_NAME", "us.anthropic.claude-3-7-sonnet-20250219-v1:0")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("InsuranceAgent")

# ============================================================================
# AGENTCORE IDENTITY - Secure credential management
# ============================================================================
# Identity provides two authentication patterns:
# 1. INBOUND: Workload Identity - Authenticates your agent (who is calling)
# 2. OUTBOUND: API Key Provider - Stores credentials for external APIs
#
# Benefits:
# - Centralized credential storage (no hardcoded secrets)
# - Automatic credential rotation
# - Fine-grained access control
# - Audit logging

def setup_identity():
    """Initialize Identity service for authentication"""
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
# AGENTCORE MEMORY - Persistent conversation storage
# ============================================================================
# Memory stores conversation history and user preferences across sessions.
#
# Key features:
# - Event Memory: Stores conversation turns (user/assistant messages)
# - Semantic Memory: Retrieves relevant context based on query similarity
# - User Preferences: Tracks customer preferences over time
# - Namespaces: Organize memories by customer (/insurance/customers/{actorId})
#
# Best practice: Set MEMORY_ID in .env to reuse existing memory

_memory_client = None
_memory_resource = None
_memory_initialized = False

def setup_memory():
    """Initialize Memory service (lazy initialization for performance)"""
    global _memory_client, _memory_resource, _memory_initialized
    
    if _memory_initialized:
        return _memory_client, _memory_resource
    
    _memory_initialized = True
    
    try:
        memory_client = MemoryClient(region_name=AWS_REGION)
        
        # Best practice: Use MEMORY_ID from .env to avoid searching/creating
        memory_id = os.getenv("MEMORY_ID")
        if memory_id:
            logger.info(f"✓ Using memory from MEMORY_ID: {memory_id}")
            return memory_client, {"id": memory_id}
        
        # Fallback: Search for existing memory
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
        
        # Create new memory if none exists
        logger.info("Creating new memory resource...")
        try:
            memory_resource = memory_client.create_memory_and_wait(
                name="InsuranceAgentMemory",
                description="Insurance agent conversation memory",
                strategies=[{
                    "userPreferenceMemoryStrategy": {  # Tracks user preferences
                        "name": "CustomerPreferences",
                        "description": "Customer insurance preferences and history",
                        "namespaces": ["/insurance/customers/{actorId}"]  # Per-customer storage
                    }
                }]
            )
            memory_id = memory_resource.get('id')
            logger.info(f"✓ Created memory: {memory_id}")
            logger.info(f"💡 Add to .env to avoid recreation: MEMORY_ID=\"{memory_id}\"")
            _memory_client = memory_client
            _memory_resource = memory_resource
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
                            _memory_client = memory_client
                            _memory_resource = {"id": memory_id}
                            return memory_client, {"id": memory_id}
                except:
                    pass
            logger.warning(f"⚠ Could not create memory: {create_error}")
            return None, None
        
    except Exception as e:
        logger.warning(f"⚠ Memory setup failed: {e}")
        return None, None

# Memory will be initialized lazily on first use (not at module load time)

# ============================================================================
# AGENTCORE GATEWAY - MCP tool integration
# ============================================================================
# Gateway exposes your APIs as MCP tools that agents can use.
#
# How it works:
# 1. Gateway reads your OpenAPI spec
# 2. Converts API endpoints to MCP tools
# 3. Handles OAuth authentication
# 4. Provides tools to your agent
#
# Benefits:
# - No custom tool code needed
# - Automatic API-to-tool conversion
# - Built-in authentication
# - Centralized API management

def get_mcp_token():
    """Get OAuth token for Gateway authentication"""
    token = os.getenv("MCP_ACCESS_TOKEN")
    if not token:
        logger.warning("⚠ MCP_ACCESS_TOKEN not set")
    return token

# Connect to Gateway to access insurance API tools
insurance_mcp_client = MCPClient(
    lambda: streamablehttp_client(
        MCP_SERVER_URL,
        headers={"Authorization": f"Bearer {get_mcp_token()}"}
    )
)

# ============================================================================
# AGENT CONFIGURATION - System prompt and behavior
# ============================================================================
# Define how your agent behaves and what it can do

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
# CORE AGENT LOGIC - Memory retrieval and agent execution
# ============================================================================

def get_memory_context(actor_id: str, query: str) -> str:
    """Retrieve relevant conversation history from Memory"""
    memory_client, memory_resource = setup_memory()
    
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
    """Save conversation turn to Memory for future context"""
    memory_client, memory_resource = setup_memory()
    
    if not memory_client or not memory_resource:
        logger.warning(f"⚠ Memory not configured - skipping save")
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
    """Execute the agent with Memory context and Gateway tools"""
    
    # 1. MEMORY: Get relevant conversation history
    memory_context = get_memory_context(actor_id, user_input)
    enhanced_prompt = SYSTEM_PROMPT + memory_context
    
    # 2. GATEWAY: Connect and get available tools
    with insurance_mcp_client:
        tools = insurance_mcp_client.list_tools_sync()
        logger.info(f"✓ Connected to MCP server ({len(tools)} tools)")
        
        # 3. Create agent with tools and context
        agent = Agent(
            model=MODEL_NAME,
            tools=tools,
            system_prompt=enhanced_prompt
        )
        
        # 4. Get agent response
        response = agent(user_input)
        
        # Extract response text
        if isinstance(response, dict):
            response_text = response.get("content") or response.get("message", {}).get("content", str(response))
        else:
            response_text = str(response)
        
        # 5. MEMORY: Save conversation for future context
        save_to_memory(actor_id, session_id, user_input, response_text)
        
        return response_text

# ============================================================================
# AGENTCORE RUNTIME - Request handler
# ============================================================================
# The @app.entrypoint decorator marks this as the Lambda handler.
# Runtime automatically:
# - Deploys as Lambda function
# - Handles request/response
# - Integrates with CloudWatch
# - Enables distributed tracing

@app.entrypoint
def main(payload: Dict) -> str:
    """
    Main request handler - invoked by AgentCore Runtime
    
    Args:
        payload: {"user_input": str, "actor_id": str, "session_id": str}
        
    Returns:
        Agent response string
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
        
        # OBSERVABILITY: Set session context for distributed tracing
        ctx = baggage.set_baggage("session.id", session_id)
        context.attach(ctx)
        
        # Execute agent
        response = run_agent(user_input, actor_id, session_id)
        
        logger.info(f"Response: {response[:100]}...")
        logger.info("=" * 60)
        
        return response
        
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        logger.error(error_msg)
        return f"I'm sorry, I encountered an error. Please try again later."

# ============================================================================
# AGENTCORE RUNTIME - Start the application
# ============================================================================
# app.run() starts the Lambda handler
# When deployed: Handles Lambda events
# When local: Runs development server for testing

if __name__ == "__main__":
    app.run()
