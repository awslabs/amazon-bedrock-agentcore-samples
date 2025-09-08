"""
Strands Data Analyst Assistant - Main Application

This application provides a data analyst assistant powered by Amazon Bedrock and uses 
the Amazon RDS Data API to execute SQL queries against an Aurora Serverless PostgreSQL database.
It leverages Bedrock Agent Core for agent functionality and memory management.
"""

import logging
import json
from uuid import uuid4

# Bedrock Agent Core imports
from bedrock_agentcore import BedrockAgentCoreApp
from bedrock_agentcore.memory import MemoryClient
from strands import Agent, tool
from strands_tools import current_time
from strands.models import BedrockModel

# Custom module imports
from src.MemoryHookProvider import MemoryHookProvider
from src.tools import get_tables_information, load_file_content
from src.rds_data_api_utils import run_sql_query
from src.utils import save_raw_query_result, read_interactions_by_session, save_agent_interactions
from src.ssm_utils import get_ssm_parameter
from src.agentcore_memory_utils import get_agentcore_memory_messages

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("personal-agent")

# Read memory ID from SSM Parameter Store
try:
    print("\n" + "="*70)
    print("🚀 INITIALIZING STRANDS DATA ANALYST ASSISTANT")
    print("="*70)
    print("📋 Reading configuration from AWS Systems Manager...")
    
    # Read memory ID from SSM
    memory_id = get_ssm_parameter("MEMORY_ID")
    
    # Check if memory ID is empty
    if not memory_id or memory_id.strip() == "":
        error_msg = "Memory ID from SSM is empty. Memory has not been created yet."
        print(f"❌ ERROR: {error_msg}")
        logger.error(error_msg)
        raise ValueError(error_msg)
        
    print(f"✅ Successfully retrieved Memory ID: {memory_id}")
    
    # Initialize Memory Client
    print("🔧 Initializing AgentCore Memory Client...")
    client = MemoryClient()
    print("✅ Memory Client initialized successfully")
    print("="*70 + "\n")
    
except Exception as e:
    print(f"💥 INITIALIZATION ERROR: {str(e)}")
    print("="*70 + "\n")
    logger.error(f"Error retrieving memory ID from SSM: {e}")
    raise  # Re-raise the exception to stop execution


# Initialize the Bedrock Agent Core app
app = BedrockAgentCoreApp()

def load_system_prompt():
    """
    Load the system prompt from the instructions.txt file.
    
    This prompt defines the behavior and capabilities of the data analyst assistant.
    If the file is not available, a fallback prompt is used.
    
    Returns:
        str: The system prompt to use for the data analyst assistant
    """
    print("\n" + "="*50)
    print("📝 LOADING SYSTEM PROMPT")
    print("="*50)
    print("📂 Attempting to load instructions.txt...")
    
    fallback_prompt = """You are a helpful Data Analyst Assistant who can help with data analysis tasks.
                You can process data, interpret statistics, and provide insights based on data."""
    
    try:
        prompt = load_file_content("instructions.txt", default_content=fallback_prompt)
        if prompt == fallback_prompt:
            print("⚠️  Using fallback prompt (instructions.txt not found)")
        else:
            print("✅ Successfully loaded system prompt from instructions.txt")
            print(f"📊 Prompt length: {len(prompt)} characters")
        print("="*50 + "\n")
        return prompt
    except Exception as e:
        print(f"❌ Error loading system prompt: {str(e)}")
        print("⚠️  Using fallback prompt")
        print("="*50 + "\n")
        return fallback_prompt

# Load the system prompt
DATA_ANALYST_SYSTEM_PROMPT = load_system_prompt()

