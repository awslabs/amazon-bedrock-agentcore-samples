"""
AI Chatbot with Lambda Web Adapter - OPTIMIZED WITH DYNAMODB PERSISTENCE
Minimal FastAPI application with Strands Agent and BAC Gateway MCP tools
Optimized for performance with DynamoDB conversation persistence and ephemeral agents
"""
import os
import json
import uuid
import logging
import asyncio
import requests
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Strands SDK imports
from strands import Agent, tool
from strands.models import BedrockModel

# Import Strands MCP client and conversation manager
from mcp_client import StrandsMCPClient
from conversation_manager import ConversationManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-3-7-sonnet-20250219-v1:0")
BEDROCK_REGION = os.environ.get("BEDROCK_REGION", "us-east-1")
DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "ai-chatbot-conversations")
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 4000

# Global variables
strands_mcp_client = None
conversation_manager = None

# MCP Tools caching
_mcp_tools_cache = None
_mcp_tools_cache_time = None
MCP_CACHE_DURATION_SECONDS = 900  # 5 minutes

# Define local tools
@tool(name="get_current_time", description="Get the current date and time")
def get_current_time() -> str:
    """Get current timestamp"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

@tool(name="echo_message", description="Echo back a message for testing")
def echo_message(message: str) -> str:
    """Echo back the provided message"""
    return f"Echo: {message}"

def get_cached_mcp_tools():
    """Get MCP tools with caching to improve performance"""
    global _mcp_tools_cache, _mcp_tools_cache_time
    current_time = datetime.now()
    
    # Check if cache is valid (within cache duration)
    if (_mcp_tools_cache is None or 
        _mcp_tools_cache_time is None or 
        (current_time - _mcp_tools_cache_time).total_seconds() > MCP_CACHE_DURATION_SECONDS):
        
        logger.info("Refreshing MCP tools cache")
        try:
            if strands_mcp_client and strands_mcp_client.is_ready():
                logger.info(f"MCP client is ready, gateway URL: {strands_mcp_client.gateway_url}")
                _mcp_tools_cache = strands_mcp_client.get_mcp_tools_for_agent()
                _mcp_tools_cache_time = current_time
                logger.info(f"Cached {len(_mcp_tools_cache)} MCP tools")
                if _mcp_tools_cache:
                    logger.info(f"First MCP tool type: {type(_mcp_tools_cache[0]).__name__}")
            else:
                _mcp_tools_cache = []
                _mcp_tools_cache_time = current_time
                ready_status = strands_mcp_client.is_ready() if strands_mcp_client else "No client"
                logger.warning(f"MCP client not ready, using empty tools cache. Ready status: {ready_status}")
        except Exception as e:
            logger.error(f"Error refreshing MCP tools cache: {str(e)}")
            _mcp_tools_cache = []
            _mcp_tools_cache_time = current_time
    
    return _mcp_tools_cache or []

def create_bedrock_model(temperature: float = DEFAULT_TEMPERATURE, max_tokens: int = DEFAULT_MAX_TOKENS) -> BedrockModel:
    """Create a BedrockModel with specified parameters"""
    return BedrockModel(
        region_name=BEDROCK_REGION,
        model_id=BEDROCK_MODEL_ID,
        temperature=temperature,
        max_tokens=max_tokens,
        system_prompt="You are an AWS Operational Support Agent with read-only access to AWS resources through BAC Gateway tools.\n\nWhen using AWS tools, be very clear and crisp in your natural language queries. Ask only for the minimum required information needed to answer the user's question. Use concise, specific queries like:\n- 'list running instances' (not 'show me all the EC2 instances with their details and configurations')\n- 'count S3 buckets' (not 'give me comprehensive information about all S3 buckets')\n- 'show failed stacks' (not 'list all CloudFormation stacks with their complete status information')\n\nAvailable AWS Services: EC2, S3, Lambda, CloudFormation, IAM, RDS, CloudWatch, Cost Explorer, ECS, EKS, SNS, SQS, DynamoDB, Route53, API Gateway, SES, Bedrock, SageMaker.\n\nProvide clear, structured responses focusing on the specific information requested by the user."
    )

def create_agent_for_request(
    conversation_history: list = None, 
    use_mcp_tools: bool = False, 
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS
) -> Agent:
    """Create a fresh agent for each request to avoid state pollution and race conditions"""
    
    # Create model with request-specific parameters
    model = create_bedrock_model(temperature=temperature, max_tokens=max_tokens)
    
    # Determine tools to use
    tools = [get_current_time, echo_message]
    if use_mcp_tools:
        mcp_tools = get_cached_mcp_tools()
        
        # Log detailed information about MCP tools
        logger.info(f"Got {len(mcp_tools)} MCP tools from cache")
        for i, tool in enumerate(mcp_tools[:5]):  # Log first 5 tools
            try:
                tool_name = getattr(tool, 'name', None) or getattr(tool, '_name', None) or str(tool)
                logger.info(f"MCP Tool {i}: name={tool_name}, type={type(tool).__name__}, length={len(tool_name)}")
                if '___' in tool_name:
                    prefix, operation = tool_name.split('___', 1)
                    logger.info(f"  - MCP Tool name has prefix: prefix={prefix}, operation={operation}")
            except Exception as e:
                logger.error(f"Error logging MCP tool: {str(e)}")
        
        tools.extend(mcp_tools)
        logger.info(f"Agent created with {len(tools)} tools ({len(mcp_tools)} MCP tools)")
    else:
        logger.info(f"Agent created with {len(tools)} local tools only")
    
    # Create fresh agent instance
    agent = Agent(model=model, tools=tools)
    
    # Set conversation history if provided
    if conversation_history:
        agent.messages = [
            {"role": msg["role"], "content": [{"text": msg["content"]}]}
            for msg in conversation_history
        ]
        logger.info(f"Agent initialized with {len(conversation_history)} conversation messages")
    
    return agent

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    global strands_mcp_client, conversation_manager
    
    # Startup
    logger.info("Starting AI Chatbot API with DynamoDB persistence...")
    
    # Initialize conversation manager
    conversation_manager = ConversationManager(
        table_name=DYNAMODB_TABLE_NAME,
        region=BEDROCK_REGION
    )
    
    # Initialize Strands MCP client
    strands_mcp_client = StrandsMCPClient()
    await strands_mcp_client.initialize()
    
    logger.info("AI Chatbot API ready with DynamoDB persistence")
    yield
    
    # Shutdown
    if strands_mcp_client:
        await strands_mcp_client.close()
        logger.info("MCP client closed")

# Initialize FastAPI app
app = FastAPI(title="AI Chatbot API", version="3.2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Request model with consistent defaults
class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    temperature: Optional[float] = DEFAULT_TEMPERATURE
    max_tokens: Optional[int] = DEFAULT_MAX_TOKENS
    use_tools: Optional[bool] = True
    okta_token: Optional[str] = None

# API Endpoints

@app.get("/")
@app.get("/health")
async def health():
    """Health check and root endpoint"""
    cache_status = "valid" if _mcp_tools_cache_time and (datetime.now() - _mcp_tools_cache_time).total_seconds() < MCP_CACHE_DURATION_SECONDS else "expired"
    return {
        "status": "healthy",
        "version": "3.3.0",
        "model": BEDROCK_MODEL_ID,
        "mcp_ready": strands_mcp_client.is_ready() if strands_mcp_client else False,
        "dynamodb_table": DYNAMODB_TABLE_NAME,
        "conversation_manager_ready": conversation_manager is not None,
        "mcp_tools_cache": {
            "status": cache_status,
            "tools_count": len(_mcp_tools_cache) if _mcp_tools_cache else 0,
            "last_refresh": _mcp_tools_cache_time.isoformat() if _mcp_tools_cache_time else None
        }
    }

@app.post("/")

@app.post("/stream")
async def stream(request: Request):
    """Streaming chat endpoint with DynamoDB persistence"""
    try:
        body = await request.json()
        message = body.get("message", "")
        conversation_id = body.get("conversation_id")
        temperature = body.get("temperature", DEFAULT_TEMPERATURE)
        max_tokens = body.get("max_tokens", DEFAULT_MAX_TOKENS)
        use_tools = body.get("use_tools", True)
        okta_token = body.get("okta_token")
        
        if not message:
            return {"error": "Message is required"}
        
        # Generate conversation ID if not provided
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
        
        # Load conversation history from DynamoDB
        conversation_history = await conversation_manager.get_conversation_history(conversation_id)
        
        # Set up MCP client if needed
        if use_tools and okta_token and strands_mcp_client:
            # Update Gateway URL if provided in request
            bedrock_agentcore_gateway_url = body.get("bedrock_agentcore_gateway_url")
            if bedrock_agentcore_gateway_url:
                strands_mcp_client.update_gateway_url(bedrock_agentcore_gateway_url)
            
            await strands_mcp_client.set_auth_token(okta_token)
        
        async def generate_response():
            try:
                # Create ephemeral agent for this request with specified parameters
                agent = create_agent_for_request(
                    conversation_history=conversation_history,
                    use_mcp_tools=use_tools,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                # Real streaming from Strands Agent
                full_response = ""
                async for chunk in agent.stream_async(message):
                    # Extract text from chunk - handle different Strands streaming formats
                    chunk_text = ""
                    
                    # Try different ways to extract text from Strands chunk
                    if hasattr(chunk, 'data') and chunk.data:
                        chunk_text = chunk.data
                    elif hasattr(chunk, 'delta') and hasattr(chunk.delta, 'text'):
                        chunk_text = chunk.delta.text
                    elif hasattr(chunk, 'content'):
                        chunk_text = chunk.content
                    elif hasattr(chunk, 'message') and 'content' in chunk.message:
                        for content_block in chunk.message['content']:
                            if 'text' in content_block:
                                chunk_text += content_block['text']
                    elif isinstance(chunk, dict):
                        # Handle dict format
                        if 'data' in chunk:
                            chunk_text = chunk['data']
                        elif 'delta' in chunk and 'text' in chunk['delta']:
                            chunk_text = chunk['delta']['text']
                    
                    # Only yield if we have actual text content
                    if chunk_text and isinstance(chunk_text, str):
                        full_response += chunk_text
                        yield chunk_text
                
                # Save conversation to DynamoDB after streaming completes
                await conversation_manager.add_message_to_conversation(
                    conversation_id, "user", message
                )
                await conversation_manager.add_message_to_conversation(
                    conversation_id, "assistant", full_response
                )
                    
            except Exception as e:
                yield f"Error: {str(e)}"
        
        return StreamingResponse(
            generate_response(),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )
        
    except Exception as e:
        return {"error": str(e)}

# Conversation Management Endpoints

@app.get("/api/conversations")
async def list_conversations():
    """List all conversation IDs from DynamoDB"""
    try:
        # Get all conversations from DynamoDB
        # This is a simple scan - in production, you might want pagination
        import boto3
        dynamodb = boto3.resource('dynamodb', region_name=BEDROCK_REGION)
        table = dynamodb.Table(DYNAMODB_TABLE_NAME)
        
        response = table.scan(
            ProjectionExpression='conversation_id, updated_at, message_count'
        )
        
        conversations = []
        for item in response.get('Items', []):
            conversations.append({
                'conversation_id': item.get('conversation_id'),
                'updated_at': item.get('updated_at'),
                'message_count': item.get('message_count', 0)
            })
        
        # Sort by updated_at descending (most recent first)
        conversations.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
        
        return {
            "conversations": conversations,
            "count": len(conversations)
        }
        
    except Exception as e:
        logger.error(f"Error listing conversations: {str(e)}")
        return {"error": str(e)}

@app.delete("/api/conversations")
async def clear_all_conversations():
    """Clear all conversations from DynamoDB"""
    try:
        import boto3
        dynamodb = boto3.resource('dynamodb', region_name=BEDROCK_REGION)
        table = dynamodb.Table(DYNAMODB_TABLE_NAME)
        
        # Scan to get all conversation IDs
        response = table.scan(ProjectionExpression='conversation_id')
        
        deleted_count = 0
        # Delete each conversation
        for item in response.get('Items', []):
            conversation_id = item.get('conversation_id')
            table.delete_item(Key={'conversation_id': conversation_id})
            deleted_count += 1
        
        logger.info(f"Cleared {deleted_count} conversations from DynamoDB")
        return {
            "message": f"Successfully cleared {deleted_count} conversations",
            "deleted_count": deleted_count
        }
        
    except Exception as e:
        logger.error(f"Error clearing all conversations: {str(e)}")
        return {"error": str(e)}

@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get conversation history and metadata"""
    try:
        history = await conversation_manager.get_conversation_history(conversation_id)
        metadata = await conversation_manager.get_conversation_metadata(conversation_id)
        
        return {
            "conversation_id": conversation_id,
            "history": history,
            "metadata": metadata,
            "message_count": len(history)
        }
    except Exception as e:
        logger.error(f"Error retrieving conversation {conversation_id}: {str(e)}")
        return {"error": str(e)}

