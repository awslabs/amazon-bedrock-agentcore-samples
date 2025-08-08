#!/usr/bin/env python3
"""
SDK Agent for AgentCore Runtime with BedrockAgentCoreApp
Uses shared business logic with DIY agent for consistency
"""

# ============================================================================
# IMPORTS
# ============================================================================

from bedrock_agentcore.runtime import BedrockAgentCoreApp
<<<<<<< HEAD
import functools
=======
>>>>>>> origin/main
import json
import logging
import sys
import os

# Add paths for both container and local development environments
current_dir = os.path.dirname(os.path.abspath(__file__))

# Detect container vs local environment
if current_dir.startswith('/app'):
    # Container environment - AgentCore CLI packages everything in /app
    sys.path.append('/app')  # For agent_shared
else:
    # Local development environment
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
    sys.path.append(project_root)  # For shared.config_manager
    sys.path.append(os.path.dirname(current_dir))  # For agent_shared

# Strands imports
from strands import Agent, tool
from strands.models import BedrockModel

# Use AWS documented Strands MCP client pattern
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

<<<<<<< HEAD
# Import loop control tools from strands_tools
from strands_tools import think, stop, handoff_to_user

=======
>>>>>>> origin/main
# Shared configuration manager (agent-local copy for CLI packaging)
from agent_shared.config_manager import AgentCoreConfigManager

# Agent-specific shared utilities
from agent_shared.auth import setup_oauth, get_m2m_token, is_oauth_available
<<<<<<< HEAD
=======
from agent_shared.mcp import create_mcp_client, get_mcp_tools, is_mcp_available, get_mcp_tools_with_persistent_client, cleanup_mcp_client
>>>>>>> origin/main
from agent_shared.memory import setup_memory, get_conversation_context, save_conversation, is_memory_available
from agent_shared.responses import format_sdk_response, extract_text_from_event, format_error_response

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
<<<<<<< HEAD
# EXACT AWS DOCUMENTATION PATTERNS
# ============================================================================

def _create_streamable_http_transport(url, headers=None):
    """
    EXACT function from AWS documentation
    https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-using-mcp-clients.html
    """
    return streamablehttp_client(url, headers=headers)

# ============================================================================
=======
>>>>>>> origin/main
# CONFIGURATION
# ============================================================================

# Initialize configuration manager
config_manager = AgentCoreConfigManager()

# Load model settings
model_settings = config_manager.get_model_settings()
gateway_url = config_manager.get_gateway_url()

logger.info(f"🚀 SDK Agent (CLI deployable) starting with model: {model_settings['model_id']}")
if gateway_url:
    logger.info(f"🌐 Gateway configured: {gateway_url}")
else:
    logger.info("🏠 No gateway configured - using local tools only")

# ============================================================================
# TOOLS
# ============================================================================

@tool(name="get_current_time", description="Get the current date and time")
def get_current_time() -> str:
    """Get current timestamp"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

@tool(name="echo_message", description="Echo back a message for testing")
def echo_message(message: str) -> str:
    """Echo back the provided message"""
    return f"Echo: {message}"

# ============================================================================
<<<<<<< HEAD
# STREAMING WITH MCP CONTEXT MANAGEMENT
# ============================================================================

async def execute_agent_streaming_sdk(bedrock_model, prompt):
    """
    Streaming version of AWS documented pattern for SDK agent
    """
    # Get configuration
    config_manager = AgentCoreConfigManager()
    gateway_url = config_manager.get_gateway_url()
    
    # Define system prompt for the agent
    system_prompt = """You are an AWS Operations Assistant with read-only access to AWS resources through specialized tools.

🚨 MANDATORY BEHAVIOR: IMMEDIATE PROGRESS UPDATES WITH EMOJIS 🚨

YOU MUST FOLLOW THIS EXACT PATTERN FOR EVERY REQUEST:

1. Start with: "I'll help you [task]. Here's my plan:" followed by numbered steps
2. Use emojis consistently: 🔍 before each check, ✅ after each result
3. After EVERY tool call, immediately provide the result with ✅
4. Use echo_message tool if needed to ensure progress updates are sent
5. Never execute multiple tools without progress updates between them