def create_execute_sql_query_tool(user_prompt: str, prompt_uuid: str):
    """
    Create a dynamic SQL query execution tool with session context.
    
    This function creates a tool that can execute SQL queries against the Aurora database
    using the RDS Data API. It also saves query results to DynamoDB for future reference.
    
    Args:
        user_prompt (str): The original user prompt/question
        prompt_uuid (str): Unique identifier for tracking this interaction
        
    Returns:
        function: The configured SQL query execution tool
    """
    @tool
    def execute_sql_query(sql_query: str, description: str) -> str:
        """
        Execute an SQL query against a database and return results for data analysis

        Args:
            sql_query: The SQL query to execute
            description: Concise explanation of the SQL query

        Returns:
            str: JSON string containing the query results or error message
        """
        print("\n" + "="*60)
        print("🗄️  SQL QUERY EXECUTION")
        print("="*60)
        print(f"📝 Description: {description}")
        print(f"🔍 Query: {sql_query[:200]}{'...' if len(sql_query) > 200 else ''}")
        print(f"🆔 Prompt UUID: {prompt_uuid}")
        print("-"*60)
        
        try:
            print("⏳ Executing SQL query via RDS Data API...")
            
            # Execute the SQL query using the RDS Data API function
            response_json = json.loads(run_sql_query(sql_query))
            
            # Check if there was an error
            if "error" in response_json:
                print(f"❌ Query execution failed: {response_json['error']}")
                print("="*60 + "\n")
                return json.dumps(response_json)
            
            # Extract the results
            records_to_return = response_json.get("result", [])
            message = response_json.get("message", "")
            
            print("✅ Query executed successfully")
            print(f"📊 Records returned: {len(records_to_return)}")
            if message:
                print(f"💬 Message: {message}")
            
            # Prepare result object
            if message != "":
                result = {
                    "result": records_to_return,
                    "message": message
                }
            else:
                result = {
                    "result": records_to_return
                }
            
            print("-"*60)
            print("💾 Saving query results to DynamoDB...")
            
            # Save query results to DynamoDB for future reference
            save_result = save_raw_query_result(
                prompt_uuid,
                user_prompt,
                sql_query,
                description,
                result,
                message
            )
            
            if not save_result["success"]:
                print(f"⚠️  Failed to save to DynamoDB: {save_result['error']}")
                result["saved"] = False
                result["save_error"] = save_result["error"]
            else:
                print("✅ Successfully saved query results to DynamoDB")
            
            print("="*60 + "\n")
            return json.dumps(result)
                
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(f"💥 EXCEPTION: {error_msg}")
            print("="*60 + "\n")
            return json.dumps({"error": error_msg})
    
    return execute_sql_query