@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation"""
    try:
        success = await conversation_manager.delete_conversation(conversation_id)
        if success:
            return {"message": f"Conversation {conversation_id} deleted successfully"}
        else:
            return {"error": "Failed to delete conversation"}
    except Exception as e:
        logger.error(f"Error deleting conversation {conversation_id}: {str(e)}")
        return {"error": str(e)}

@app.post("/api/conversations/{conversation_id}/clear")
async def clear_conversation(conversation_id: str):
    """Clear conversation history but keep the conversation ID"""
    try:
        success = await conversation_manager.save_conversation_history(conversation_id, [])
        if success:
            return {"message": f"Conversation {conversation_id} cleared successfully"}
        else:
            return {"error": "Failed to clear conversation"}
    except Exception as e:
        logger.error(f"Error clearing conversation {conversation_id}: {str(e)}")
        return {"error": str(e)}

@app.post("/api/tools/fetch")
async def fetch_tools(request: Request):
    """Fetch BAC Gateway tools with direct MCP call"""
    try:
        body = await request.json()
        okta_token = body.get("okta_token")
        bedrock_agentcore_gateway_url = body.get("bedrock_agentcore_gateway_url")
        
        if not okta_token:
            return {"error": "Okta token required", "tools": []}
        
        if not bedrock_agentcore_gateway_url:
            return {"error": "BAC Gateway URL required in request", "tools": []}
        
        try:
            logger.info(f"Fetching BAC Gateway tools from: {bedrock_agentcore_gateway_url}")
            logger.info(f"Using Okta token (length: {len(okta_token)})")
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {okta_token}',
                'Accept': 'application/json'
            }
            
            # Initialize MCP session
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "ai-chatbot-lambda", "version": "3.1.0"}
                }
            }
            
            response = requests.post(bedrock_agentcore_gateway_url, headers=headers, json=init_request, timeout=30)
            if response.status_code != 200:
                logger.error(f"Failed to initialize MCP session: {response.status_code} - {response.text}")
                return {"error": f"Failed to initialize MCP session: {response.status_code}", "tools": []}
            
            # List tools
            tools_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }
            
            response = requests.post(bedrock_agentcore_gateway_url, headers=headers, json=tools_request, timeout=30)
            if response.status_code != 200:
                logger.error(f"Failed to list tools: {response.status_code} - {response.text}")
                return {"error": f"Failed to list tools: {response.status_code}", "tools": []}
            
            result = response.json()
            
            if 'result' in result and not result['result'].get('isError', False):
                tools = result['result'].get('tools', [])
                logger.info(f"Fetched {len(tools)} BAC Gateway tools successfully via direct call")
                
                # Convert to expected format
                formatted_tools = []
                for tool in tools:
                    formatted_tools.append({
                        "name": tool.get("name", "unknown"),
                        "description": tool.get("description", "No description"),
                        "inputSchema": tool.get("inputSchema", {"type": "object"})
                    })
                
                return {
                    "tools": formatted_tools,
                    "count": len(formatted_tools),
                    "message": f"Successfully fetched {len(formatted_tools)} BAC Gateway tools"
                }
            else:
                error_msg = "Unknown error"
                if 'result' in result and result['result'].get('isError', False):
                    error_content = result['result'].get('content', [])
                    if error_content and len(error_content) > 0:
                        error_msg = error_content[0].get('text', 'Unknown error')
                
                logger.error(f"BAC Gateway returned error: {error_msg}")
                return {"error": f"BAC Gateway error: {error_msg}", "tools": []}
            
        except Exception as e:
            logger.error(f"Error fetching BAC Gateway tools with direct call: {str(e)}")
            return {"error": str(e), "tools": []}
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return {"error": str(e), "tools": []}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