Available AWS Services: EC2, S3, Lambda, CloudFormation, IAM, RDS, CloudWatch, Cost Explorer, ECS, EKS, SNS, SQS, DynamoDB, Route53, API Gateway, SES, Bedrock, SageMaker.

Remember: Progress updates with emojis are MANDATORY, not optional! Follow the exact pattern shown above.
"""
    
    # Fallback to local tools if gateway or oauth is not working
    if not gateway_url or not is_oauth_available():
        logger.info("🏠 No MCP available - using local streaming")
        local_tools = [get_current_time, echo_message, think, stop, handoff_to_user]
        agent = Agent(model=bedrock_model, tools=local_tools, system_prompt=system_prompt)
        async for event in agent.stream_async(prompt):
            yield event
        return
    
    try:
        access_token = get_m2m_token()
        if not access_token:
            raise Exception("No access token")
        
        # Create headers for authentication
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # EXACT AWS pattern: Create MCP client with functools.partial
        mcp_client = MCPClient(functools.partial(
            _create_streamable_http_transport,
            url=gateway_url,
            headers=headers
        ))
        
        # EXACT AWS pattern: Use context manager
        with mcp_client:
            tools = mcp_client.list_tools_sync()
            
            # Add local tools
            all_tools = [get_current_time, echo_message, think, stop, handoff_to_user]
            if tools:
                all_tools.extend(tools)
                logger.info(f"🛠️ SDK Streaming with {len(tools)} MCP tools + local tools")
            
            agent = Agent(model=bedrock_model, tools=all_tools, system_prompt=system_prompt)
            async for event in agent.stream_async(prompt):
                yield event
                
    except Exception as e:
        logger.error(f"❌ MCP streaming failed: {e}")
        # Fallback to local streaming
        logger.info("🏠 Falling back to local streaming")
        local_tools = [get_current_time, echo_message, think, stop, handoff_to_user]
        agent = Agent(model=bedrock_model, tools=local_tools, system_prompt=system_prompt)
        async for event in agent.stream_async(prompt):
            yield event

# ============================================================================
=======
>>>>>>> origin/main
# AGENT SETUP
# ============================================================================

def create_strands_agent(use_mcp=True):
    """Create Strands agent with local tools and optionally MCP tools using AWS compliant pattern"""
    # Create BedrockModel
    model = BedrockModel(**model_settings)

    # Define system prompt for the agent
<<<<<<< HEAD
    system_prompt = """You are an AWS Operations Assistant with read-only access to AWS resources through specialized tools.

🚨 MANDATORY BEHAVIOR: IMMEDIATE PROGRESS UPDATES WITH EMOJIS 🚨

YOU MUST FOLLOW THIS EXACT PATTERN FOR EVERY REQUEST:

1. Start with: "I'll help you [task]. Here's my plan:" followed by numbered steps
2. Use emojis consistently: 🔍 before each check, ✅ after each result
3. After EVERY tool call, immediately provide the result with ✅
4. Use echo_message tool if needed to ensure progress updates are sent
5. Never execute multiple tools without progress updates between them

REQUIRED RESPONSE PATTERN:
```
I'll help you get an AWS account overview. Here's my plan:
1. Check EC2 instances
2. List S3 buckets
3. Review Lambda functions
4. Check IAM resources
5. Look at databases

🔍 Checking EC2 instances now...
[Execute EC2 tool]
✅ Found 2 EC2 instances: 1 running (t3.large), 1 stopped (t3a.2xlarge)

🔍 Now checking S3 buckets...
[Execute S3 tool]  
✅ Found 47 S3 buckets - mix of service and personal storage

🔍 Next, reviewing Lambda functions...
[Execute Lambda tool]
✅ Found 5 Lambda functions including MCP tools and API handlers

[Continue this exact pattern for ALL tasks]

📊 **Complete Overview:**
[Final detailed summary]
```