@app.entrypoint
async def agent_invocation(payload):
    """
    Main handler for agent invocation with streaming response.
    
    This function processes incoming requests, initializes the agent with appropriate tools,
    streams the response back to the client, and saves conversation history.
    
    Expected payload structure:
    {
        "prompt": "Your data analysis question",
        "bedrock_model_id": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
        "prompt_uuid": "optional-uuid",
        "user_timezone": "US/Pacific",
        "session_id": "optional-session-id",
        "user_id": "optional-user-id",
        "last_turns": "optional-number-of-conversation-turns"
    }
    
    Returns:
        Generator: Yields response chunks for streaming
    """
    try:
        # Extract parameters from payload
        user_message = payload.get("prompt", "No prompt found in input, please guide customer to create a json payload with prompt key")
        bedrock_model_id = payload.get("bedrock_model_id", "us.anthropic.claude-3-7-sonnet-20250219-v1:0")
        prompt_uuid = payload.get("prompt_uuid", str(uuid4()))
        user_timezone = payload.get("user_timezone", "US/Pacific")
        session_id = payload.get("session_id", str(uuid4()))
        user_id = payload.get("user_id", "guest")
        last_k_turns = int(payload.get("last_k_turns", 20))
        
        print("\n" + "="*80)
        print("🎯 AGENT INVOCATION REQUEST")
        print("="*80)
        print(f"💬 User Message: {user_message[:100]}{'...' if len(user_message) > 100 else ''}")
        print(f"🤖 Bedrock Model: {bedrock_model_id}")
        print(f"🆔 Prompt UUID: {prompt_uuid}")
        print(f"🌍 User Timezone: {user_timezone}")
        print(f"🔗 Session ID: {session_id}")
        print(f"👤 User ID: {user_id}")
        print(f"🔄 Last K Turns: {last_k_turns}")
        print("-"*80)
        
        # Get agent interactions from DynamoDB
        print("📊 Loading agent interactions from DynamoDB...")
        agent_interactions = read_interactions_by_session(session_id)
        starting_message_id = len(agent_interactions)
        print(f"✅ Loaded {len(agent_interactions)} previous interactions")
        
        if agent_interactions:
            print("📝 Previous interactions preview:")
            for i, interaction in enumerate(agent_interactions[-3:], 1):  # Show last 3
                interaction_str = str(interaction)
                interaction_preview = f"{interaction_str[:100]}..." if len(interaction_str) > 100 else interaction_str
                print(f"   {i}. {interaction_preview}")
        
        print("-"*80)

        # Create Bedrock model instance
        print(f"🧠 Initializing Bedrock model: {bedrock_model_id}")
        bedrock_model = BedrockModel(model_id=bedrock_model_id)
        print("✅ Bedrock model initialized")
        
        print("-"*80)
        print("🧠 Loading conversation history from AgentCore Memory...")
        agentcore_messages = get_agentcore_memory_messages(client, memory_id, user_id, session_id, last_k_turns)    
        
        print("📋 AGENTCORE MEMORY MESSAGES LOADED:")
        print("-"*50)
        if agentcore_messages:
            for i, msg in enumerate(agentcore_messages, 1):
                role = msg.get('role', 'unknown')
                role_icon = "🤖" if role == 'assistant' else "👤"
                content_text = ""
                if 'content' in msg and msg['content']:
                    for content_item in msg['content']:
                        if 'text' in content_item:
                            content_text = content_item['text']
                            break
                content_preview = f"{content_text[:80]}..." if len(content_text) > 80 else content_text
                print(f"   {i}. {role_icon} {role.upper()}: {content_preview}")
        else:
            print("   📭 No previous conversation history found")
        print("-"*50)
        
        # Prepare system prompt with user's timezone
        print("📝 Preparing system prompt with user timezone...")
        system_prompt = DATA_ANALYST_SYSTEM_PROMPT.replace("{timezone}", user_timezone)
        print(f"✅ System prompt prepared (length: {len(system_prompt)} characters)")
        
        print("-"*80)
        print("🔧 Creating agent with tools and memory hooks...")
        
        # Create the agent with conversation history, memory hooks, and tools
        agent = Agent(
            messages=agentcore_messages,
            model=bedrock_model,
            system_prompt=system_prompt,
            hooks=[MemoryHookProvider(client, memory_id, user_id, session_id, last_k_turns)],
            tools=[get_tables_information, current_time, create_execute_sql_query_tool(user_message, prompt_uuid)],
            callback_handler=None
        )
        
        print("✅ Agent created successfully with:")
        print(f"   📝 {len(agentcore_messages)} conversation messages")
        print(f"   🔧 3 tools (get_tables_information, current_time, execute_sql_query)")
        print(f"   🧠 Memory hook provider configured")
        
        print("-"*80)
        print("🚀 Starting streaming response...")
        print("="*80)
        
        # Stream the response to the client
        stream = agent.stream_async(user_message)
        async for event in stream:            
            if "message" in event and "content" in event["message"] and "role" in event["message"] and event["message"]["role"] == "assistant":
                for content_item in event['message']['content']:
                    if "toolUse" in content_item and "input" in content_item["toolUse"] and content_item["toolUse"]['name'] == 'execute_sql_query':
                        yield f" {content_item['toolUse']['input']['description']}.\n\n"
                    elif "toolUse" in content_item and "name" in content_item["toolUse"] and content_item["toolUse"]['name'] == 'get_tables_information':
                        yield "\n\n"
                    elif "toolUse" in content_item and "name" in content_item["toolUse"] and content_item["toolUse"]['name'] == 'current_time':
                        yield "\n\n"
            elif "data" in event:
                yield event['data']
        
        print("\n" + "-"*80)
        print("💾 Saving agent interactions to DynamoDB...")
        
        # Save detailed agent interactions after streaming is complete
        save_agent_interactions(session_id, prompt_uuid, starting_message_id, agent.messages)
        print("✅ Agent interactions saved successfully")
        print("="*80 + "\n")
        
    except Exception as e:
        import traceback
        tb = traceback.extract_tb(e.__traceback__)
        filename, line_number, function_name, text = tb[-1]
        error_message = f"Error: {str(e)} (Line {line_number} in {filename})"
        print("\n" + "="*80)
        print("💥 AGENT INVOCATION ERROR")
        print("="*80)
        print(f"❌ Error: {str(e)}")
        print(f"📍 Location: Line {line_number} in {filename}")
        print(f"🔧 Function: {function_name}")
        if text:
            print(f"💻 Code: {text}")
        print("="*80 + "\n")
        yield f"I apologize, but I encountered an error while processing your request: {error_message}"

if __name__ == "__main__":
    print("\n" + "="*80)
    print("🚀 STARTING STRANDS DATA ANALYST ASSISTANT")
    print("="*80)
    print("🤖 Powered by Amazon Bedrock AgentCore")
    print("🗄️  Connected to Aurora Serverless PostgreSQL")
    print("🧠 Memory-enabled conversation system")
    print("🔧 SQL query execution capabilities")
    print("-"*80)
    print("📡 Server starting on port 8080...")
    print("🌐 Health check available at: /ping")
    print("🎯 Invocation endpoint: /invocations")
    print("="*80)
    app.run()