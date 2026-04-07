"""
Video Games Sales Data Analyst Assistant - Main Application

This application provides an intelligent data analyst assistant specialized in video game sales analysis.
It leverages Amazon Bedrock Claude models for natural language processing, Aurora Serverless PostgreSQL
for data storage, and AgentCore Memory for conversation context management.

Key Features:
- Natural language to SQL query conversion
- Video game sales data analysis and insights
- Conversation memory and context awareness
- Real-time streaming responses
- Comprehensive error handling and logging
"""

import logging
import json
import os
from uuid import uuid4

# Bedrock Agent Core imports
from bedrock_agentcore import BedrockAgentCoreApp
from strands import Agent, tool
from strands_tools import current_time
from strands.models import BedrockModel

# Custom module imports
from src.tools import get_tables_information, run_sql_query
from src.utils import (
    save_raw_query_result,
    load_file_content,
    get_agentcore_memory_messages,
    MemoryHookProvider,
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("personal-agent")

# Retrieve AgentCore Memory ID
memory_id = os.environ.get("MEMORY_ID")

# Retrieve Bedrock Model ID
bedrock_model_id_env = os.environ.get(
    "BEDROCK_MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0"
)

# Initialize the Bedrock Agent Core app
app = BedrockAgentCoreApp()


def load_system_prompt():
    """
    Load the system prompt configuration for the video games sales analyst assistant.

    This prompt defines the assistant's behavior, capabilities, and domain expertise
    in video game sales data analysis. Falls back to a default prompt if the
    instructions.txt file is not available.

    Returns:
        str: The system prompt configuration for the assistant
    """
    print("\n" + "=" * 50)
    print("📝 LOADING SYSTEM PROMPT")
    print("=" * 50)
    print("📂 Attempting to load instructions.txt...")

    fallback_prompt = """You are a specialized Video Games Sales Data Analyst Assistant with expertise in 
                analyzing gaming industry trends, sales performance, and market insights. You can execute SQL queries,
                interpret gaming data, and provide actionable business intelligence for the video game industry."""

    try:
        prompt = load_file_content("instructions.txt", default_content=fallback_prompt)
        if prompt == fallback_prompt:
            print("⚠️  Using fallback prompt (instructions.txt not found)")
        else:
            print("✅ Successfully loaded system prompt from instructions.txt")
            print(f"📊 Prompt length: {len(prompt)} characters")
        print("=" * 50 + "\n")
        return prompt
    except Exception as e:
        print(f"❌ Error loading system prompt: {str(e)}")
        print("⚠️  Using fallback prompt")
        print("=" * 50 + "\n")
        return fallback_prompt


# Load the system prompt
DATA_ANALYST_SYSTEM_PROMPT = load_system_prompt()


def create_execute_sql_query_tool(user_prompt: str, prompt_uuid: str):
    """
    Create a dynamic SQL query execution tool for video game sales data analysis.

    This function generates a specialized tool that executes SQL queries against the
    Aurora PostgreSQL database containing video game sales data. Query results are
    automatically saved to DynamoDB for audit trails and future reference.

    Args:
        user_prompt (str): The original user question about video game sales data
        prompt_uuid (str): Unique identifier for tracking this analysis prompt

    Returns:
        function: Configured SQL execution tool with video game sales context
    """

    @tool
    def execute_sql_query(sql_query: str, description: str) -> str:
        """
        Execute SQL queries against the video game sales database for data analysis.

        This tool runs SQL queries against the Aurora PostgreSQL database containing
        comprehensive video game sales data, including game titles, platforms, genres,
        sales figures, and regional performance metrics.

        Args:
            sql_query (str): The SQL query to execute against the video game sales database
            description (str): Clear description of what the query analyzes or retrieves

        Returns:
            str: JSON string containing query results, metadata, or error information
        """
        print("\n" + "=" * 60)
        print("🎮 VIDEO GAME SALES DATA QUERY EXECUTION")
        print("=" * 60)
        print(f"📝 Analysis: {description}")
        print(f"🔍 SQL Query: {sql_query[:200]}{'...' if len(sql_query) > 200 else ''}")
        print(f"🆔 Prompt UUID: {prompt_uuid}")
        print("-" * 60)

        try:
            print("⏳ Executing video game sales data query via RDS Data API...")

            # Execute the SQL query using the RDS Data API function
            response_json = json.loads(run_sql_query(sql_query))

            # Check if there was an error
            if "error" in response_json:
                print(f"❌ Query execution failed: {response_json['error']}")
                print("=" * 60 + "\n")
                return json.dumps(response_json)

            # Extract the results
            records_to_return = response_json.get("result", [])
            message = response_json.get("message", "")

            print("✅ Video game sales data query executed successfully")
            print(f"📊 Data records retrieved: {len(records_to_return)}")
            if message:
                print(f"💬 Query message: {message}")

            # Prepare result object
            if message != "":
                result = {"result": records_to_return, "message": message}
            else:
                result = {"result": records_to_return}

            print("-" * 60)
            print("💾 Saving analysis results to DynamoDB for audit trail...")

            # Save query results to DynamoDB for future reference
            save_result = save_raw_query_result(
                prompt_uuid, user_prompt, sql_query, description, result, message
            )

            if not save_result["success"]:
                print(
                    f"⚠️  Failed to save analysis results to DynamoDB: {save_result['error']}"
                )
                result["saved"] = False
                result["save_error"] = save_result["error"]
            else:
                print("✅ Analysis results successfully saved to DynamoDB audit trail")

            print("=" * 60 + "\n")
            return json.dumps(result)

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(f"💥 EXCEPTION: {error_msg}")
            print("=" * 60 + "\n")
            return json.dumps({"error": error_msg})

    return execute_sql_query


@app.entrypoint
async def agent_invocation(payload):
    """Main entry point for video game sales data analysis requests with streaming responses.

    This function processes natural language queries about video game sales data, initializes
    the Claude-powered agent with specialized tools, and streams intelligent analysis back
    to the client while maintaining conversation context.

    Expected payload structure:
    {
        "prompt": "Your video game sales analysis question",
        "prompt_uuid": "optional-unique-prompt-identifier",
        "user_timezone": "US/Pacific",
        "session_id": "optional-conversation-session-id",
        "user_id": "optional-user-identifier",
        "last_turns": "optional-number-of-conversation-turns-to-retrieve"
    }

    Returns:
        AsyncGenerator: Yields streaming response chunks with analysis results
    """
    try:
        # Extract parameters from payload
        user_message = payload.get(
            "prompt",
            "No prompt found in input, please guide customer to create a json payload with prompt key",
        )
        prompt_uuid = payload.get("prompt_uuid", str(uuid4()))
        user_timezone = payload.get("user_timezone", "US/Pacific")
        session_id = payload.get("session_id", str(uuid4()))
        user_id = payload.get("user_id", "guest")
        last_k_turns = int(payload.get("last_k_turns", 20))

        print("\n" + "=" * 80)
        print("🎮 VIDEO GAME SALES ANALYSIS REQUEST")
        print("=" * 80)
        print(
            f"💬 User Query: {user_message[:100]}{'...' if len(user_message) > 100 else ''}"
        )
        print(f"🤖 Claude Model: {bedrock_model_id_env}")
        print(f"🆔 Prompt UUID: {prompt_uuid}")
        print(f"🌍 User Timezone: {user_timezone}")
        print(f"🔗 Conversation ID: {session_id}")
        print(f"👤 User ID: {user_id}")
        print(f"🔄 Context Turns: {last_k_turns}")
        print("-" * 80)

        # Initialize Claude model for video game sales analysis
        print(f"🧠 Initializing Claude model for analysis: {bedrock_model_id_env}")
        bedrock_model = BedrockModel(model_id=bedrock_model_id_env)
        print("✅ Claude model ready for video game sales analysis")

        print("-" * 80)
        print("🧠 Retrieving conversation context from AgentCore Memory...")
        agentcore_messages = get_agentcore_memory_messages(
            memory_id, user_id, session_id, last_k_turns
        )

        print("📋 CONVERSATION CONTEXT LOADED:")
        print("-" * 50)
        if agentcore_messages:
            for i, msg in enumerate(agentcore_messages, 1):
                role = msg.get("role", "unknown")
                role_icon = "🤖" if role == "assistant" else "👤"
                content_text = ""
                if "content" in msg and msg["content"]:
                    for content_item in msg["content"]:
                        if "text" in content_item:
                            content_text = content_item["text"]
                            break
                content_preview = (
                    f"{content_text[:80]}..."
                    if len(content_text) > 80
                    else content_text
                )
                print(f"   {i}. {role_icon} {role.upper()}: {content_preview}")
        else:
            print("   📭 Starting new conversation (no previous context)")
        print("-" * 50)

        # Configure system prompt with user's timezone context
        print("📝 Configuring video game sales analyst system prompt...")
        system_prompt = DATA_ANALYST_SYSTEM_PROMPT.replace("{timezone}", user_timezone)
        print(
            f"✅ System prompt configured for video game sales analysis ({len(system_prompt)} characters)"
        )

        print("-" * 80)
        print("🔧 Initializing video game sales analyst agent...")

        # Create specialized agent with video game sales analysis capabilities
        agent = Agent(
            messages=agentcore_messages,
            model=bedrock_model,
            system_prompt=system_prompt,
            hooks=[MemoryHookProvider(memory_id, user_id, session_id, last_k_turns)],
            tools=[
                get_tables_information,
                current_time,
                create_execute_sql_query_tool(user_message, prompt_uuid),
            ],
            callback_handler=None,
        )

        print("✅ Video game sales analyst agent ready with:")
        print(f"   📝 {len(agentcore_messages)} conversation context messages")
        print(
            "   🔧 3 specialized tools (database schema, time utilities, SQL execution)"
        )
        print("   🧠 Conversation memory management enabled")

        print("-" * 80)
        print("🚀 Starting video game sales data analysis...")
        print("=" * 80)

        # Stream the response
        tool_active = False

        async for item in agent.stream_async(user_message):
            if "event" in item:
                event = item["event"]

                # Check for tool start
                if "contentBlockStart" in event and "toolUse" in event[
                    "contentBlockStart"
                ].get("start", {}):
                    tool_active = True
                    event_formatted = {"event": event}
                    yield json.dumps(event_formatted) + "\n"

                # Check for tool end
                elif "contentBlockStop" in event and tool_active:
                    tool_active = False

                    event_formatted = {"event": event}
                    yield json.dumps(event_formatted) + "\n"

            elif "start_event_loop" in item:
                yield json.dumps(item) + "\n"
            elif "current_tool_use" in item and tool_active:
                yield json.dumps(item["current_tool_use"]) + "\n"
            elif "data" in item:
                yield json.dumps({"data": item["data"]}) + "\n"

    except Exception as e:
        import traceback

        tb = traceback.extract_tb(e.__traceback__)
        filename, line_number, function_name, text = tb[-1]
        error_message = f"Error: {str(e)} (Line {line_number} in {filename})"
        print("\n" + "=" * 80)
        print("💥 VIDEO GAME SALES ANALYSIS ERROR")
        print("=" * 80)
        print(f"❌ Error: {str(e)}")
        print(f"� Locatiion: Line {line_number} in {filename}")
        print(f"🔧 Function: {function_name}")
        if text:
            print(f"💻 Code: {text}")
        print("=" * 80 + "\n")
        yield f"I apologize, but I encountered an error while analyzing your video game sales data request: {error_message}"


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🚀 STARTING VIDEO GAMES SALES DATA ANALYST ASSISTANT")
    print("=" * 80)
    print("📡 Server starting on port 8080...")
    print("🌐 Health check endpoint: /ping")
    print("🎯 Analysis endpoint: /invocations")
    print("📋 Ready to analyze video game sales trends and insights!")
    print("=" * 80)
    app.run()