CRITICAL RULES - NO EXCEPTIONS:
- Use 🔍 before EVERY tool execution
- Use ✅ immediately after EVERY tool result
- Provide specific results after each tool call
- Never batch multiple tool calls without intermediate updates
- Use echo_message tool to send progress updates if needed
- Break complex operations into smaller atomic tasks

ATOMIC TASK BREAKDOWN STRATEGY:
Your role is to break down complex AWS queries into very small, atomic tasks and execute them step-by-step with immediate progress updates.

EXECUTION WORKFLOW:
1. **Think First**: Use the think tool to break down complex requests into atomic steps
2. **Announce Plan**: Tell the user your step-by-step plan with numbered steps
3. **Execute with Updates**: For each step:
   - Say "🔍 [What you're about to check]..."
   - Execute the tool
   - Immediately say "✅ [What you found]"
4. **Final Summary**: Provide comprehensive summary with 📊

TOOL USAGE STRATEGY:
1. **think**: ALWAYS use first to break down requests into atomic steps
2. **echo_message**: Use for progress announcements if streaming isn't working
3. **AWS tools**: Execute one atomic operation at a time
4. **get_current_time**: Use when time-based queries are needed
5. **stop**: Use if you exceed 15 tool calls with a summary
6. **handoff_to_user**: Use if you need guidance

PROGRESS INDICATORS (MANDATORY):
- 🤔 Thinking/Planning
- 🔍 About to check/query (REQUIRED before each tool)
- ✅ Task completed (REQUIRED after each tool)
- 📊 Final summary
- ⚠️ Issues found
- 💡 Recommendations

EXAMPLE ATOMIC TASKS:

❌ WRONG - No progress updates:
"Let me check your AWS resources... [long pause] ...here's your overview"

✅ CORRECT - With progress updates:
"I'll check your AWS resources. Here's my plan:
1. EC2 instances
2. S3 buckets
3. Lambda functions

🔍 Checking EC2 instances now...
✅ Found 2 instances: 1 running, 1 stopped

🔍 Now checking S3 buckets...
✅ Found 47 buckets across various services

🔍 Next, reviewing Lambda functions...
✅ Found 5 functions including MCP tools

📊 **Complete Overview:** [detailed summary]"

CRITICAL SUCCESS FACTORS:
- Every tool execution MUST be preceded by 🔍 announcement
- Every tool result MUST be followed by ✅ summary
- Use specific numbers and details in progress updates
- Maintain consistent emoji usage throughout
- Provide immediate feedback, never batch operations silently

Available AWS Services: EC2, S3, Lambda, CloudFormation, IAM, RDS, CloudWatch, Cost Explorer, ECS, EKS, SNS, SQS, DynamoDB, Route53, API Gateway, SES, Bedrock, SageMaker.

Remember: Progress updates with emojis are MANDATORY, not optional! Follow the exact pattern shown above.
"""
    
    # Start with local tools including loop control tools
    tools = [get_current_time, echo_message, think, stop, handoff_to_user]
    
    # Add MCP tools if available and requested - but don't try to use them in agent creation
    # The MCP client context manager issue means we should fall back to local tools for now
    if use_mcp and gateway_url and is_oauth_available():
        logger.info("🏠 MCP tools requested but using local tools only due to context manager constraints")
        logger.info("🛠️ SDK Agent will use local tools for reliable operation")
    else:
        if not gateway_url:
            logger.info("🏠 No gateway configured - using local tools only")
        elif not is_oauth_available():
            logger.info("🔑 OAuth not available - using local tools only")
        else:
            logger.info(f"🛠️ MCP disabled - using {len(tools)} local tools only")
    
    logger.info(f"🛠️ SDK Agent created with {len(tools)} local tools")
    return Agent(model=model, tools=tools, system_prompt=system_prompt)

=======
    system_prompt = """You are an AWS Operational Support Agent with read-only access to AWS resources through BAC Gateway tools.

CRITICAL: For any date-related queries, ALWAYS use the get_time tool first to get the current date before making AWS tool calls.

When using AWS tools:
1. If the query involves dates or time periods (like "last month", "last 14 days", "current month"):
   - FIRST call get_time to get the current date and year
   - Calculate the correct date ranges based on the current date  
   - Pass specific, accurate dates to AWS tools
   - Never assume or hardcode dates - always calculate from current time

2. Be very clear and crisp in your natural language queries to AWS tools
3. Ask only for the minimum required information needed to answer the user's question
4. Use concise, specific queries

Date-Aware Query Examples:
- User asks 'last month expenses' → Call get_time first, then use cost_explorer_read_operations with "expenses for [calculated last month]"
- User asks 'last 14 days costs' → Call get_time first, then use cost_explorer_read_operations with "costs from [calculated start date] to [current date]"

Regular Query Examples:
- 'list running instances' (not 'show me all the EC2 instances with their details and configurations')
- 'count S3 buckets' (not 'give me comprehensive information about all S3 buckets')
- 'show failed stacks' (not 'list all CloudFormation stacks with their complete status information')

Available AWS Services: EC2, S3, Lambda, CloudFormation, IAM, RDS, CloudWatch, Cost Explorer, ECS, EKS, SNS, SQS, DynamoDB, Route53, API Gateway, SES, Bedrock, SageMaker.

Provide clear, structured responses focusing on the specific information requested by the user.
"""
    
    # Start with local tools
    tools = [get_current_time, echo_message]
    
    # Add MCP tools if available and requested
    if use_mcp and gateway_url and is_mcp_available(gateway_url):
        try:
            # Use provided access token or get from OAuth
            token_to_use = get_m2m_token() if is_oauth_available() else None
            
            if token_to_use:
                logger.info(f"🔑 Using access token for MCP tools (length: {len(token_to_use)})")
                logger.info(f"🌐 Connecting to gateway: {gateway_url}")
                
                def create_streamable_http_transport(mcp_url: str, access_token: str):
                    logger.info(f"🔗 Creating MCP transport connection:")
                    logger.info(f"   📍 MCP URL: {mcp_url}")
                    logger.info(f"   🔑 Bearer token: {access_token[:20]}...{access_token[-10:]} (length: {len(access_token)})")
                    
                    # Store token info for later validation (optional)
                    import time
                    try:
                        # Try to import JWT library (may not be available)
                        import jwt
                        # Decode token to check expiry (without verification for logging)
                        decoded = jwt.decode(access_token, options={"verify_signature": False})
                        exp_time = decoded.get('exp', 0)
                        current_time = time.time()
                        time_to_expiry = exp_time - current_time
                        logger.info(f"   ⏰ Token expires in: {time_to_expiry:.0f} seconds")
                        
                        # Store for later reference
                        global _token_expiry
                        _token_expiry = exp_time
                    except ImportError:
                        logger.info(f"   ⏰ JWT library not available - skipping token expiry check")
                    except Exception as token_error:
                        logger.warning(f"   ⚠️ Could not decode token for expiry check: {token_error}")
                    
                    return streamablehttp_client(mcp_url, headers={"Authorization": f"Bearer {access_token}"})
                
                # Simplified approach: Let Strands SDK handle tool discovery automatically
                # Create MCP client and get tools in the simplest way possible
                mcp_client = MCPClient(lambda: create_streamable_http_transport(gateway_url, token_to_use))
                
                # Store client globally for proper lifecycle management
                global _mcp_client
                _mcp_client = mcp_client
                
                # Start client and get tools - let Strands handle the complexity
                mcp_client.start()
                
                # Simple tool discovery - no pagination complexity needed for most cases
                try:
                    mcp_tools = mcp_client.list_tools_sync()
                    if mcp_tools:
                        tools.extend(mcp_tools)
                        logger.info(f"🛠️ Added {len(mcp_tools)} MCP tools: {[tool.tool_name for tool in mcp_tools[:5]]}")
                    else:
                        logger.warning("⚠️ No MCP tools found from gateway")
                except Exception as e:
                    logger.error(f"❌ Failed to get MCP tools: {e}")
                
                logger.info(f"🔗 MCP client ready - Agent will have {len(tools)} total tools")
            else:
                logger.warning("⚠️ No OAuth access_token available for MCP")
                logger.info(f"🛠️ Agent created with {len(tools)} local tools only")
        except Exception as e:
            logger.error(f"❌ MCP setup failed: {e}")
            import traceback
            logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            logger.info(f"🛠️ Agent created with {len(tools)} local tools only")
    else:
        logger.info(f"🛠️ Agent created with {len(tools)} local tools only")
    
    return Agent(model=model, tools=tools, system_prompt=system_prompt)

# Agent instance - will be created after startup
strands_agent = None
_mcp_client = None
_token_expiry = None

>>>>>>> origin/main
# ============================================================================
# AGENTCORE APP
# ============================================================================

app = BedrockAgentCoreApp()

# ============================================================================
# STREAMING
# ============================================================================

def extract_prompt_from_payload(payload):
    """Extract prompt from payload supporting both direct and wrapped formats"""
    try:
        # Direct format: {"prompt": "message", "session_id": "optional", "actor_id": "user"}
        if isinstance(payload, dict) and "prompt" in payload:
            return payload.get("prompt", "No prompt provided"), payload.get("session_id"), payload.get("actor_id", "user")
        
        # Wrapped format: {"payload": "{\"prompt\": \"message\"}"}
        if isinstance(payload, dict) and "payload" in payload:
            try:
                inner_payload = json.loads(payload["payload"])
                return inner_payload.get("prompt", "No prompt provided"), inner_payload.get("session_id"), inner_payload.get("actor_id", "user")
            except json.JSONDecodeError:
                logger.warning("⚠️ Invalid JSON in wrapped payload")
                return "Invalid payload format", None, "user"
        
        # Fallback
        logger.warning(f"⚠️ Unexpected payload format: {type(payload)}")
        return "No prompt found in input, please provide a JSON payload with prompt key", None, "user"
        
    except Exception as e:
        logger.error(f"❌ Failed to extract prompt: {e}")
        return f"Error processing payload: {str(e)}", None, "user"

# ============================================================================
# SDK APP
# ============================================================================

# Using automatic ping handler from BedrockAgentCoreApp

@app.entrypoint
async def invoke(payload):
    """Process user input and return a response with memory support"""
    logger.info("📥 Received SDK invocation request")
    
    response_parts = []
<<<<<<< HEAD
    
    try:
=======
    chunk_count = 0
    tool_calls_detected = 0
    
    try:
        # Ensure agent is created (safety check)
        global strands_agent
        if strands_agent is None:
            logger.warning("⚠️ Agent not initialized, creating now...")
            strands_agent = create_strands_agent()
        
>>>>>>> origin/main
        # Extract prompt and metadata from payload
        user_message, session_id, actor_id = extract_prompt_from_payload(payload)
        
        logger.info(f"🚀 SDK Agent invocation: {user_message[:50]}...")
        logger.info(f"📋 Session: {session_id}, Actor: {actor_id}")
<<<<<<< HEAD
=======
        logger.info("🔑 Using AgentCore Runtime for inbound auth, M2M tokens for outbound MCP auth")
>>>>>>> origin/main
        
        # Get conversation context if memory is available
        context = ""
        if is_memory_available() and session_id:
<<<<<<< HEAD
            context = get_conversation_context(session_id, actor_id)
            if context:
                logger.info(f"💾 Retrieved context length: {len(context)} chars")
=======
            logger.info(f"💾 SDK: Retrieving memory for session {session_id}, actor {actor_id}")
            context = get_conversation_context(session_id, actor_id)
            if context:
                logger.info(f"💾 SDK: Retrieved context length: {len(context)} chars")
                logger.info(f"💾 SDK: Context preview: {context[:200]}...")
            else:
                logger.info("💾 SDK: No previous context found")
        else:
            logger.info("💾 SDK: Memory not available or no session ID")
>>>>>>> origin/main
        
        # Prepare final message with context
        final_message = user_message
        if context:
            final_message = f"{context}\n\nCurrent user message: {user_message}"
<<<<<<< HEAD
        
        # Create model with streaming enabled
        model = BedrockModel(**model_settings, streaming=True, timeout=900)
        
        # Use the streaming function with proper MCP context management
        async for event in execute_agent_streaming_sdk(model, final_message):
            # Format event for SDK (keeps format_sdk_response)
=======
            logger.info("📚 SDK: Added conversation context to message")
        
        # Log agent and tool state before streaming
        logger.info(f"🤖 Starting SDK agent stream...")
        logger.info(f"🛠️ Agent has {len(strands_agent.tools) if hasattr(strands_agent, 'tools') else 'unknown'} tools available")
        
        # Log MCP client state if available
        global _mcp_client
        if _mcp_client:
            try:
                logger.info(f"🔌 MCP client state: Connected")
                logger.info(f"🔑 Checking MCP client connection health...")
            except Exception as mcp_error:
                logger.warning(f"⚠️ MCP client state check failed: {mcp_error}")
        
        last_event_type = None
        
        async for event in strands_agent.stream_async(final_message):
            chunk_count += 1
            
            # Enhanced event logging for debugging
            event_class = getattr(event, '__class__', None)
            event_type = getattr(event_class, '__name__', 'unknown') if event_class else 'unknown'
            current_event_type = str(type(event)).split('.')[-1].replace("'>", "")
            
            # Log significant event types
            if current_event_type != last_event_type:
                logger.info(f"📡 Event type changed: {last_event_type} → {current_event_type}")
                last_event_type = current_event_type
            
            # Detect tool usage patterns
            event_str = str(event)
            if 'toolUse' in event_str or 'tool_use' in event_str:
                tool_calls_detected += 1
                logger.info(f"🔧 Tool call detected #{tool_calls_detected} in chunk {chunk_count}")
                logger.info(f"🔧 Tool call details: {event_str[:200]}...")
                
                # Check MCP client state during tool calls
                if _mcp_client:
                    try:
                        logger.info(f"🔌 MCP client during tool call: Checking connection...")
                        
                        # Check token expiry (if available)
                        global _token_expiry
                        if _token_expiry:
                            import time
                            current_time = time.time()
                            time_remaining = _token_expiry - current_time
                            logger.info(f"🔑 Token time remaining: {time_remaining:.0f} seconds")
                            
                            if time_remaining < 60:
                                logger.warning(f"⚠️ Token expires soon! ({time_remaining:.0f}s remaining)")
                            elif time_remaining < 0:
                                logger.error(f"❌ Token has expired! ({-time_remaining:.0f}s ago)")
                        else:
                            logger.info(f"🔑 Token expiry info not available (JWT library missing)")
                        
                        logger.info(f"🔑 MCP client appears active during tool call")
                    except Exception as mcp_error:
                        logger.error(f"❌ MCP client error during tool call: {mcp_error}")
            
            # Detect tool results
            if 'toolResult' in event_str or 'tool_result' in event_str:
                logger.info(f"📊 Tool result received in chunk {chunk_count}")
                logger.info(f"📊 Tool result preview: {event_str[:200]}...")
            
            # Format event for SDK (direct streaming)
>>>>>>> origin/main
            formatted = format_sdk_response(event)
            yield formatted
            
            # Extract text for memory storage
            text = extract_text_from_event(event)
            if text:
                response_parts.append(text)
<<<<<<< HEAD
=======
            
            # Enhanced chunk logging
            if text:
                logger.debug(f"📤 Chunk {chunk_count}: {text[:50]}..." if len(text) > 50 else f"📤 Chunk {chunk_count}: {text}")
            else:
                logger.debug(f"📤 Chunk {chunk_count}: (no text) - Event: {current_event_type}")
            
            # Log every 10 chunks to track progress
            if chunk_count % 10 == 0:
                logger.info(f"📈 Streaming progress: {chunk_count} chunks, {tool_calls_detected} tool calls detected")
        
        # Enhanced completion logging
        logger.info(f"✅ SDK stream completed with {chunk_count} chunks, {tool_calls_detected} tool calls detected")
        logger.info(f"📊 Response parts collected: {len(response_parts)}")
        
        if tool_calls_detected > 0:
            logger.info(f"🔧 Tool execution summary: {tool_calls_detected} tool calls processed")
            if len(response_parts) == 0:
                logger.warning(f"⚠️ Tool calls detected but no response text collected - possible tool execution failure")
>>>>>>> origin/main
        
        # Save conversation to memory after streaming
        if is_memory_available() and session_id and response_parts:
            full_response = ''.join(response_parts)
<<<<<<< HEAD
            save_conversation(session_id, user_message, full_response, actor_id)
            logger.info("💾 Conversation saved successfully")
            
    except Exception as e:
        logger.error(f"❌ SDK streaming error: {e}")
=======
            logger.info(f"💾 SDK: Saving conversation to memory (response length: {len(full_response)})")
            logger.info(f"💾 SDK: Saving session {session_id}, actor {actor_id}")
            logger.info(f"💾 SDK: User message: {user_message[:100]}...")
            logger.info(f"💾 SDK: Response preview: {full_response[:100]}...")
            save_conversation(session_id, user_message, full_response, actor_id)
            logger.info("💾 SDK: Conversation saved successfully")
        elif is_memory_available() and session_id and not response_parts:
            logger.warning(f"⚠️ SDK: No response parts to save to memory despite memory being available")
            
    except Exception as e:
        logger.error(f"❌ SDK streaming error: {e}")
        logger.error(f"❌ Error type: {type(e).__name__}")
        logger.error(f"❌ Error occurred at chunk {chunk_count}, tool calls: {tool_calls_detected}")
        
        # Log MCP client state during error
        if _mcp_client:
            try:
                logger.error(f"❌ MCP client state during error: Checking...")
                logger.error(f"❌ MCP client appears to be in error state")
            except Exception as mcp_error:
                logger.error(f"❌ MCP client also failed during error: {mcp_error}")
        
        # Import traceback for detailed error logging
        import traceback
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")
        
>>>>>>> origin/main
        error_response = format_error_response(str(e), "sdk")
        yield error_response

# ============================================================================
# STARTUP INITIALIZATION
# ============================================================================

def initialize_services():
    """Initialize services on startup"""
    logger.info("🚀 Starting SDK Agent...")
    
    # Initialize OAuth
    if setup_oauth():
        logger.info("✅ OAuth initialized")
    else:
<<<<<<< HEAD
        logger.warning("⚠️ OAuth not available")
=======
        logger.warning("⚠️ OAuth not available - using access token from decorators only")
>>>>>>> origin/main
    
    # Initialize Memory
    if setup_memory():
        logger.info("✅ Memory initialized")
    else:
<<<<<<< HEAD
        logger.warning("⚠️ Memory not available")
    
    logger.info("✅ SDK Agent ready (using streaming pattern)")
=======
        logger.warning("⚠️ Memory not available - no conversation context")
    
    # Create agent instance now that OAuth and Memory are initialized
    global strands_agent
    strands_agent = create_strands_agent()
    
    logger.info("✅ SDK Agent ready")
>>>>>>> origin/main

def cleanup_resources():
    """Clean up resources on shutdown"""
    logger.info("🛑 Shutting down SDK Agent...")
<<<<<<< HEAD
=======
    
    # Clean up persistent MCP client properly
    global _mcp_client
    if _mcp_client:
        try:
            _mcp_client.close()
            logger.info("🧹 Persistent MCP client closed properly")
        except Exception as e:
            logger.warning(f"⚠️ Error closing MCP client: {e}")
        finally:
            _mcp_client = None
    
>>>>>>> origin/main
    logger.info("✅ SDK Agent shutdown complete")

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    logger.info("🚀 Starting SDK Agent...")
    
    # Initialize services before starting the app
    initialize_services()
    
    try:
        app.run()
    finally:
        # Clean up resources on shutdown
        cleanup_resources()