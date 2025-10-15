#!/usr/bin/env python3

import json
import logging
import os
import psycopg2
import requests
from typing import Dict, Any

from strands import Agent, tool
import boto3
from flask import Flask, request, jsonify
from flask_cors import CORS
from opentelemetry import baggage, context
from opentelemetry.context import attach

# Detect deployment mode
DEPLOYMENT_MODE = os.getenv('DEPLOYMENT_MODE', 'ecs')  # 'ecs', 'eks'

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000"}}, supports_credentials=True)

# Force Flask to show application logs in container
import sys
sys.stdout = sys.__stdout__
sys.stderr = sys.__stderr__
app.logger.setLevel(logging.DEBUG)

# Configure Strands observability (optional)
try:
    from strands.observability import configure_tracer
    configure_tracer()
    print("[OTEL] ✅ Strands observability configured")
except ImportError:
    print("[OTEL] ℹ️ Using ADOT auto-instrumentation for observability")
except Exception as e:
    print(f"[OTEL] ⚠️ Observability configuration failed: {e}")
    print("[OTEL] ℹ️ Falling back to ADOT auto-instrumentation")

# Global schema cache
schema_cache = None

print(f"[{DEPLOYMENT_MODE.upper()}] ✅ Flask app created successfully")

# amazonq-ignore-next-line
def get_system_prompt():
    """Generate system prompt with current database schema"""
    schema = discover_schema()
    return f"""
You are a multi-modal chat assistant with access to database and web search capabilities.

IMPORTANT: You have two tools available:
1. execute_sql_query - for database queries
2. search_web - for web searches

CURRENT DATABASE SCHEMA:
{schema}

You MUST use these tools to get real data. DO NOT make up or hallucinate any data.

For database queries:
- CRITICAL: ONLY use tables that appear in the schema above - NO OTHER TABLES EXIST
- Use the schema above to understand available tables and columns
- Generate appropriate PostgreSQL queries based on user questions
- Use proper table and column names from the schema
- Query each table SEPARATELY unless you see explicit foreign key relationships in the schema
- Do NOT assume relationships between tables based on similar column names
- Only use JOINs when the schema explicitly shows foreign key constraints

WORKFLOW:
1. Review conversation history (if available) to understand context
2. MANDATORY: You MUST call at least one tool (execute_sql_query or search_web) for EVERY new question
3. CRITICAL: For ANY question about sales, revenue, customers, or products, you MUST call execute_sql_query FIRST to check our internal data
4. Use search_web for industry trends, market data, or external context
5. Synthesize tool results with conversation context into a comprehensive response
6. Return your complete analysis as JSON

# amazonq-ignore-next-line
🚨 CRITICAL RULE: NO RESPONSE WITHOUT TOOL CALLS 🚨
- Conversation history provides CONTEXT ONLY - it does NOT replace tool calls
- You MUST call tools for EVERY new question, even if similar questions were asked before
- Memory helps you understand what the user is asking, but you still need fresh data from tools
- EVERY response must be based on actual tool outputs from THIS conversation turn

CRITICAL: After using all necessary tools, you must return your FINAL response as VALID JSON in this exact format:
{{
  "content": "Your comprehensive analysis that MUST incorporate insights from EVERY tool you used. If you used execute_sql_query, you MUST include the database insights. If you used search_web, you MUST include web research findings.",
  "sources": [
    {{"type": "database", "name": "Sales Database"}},
    {{"type": "web", "title": "EXACT title from search_web tool results", "url": "EXACT URL from search_web tool results"}}
  ]
}}

CRITICAL JSON SYNTAX RULES:
- ALL string values MUST be enclosed in double quotes
- The content field value MUST be a quoted string: "content": "your text here"
- Do NOT write: "content": your text here (missing quotes)
- Use proper JSON syntax with commas between fields

🚨 OUTPUT IN JSON FORMAT - MANDATORY 🚨

Return the data as a JSON object. Ensure the response is valid JSON.

JSON SCHEMA REQUIRED:
{{
  "content": "string - your comprehensive analysis incorporating ALL tool results",
  "sources": [
    // Include a source entry for EVERY tool you actually used:
    {{"type": "database", "name": "Sales Database"}},
    {{"type": "web", "title": "exact title from search results", "url": "exact URL"}},
    {{"type": "api", "name": "API name", "endpoint": "endpoint used"}},
    {{"type": "file", "name": "filename", "path": "file path"}}
    // Add any other source types as needed based on tools used
  ]
}}

CRITICAL JSON REQUIREMENTS:
- Output ONLY valid JSON starting with {{ and ending with }}
- NO text before or after the JSON object
- NO XML tags, explanations, or commentary outside JSON
- Include "content" field with your analysis as a string
- Include "sources" array with entries for every tool used
- Use exact titles/URLs from tool results in sources

STRICT RULES:
- You MUST call execute_sql_query for any database-related questions
- You MUST call search_web for any web search needs

- MANDATORY: If you call execute_sql_query and get results, you MUST incorporate those database insights into your final response content
- MANDATORY: If you call search_web and get results, you MUST incorporate those web insights into your final response content
- SYNTHESIZE all tool results into ONE comprehensive response - DO NOT ignore any tool results
- Include specific numbers, percentages, and data from ALL tools used
- Provide actionable insights based on the combined data from ALL sources
- You MUST include sources for EVERY tool you actually used
- NEVER put document filenames in quotes within the content text - reference them without quotes or mention them only in the sources array
- You MUST ONLY use the exact URLs returned by the search_web tool in the "results" array
- You MUST ONLY use the exact titles returned by the search_web tool in the "results" array  

- NEVER create, invent, or hallucinate any URLs, titles, or document names
- If search_web returns no results, do not include web sources

- ONLY copy the exact "url" and "title" fields from actual search_web tool responses

- CRITICAL: Only reference sources that actually appear in tool outputs - NO EXCEPTIONS
- HALLUCINATING SOURCES IS STRICTLY FORBIDDEN AND WILL CAUSE SYSTEM FAILURE
- If you did not call a tool, do not include sources for that tool type
- If a tool returned no relevant results, do not fabricate sources
- VERIFICATION REQUIRED: Before adding any source, verify it appeared in actual tool output
- MEMORY IS NOT A SOURCE: Do not create sources based on conversation memory
- NO TOOL CALL = NO SOURCE: If you didn't execute a tool, don't claim you did
- TOOL CALL VERIFICATION: If you didn't call search_web, you CANNOT reference web sources

- TOOL CALL VERIFICATION: If you didn't call execute_sql_query, you CANNOT reference database sources
- NO EXTERNAL KNOWLEDGE: Do not use your training data to create fake sources - only use actual tool results
- SOURCE AUDIT: Before finalizing response, audit each source against actual tool outputs from THIS conversation turn
- FABRICATED SOURCES = SYSTEM FAILURE: Creating sources not returned by tools will cause critical system failure

🔥 FINAL RESPONSE ENFORCEMENT 🔥
Your response must be EXACTLY:
{{ "content": "...", "sources": [...] }}
ANYTHING ELSE WILL CAUSE A SYSTEM FAILURE

🚨 MANDATORY SOURCE VERIFICATION PROTOCOL 🚨
BEFORE including ANY source in your response:
1. VERIFY you actually called the corresponding tool in THIS conversation turn
2. VERIFY the source appears in the actual tool output
3. If you did NOT call execute_sql_query, you CANNOT include database sources
4. If you did NOT call search_web, you CANNOT include web sources  

6. NO EXCEPTIONS - Sources must come from actual tool calls in THIS turn
7. CONVERSATION MEMORY IS NOT A VALID SOURCE
8. YOUR TRAINING DATA IS NOT A VALID SOURCE
9. ONLY REAL TOOL OUTPUTS FROM THIS TURN ARE VALID SOURCES
10. IF YOU USE MEMORY: State clearly "Based on our previous conversation" and do NOT include sources array
11. IF YOU USE TOOLS: Include only sources from actual tool calls in THIS turn
12. NEVER CLAIM TO HAVE CALLED TOOLS WHEN YOU USED MEMORY INSTEAD
"""

def get_database_connection():
    """Get database connection"""
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        return psycopg2.connect(database_url)
    else:
        return psycopg2.connect(
            host=os.getenv('DB_HOST', 'postgres'),
            port=os.getenv('DB_PORT', 5432),
            database=os.getenv('DB_NAME', 'sales_db'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'postgres')
        )

# amazonq-ignore-next-line
def discover_schema():
    """Dynamically discover database schema for all tables"""
    # amazonq-ignore-next-line
    global schema_cache
    if schema_cache:
        print('📋 Using cached schema')
        return schema_cache
    
    print('🔍 Discovering database schema dynamically...')
    # amazonq-ignore-next-line
    conn = get_database_connection()
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("""
        SELECT 
            table_name,
            table_type,
            obj_description(c.oid) as table_comment
        FROM information_schema.tables t
        LEFT JOIN pg_class c ON c.relname = t.table_name
        WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    tables = cursor.fetchall()
    print(f'📊 Found {len(tables)} tables: {[t[0] for t in tables]}')
    
    schema_description = 'Database Schema:\n\n'
    
    for table_name, table_type, table_comment in tables:
        print(f'🔍 Analyzing table: {table_name}')
        
        # Get table schema
        cursor.execute("""
            SELECT 
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.column_default,
                col_description(pgc.oid, c.ordinal_position) as column_comment
            FROM information_schema.columns c
            LEFT JOIN pg_class pgc ON pgc.relname = c.table_name
            WHERE c.table_name = %s
                AND c.table_schema = 'public'
            ORDER BY c.ordinal_position
        """, (table_name,))
        columns = cursor.fetchall()
        
        # amazonq-ignore-next-line
        schema_description += f'Table: {table_name}\n'
        if table_comment:
            schema_description += f'Description: {table_comment}\n'
        
        schema_description += 'Columns:\n'
        for col_name, data_type, is_nullable, col_default, col_comment in columns:
            schema_description += f'- {col_name} ({data_type}'
            if is_nullable == 'NO':
                schema_description += ', NOT NULL'
            if col_default:
                schema_description += f', DEFAULT {col_default}'
            if col_comment:
                schema_description += f', -- {col_comment}'
            schema_description += ')\n'
        
        # Add sample data
        try:
            # amazonq-ignore-next-line
            cursor.execute(f'SELECT * FROM "{table_name}" LIMIT 2')
            sample_data = cursor.fetchall()
            if sample_data:
                col_names = [desc[0] for desc in cursor.description]
                sample_dict = [dict(zip(col_names, row)) for row in sample_data]
                schema_description += f'Sample Data:\n{json.dumps(sample_dict, default=str, indent=2)}\n'
                print(f'✅ Added sample data for {table_name}')
        except Exception as e:
            print(f'⚠️ Could not get sample data for {table_name}: {e}')
        
        schema_description += '\n'
    
    cursor.close()
    conn.close()
    
    print('✅ Schema discovery complete')
    schema_cache = schema_description
    return schema_cache

@tool
def execute_sql_query(sql_query: str) -> str:
    """Execute a SQL query on the PostgreSQL database. The system will automatically provide you with the current database schema including all tables, columns, and sample data when you need to generate SQL queries."""
    print("\n" + "="*50)
    print("🔥 EXECUTE_SQL_QUERY TOOL CALLED!")
    print(f"🔥 SQL Query: {sql_query}")
    print("="*50 + "\n")
    try:
        # Debug: Print connection details
        database_url = os.getenv('DATABASE_URL')
        print(f"[DB Debug] DATABASE_URL exists: {bool(database_url)}")
        if database_url:
            print(f"[DB Debug] Using DATABASE_URL connection")
            # amazonq-ignore-next-line
            conn = get_database_connection()
        else:
            print(f"[DB Debug] Using individual env vars")
            conn = get_database_connection()
        
        print(f"[DB Debug] Connection successful")
        print(f"[DB Debug] Executing SQL: {sql_query}")
        
        # amazonq-ignore-next-line
        cursor = conn.cursor()
        cursor.execute(sql_query)
        results = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        data = [dict(zip(columns, row)) for row in results]
        print(f"[DB Debug] Query returned {len(data)} rows")
        
        cursor.close()
        conn.close()
        
        response = {
            "data": data,
            "sql_query": sql_query,
            "source": "PostgreSQL Database",
            "record_count": len(data)
        }
        
        return json.dumps(response, default=str)
        
    except Exception as e:
        error_msg = f"Database query failed: {str(e)}"
        print(f"[DB Debug] {error_msg}")
        return json.dumps({"error": error_msg})

@tool
def search_web(query: str) -> str:
    """Search the web for information related to the query using Brave Search API"""
    print("\n" + "="*50)
    print("🔥 SEARCH_WEB TOOL CALLED WITH QUERY ONLY!")
    print(f"🔥 Query: {query}")
    print("="*50 + "\n")
    
    all_results = []
    
    try:
        print("[Web Search Debug] Using Brave Search API...")
        
        # Get Brave Search API key from environment
        brave_api_key = os.getenv('BRAVE_SEARCH_API_KEY')
        if not brave_api_key:
            print("[Web Search Debug] ❌ BRAVE_SEARCH_API_KEY not found in environment")
            return json.dumps({"error": "Brave Search API key not configured"})
        
        print(f"[Web Search Debug] Starting Brave search for: '{query}'")
        
        # Brave Search API endpoint
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": brave_api_key
        }
        params = {
            "q": query,
            # amazonq-ignore-next-line
            "count": 3
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        # amazonq-ignore-next-line
        print(f"[Web Search Debug] Brave API response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            web_results = data.get('web', {}).get('results', [])
            print(f"[Web Search Debug] Brave search returned {len(web_results)} results")
            
            for i, result in enumerate(web_results):
                search_result = {
                    'title': result.get('title', '')[:100],
                    'url': result.get('url', ''),
                    'snippet': result.get('description', '')[:200],
                    'source': 'Web Search'
                }
                all_results.append(search_result)
                print(f"[Web Search Debug] Result {i+1}: {search_result['title']} - {search_result['url']}")
                
        elif response.status_code == 429:
            print("[Web Search Debug] ❌ Rate limit exceeded for Brave Search API")
            return json.dumps({"error": "Brave Search API rate limit exceeded"})
        else:
            print(f"[Web Search Debug] ❌ Brave API error: {response.status_code} - {response.text}")
            return json.dumps({"error": f"Brave Search API error: {response.status_code}"})
                
    # amazonq-ignore-next-line
    except Exception as search_error:
        print(f"[Web Search Debug] ❌ Brave search error: {search_error}")
        import traceback
        print(f"[Web Search Debug] Traceback: {traceback.format_exc()}")
        return json.dumps({"error": f"Brave search failed: {search_error}"})
    
    response = {
        "query": query,
        "results": all_results,
        "source": "Web Search",
        "total_results": len(all_results)
    }
    
    print(f"[Web Search Debug] Returning {len(all_results)} results:")
    for i, result in enumerate(all_results):
        print(f"[Web Search Debug] Result {i+1}: {result['title']} - {result['url']}")
    
    print(f"[Web Search Debug] FULL RESPONSE TO AGENT:")
    print(json.dumps(response, indent=2)[:500] + "...")
    
    result = json.dumps(response)
    print(f"[Web Search Debug] Final JSON length: {len(result)}")
    return result



@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "runtime": f"Strands {DEPLOYMENT_MODE.upper()}"})

@app.route('/api/chat/message', methods=['POST'])
def chat_message():
    """Frontend-compatible chat endpoint"""
    try:
        data = request.get_json()
        user_message = data.get('message')  # Frontend sends 'message'
        session_id = data.get('sessionId')
        user_id = data.get('userId', 'anonymous')
        
        # Call the main invoke function
        return invoke_agent(user_message, session_id, user_id)
    except Exception as e:
        print(f"[{DEPLOYMENT_MODE.upper()} Runtime] Chat API ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/invoke', methods=['POST'])
def invoke():
    """Direct invoke endpoint"""
    try:
        data = request.get_json()
        user_message = data.get('prompt')
        session_id = data.get('sessionId')
        user_id = data.get('userId', 'anonymous')
        
        return invoke_agent(user_message, session_id, user_id)
    except Exception as e:
        print(f"[{DEPLOYMENT_MODE.upper()} Runtime] Invoke ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

# amazonq-ignore-next-line
def invoke_agent(user_message, session_id, user_id):
    """Core agent invocation logic"""
    try:
        
        if not user_message:
            return jsonify({"error": "No message provided"}), 400
        
        print(f"[{DEPLOYMENT_MODE.upper()} Runtime] Processing: {user_message}")
        print(f"[{DEPLOYMENT_MODE.upper()} Runtime] Session: {session_id}, User: {user_id}")
        
        # Set session ID in OTEL baggage for observability
        if session_id:
            ctx = baggage.set_baggage("session.id", session_id)
            attach(ctx)
            print(f"[OTEL] Set session.id in baggage: {session_id}")
        
        # Initialize AgentCore Memory for containerized deployment
        # amazonq-ignore-next-line
        global memory_id
        if not memory_id:
            try:
                print(f"🔄 Initializing AgentCore memory: {MEMORY_NAME}")
                memories = memory_client.list_memories()
                memory_id = next((m['id'] for m in memories if m['id'].startswith(MEMORY_NAME)), None)
                
                if memory_id:
                    print(f"✅ Found existing AgentCore memory: {memory_id}")
                else:
                    print(f"🔄 Creating new AgentCore memory: {MEMORY_NAME}")
                    memory = memory_client.create_memory_and_wait(
                        name=MEMORY_NAME,
                        strategies=[],
                        description="Short-term memory for sales assistant",
                        event_expiry_days=30
                    )
                    memory_id = memory['id']
                    print(f"✅ Created AgentCore memory: {memory_id}")
            # amazonq-ignore-next-line
            except Exception as e:
                print(f"❌ Memory initialization failed: {e}")
                memory_id = None
        
        # Create agent with AgentCore Memory hooks
        hooks = []
        if memory_id:
            hooks.append(MemoryHookProvider(memory_client, memory_id))
        
        # amazonq-ignore-next-line
        agent = Agent(
            model="anthropic.claude-3-sonnet-20240229-v1:0",
            system_prompt=get_system_prompt(),
            tools=[execute_sql_query, search_web],
            hooks=hooks,
            state={"actor_id": user_id, "session_id": session_id}
        )
        
        # Invoke agent
        response = agent(user_message)
        result = response.message['content'][0]['text']
        
        # amazonq-ignore-next-line
        # Clean and validate JSON
        import re
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            json_str = json_match.group(0)
            print(f"[{DEPLOYMENT_MODE.upper()} Runtime] Original JSON length: {len(json_str)}")
            
            # Clean control characters and normalize whitespace
            cleaned_json = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
            cleaned_json = re.sub(r'\s+', ' ', cleaned_json)
            
            # Fix unescaped quotes in content field
            try:
                # Parse and re-serialize to fix escaping
                parsed = json.loads(cleaned_json)
                cleaned_json = json.dumps(parsed, ensure_ascii=False)
            except json.JSONDecodeError:
                # Manual quote escaping as fallback
                cleaned_json = re.sub(r'"([^"]*?)"([^"]*?)"([^"]*?)"', r'"\1\\"\2\\"\3"', cleaned_json)
            
            try:
                json.loads(cleaned_json)
                result = cleaned_json
                print(f"[{DEPLOYMENT_MODE.upper()} Runtime] JSON validation successful")
            except json.JSONDecodeError as e:
                print(f"[{DEPLOYMENT_MODE.upper()} Runtime] JSON validation failed: {e}")
                print(f"[{DEPLOYMENT_MODE.upper()} Runtime] Keeping original response")
        
        # Parse the agent result and format for frontend compatibility
        print(f"[{DEPLOYMENT_MODE.upper()} Runtime] Final result for parsing: {result[:200]}...")
        try:
            parsed_result = json.loads(result)
            print(f"[{DEPLOYMENT_MODE.upper()} Runtime] Successfully parsed JSON")
            # Format response to match working frontend expectations
            streaming_response = {
                "type": "complete",
                "response": {
                    "answer": parsed_result.get("content", ""),
                    "sources": parsed_result.get("sources", []),
                    "reasoning": [],
                    "citations": []
                },
                "timestamp": "2025-10-03T04:26:37.529Z"
            }
            print(f"[{DEPLOYMENT_MODE.upper()} Runtime] Returning streaming response")
            return jsonify(streaming_response)
        except json.JSONDecodeError as e:
            print(f"[{DEPLOYMENT_MODE.upper()} Runtime] JSON parse error: {e}")
            print(f"[{DEPLOYMENT_MODE.upper()} Runtime] Error at position {e.pos}: {repr(result[max(0, e.pos-50):e.pos+50]) if hasattr(e, 'pos') else 'N/A'}")
            # If not valid JSON, return error format
            error_response = {
                "type": "error",
                "error": f"Failed to parse agent response: {str(e)}"
            }
            return jsonify(error_response)
        
    except Exception as e:
        print(f"[{DEPLOYMENT_MODE.upper()} Runtime] Agent ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Agent will be created per request to ensure fresh schema discovery
agent = None

# AgentCore Memory configuration
from strands.hooks import AgentInitializedEvent, HookProvider, HookRegistry, MessageAddedEvent
from bedrock_agentcore.memory import MemoryClient

# Memory configuration
REGION = os.getenv('AWS_REGION', 'ap-southeast-2')
MEMORY_NAME = "SalesAnalystMemory"

# Initialize Memory Client
# amazonq-ignore-next-line
memory_client = MemoryClient(region_name=REGION)
memory_id = None

# Memory will be initialized per request to ensure proper logging
memory_id = None

class MemoryHookProvider(HookProvider):
    def __init__(self, memory_client: MemoryClient, memory_id: str):
        self.memory_client = memory_client
        self.memory_id = memory_id
    
    def on_agent_initialized(self, event: AgentInitializedEvent):
        """Load recent conversation history when agent starts"""
        try:
            actor_id = event.agent.state.get("actor_id")
            session_id = event.agent.state.get("session_id")
            
            if not actor_id or not session_id or not self.memory_id:
                return
            
            recent_turns = self.memory_client.get_last_k_turns(
                memory_id=self.memory_id,
                actor_id=actor_id,
                session_id=session_id,
                # amazonq-ignore-next-line
                k=6  # Last 6 turns for context
            )
            
            if recent_turns:
                context_messages = []
                for turn in recent_turns:
                    for message in turn:
                        role = message['role']
                        # amazonq-ignore-next-line
                        content = message['content']['text']
                        context_messages.append(f"{role}: {content}")
                
                context = "\n".join(context_messages)
                event.agent.system_prompt += f"\n\nPREVIOUS CONVERSATION CONTEXT:\n{context}\n\nCURRENT QUESTION:\n"
                # amazonq-ignore-next-line
                print(f"✅ Loaded {len(recent_turns)} conversation turns from AgentCore Memory")
                
        except Exception as e:
            if "Memory not found" in str(e):
                print(f"❌ Memory not found during load, recreating: {e}")
                self._recreate_memory()
            else:
                print(f"❌ Memory load error: {e}")
    
    def on_message_added(self, event: MessageAddedEvent):
        """Store messages in AgentCore Memory"""
        try:
            messages = event.agent.messages
            actor_id = event.agent.state.get("actor_id")
            session_id = event.agent.state.get("session_id")

            # amazonq-ignore-next-line
            if messages and messages[-1]["content"][0].get("text") and self.memory_id:
                self.memory_client.create_event(
                    memory_id=self.memory_id,
                    actor_id=actor_id,
                    session_id=session_id,
                    messages=[(messages[-1]["content"][0]["text"], messages[-1]["role"])]
                )
        except Exception as e:
            # amazonq-ignore-next-line
            if "Memory not found" in str(e):
                print(f"❌ Memory not found, recreating: {e}")
                self._recreate_memory()
            else:
                print(f"❌ Memory save error: {e}")
    
    def _recreate_memory(self):
        """Recreate memory if it was deleted"""
        try:
            # amazonq-ignore-next-line
            global memory_id
            print(f"🔄 Recreating AgentCore memory: {MEMORY_NAME}")
            memory = self.memory_client.create_memory_and_wait(
                name=MEMORY_NAME,
                strategies=[],
                description="Short-term memory for sales assistant",
                event_expiry_days=30
            )
            # amazonq-ignore-next-line
            memory_id = memory['id']
            self.memory_id = memory_id
            print(f"✅ Recreated AgentCore memory: {memory_id}")
        # amazonq-ignore-next-line
        except Exception as e:
            print(f"❌ Failed to recreate memory: {e}")
    
    def register_hooks(self, registry: HookRegistry):
        registry.add_callback(MessageAddedEvent, self.on_message_added)
        registry.add_callback(AgentInitializedEvent, self.on_agent_initialized)

# AgentCore entry point (only works when app is BedrockAgentCoreApp)
# amazonq-ignore-next-line
def agentcore_invoke(payload):
    """Handler for agent invocation"""
    try:
        print(f"[AgentCore Runtime] Received payload: {payload}")
        
        # Extract message and session ID
        user_message = payload.get('prompt')
        session_id = payload.get('sessionId')
        
        if not user_message:
            messages = payload.get('messages', [])
            user_message = messages[0]['content'] if messages else payload.get('inputText', '')
        
        if not user_message:
            print(f"[AgentCore Runtime] No prompt found in payload")
            return "No prompt found in input, please provide a message"
        
        # Extract user ID from payload for AgentCore Memory
        user_id = payload.get('userId') or payload.get('user_id')
        actor_id = user_id or session_id or "anonymous_user"
        
        print(f"[AgentCore Runtime] Processing message: {user_message}")
        print(f"[AgentCore Runtime] Session ID: {session_id}")
        print(f"[AgentCore Runtime] User ID: {user_id}")
        print(f"[AgentCore Runtime] Actor ID: {actor_id}")
        contextual_message = user_message
        
        # Initialize memory if not already done
        # amazonq-ignore-next-line
        global memory_id
        # amazonq-ignore-next-line
        if not memory_id:
            try:
                print(f"🔄 Initializing AgentCore memory: {MEMORY_NAME}")
                memories = memory_client.list_memories()
                memory_id = next((m['id'] for m in memories if m['id'].startswith(MEMORY_NAME)), None)
                
                if memory_id:
                    print(f"✅ Found existing AgentCore memory: {memory_id}")
                else:
                    print(f"🔄 Creating new AgentCore memory: {MEMORY_NAME}")
                    memory = memory_client.create_memory_and_wait(
                        name=MEMORY_NAME,
                        strategies=[],
                        description="Short-term memory for sales assistant",
                        event_expiry_days=30
                    )
                    memory_id = memory['id']
                    print(f"✅ Created AgentCore memory: {memory_id}")
            except Exception as e:
                print(f"❌ Memory initialization failed: {e}")
                memory_id = None
        else:
            print(f"✅ Using existing memory: {memory_id}")
        
        # Schema will be cached after first discovery
        
        # Create agent with AgentCore Memory hooks
        print('🔥 INITIALIZING AGENT WITH DYNAMIC SCHEMA DISCOVERY')
        print('='*60)
        
        hooks = []
        if memory_id:
            hooks.append(MemoryHookProvider(memory_client, memory_id))
            print(f"✅ Added memory hook with ID: {memory_id}")
        
        # amazonq-ignore-next-line
        agent = Agent(
            model="anthropic.claude-3-sonnet-20240229-v1:0",
            system_prompt=get_system_prompt(),
            tools=[execute_sql_query, search_web],
            hooks=hooks,
            state={"actor_id": actor_id, "session_id": session_id}
        )
        print('✅ Agent initialized with dynamic schema and AgentCore Memory')
        print('='*60)
        
        # Invoke the agent with OTEL tracing
        print("🚀 INVOKING AGENT NOW...")
        try:
            from opentelemetry import trace
            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span("agent_invoke") as span:
                span.set_attribute("session_id", session_id or "unknown")
                span.set_attribute("user_id", user_id or "unknown")
                span.add_event("Agent invocation started")
                response = agent(contextual_message)
                span.add_event("Agent invocation completed")
                print("[OTEL] ✅ Agent invocation traced")
        # amazonq-ignore-next-line
        except Exception as otel_error:
            print(f"[OTEL] ⚠️ Tracing failed: {otel_error}")
            response = agent(contextual_message)
        
        print("✅ AGENT INVOCATION COMPLETE")
        print(f"[AgentCore Runtime] Agent response type: {type(response)}")
        
        # Parse and clean the JSON response
        result = response.message['content'][0]['text']
        print(f"[AgentCore Runtime] Raw result length: {len(result)}")
        
        # Extract and clean JSON object from response
        import re
        import json
        
        # Remove debug reflection text that shouldn't be in final response
        result = re.sub(r'<search_quality_reflection>.*?</search_quality_reflection>', '', result, flags=re.DOTALL)
        result = re.sub(r'<search_quality_score>.*?</search_quality_score>', '', result, flags=re.DOTALL)
        
        # amazonq-ignore-next-line
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            json_str = json_match.group(0)
            print(f"[AgentCore Runtime] Original JSON length: {len(json_str)}")
            print(f"[AgentCore Runtime] First 200 chars: {repr(json_str[:200])}")
            
            # Clean control characters and normalize whitespace
            cleaned_json = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
            cleaned_json = re.sub(r'\s+', ' ', cleaned_json)
            
            # Fix unescaped quotes in content field
            try:
                # Parse and re-serialize to fix escaping
                parsed = json.loads(cleaned_json)
                cleaned_json = json.dumps(parsed, ensure_ascii=False)
            except json.JSONDecodeError:
                # Manual quote escaping as fallback
                cleaned_json = re.sub(r'"([^"]*?)"([^"]*?)"([^"]*?)"', r'"\1\\"\2\\"\3"', cleaned_json)
            print(f"[AgentCore Runtime] Cleaned JSON length: {len(cleaned_json)}")
            print(f"[AgentCore Runtime] Cleaned first 200 chars: {repr(cleaned_json[:200])}")
            
            try:
                json.loads(cleaned_json)
                result = cleaned_json
                print(f"[AgentCore Runtime] JSON validation successful")
            except json.JSONDecodeError as e:
                print(f"[AgentCore Runtime] JSON validation failed: {e}")
                print(f"[AgentCore Runtime] Error at position {e.pos}: {repr(cleaned_json[max(0, e.pos-50):e.pos+50])}")
                print(f"[AgentCore Runtime] Keeping original response")
        else:
            print(f"[AgentCore Runtime] No JSON object found in response")
        
        # AgentCore Memory handles conversation storage automatically via hooks
        print(f"[AgentCore Runtime] Conversation stored in AgentCore Memory for user: {actor_id}, session: {session_id}")
        
        # For AgentCore, return the raw response (it handles JSON parsing)
        return result
        
    except Exception as e:
        print(f"[AgentCore Runtime] ERROR: {str(e)}")
        import traceback
        print(f"[AgentCore Runtime] Traceback: {traceback.format_exc()}")
        return f"Error processing request: {str(e)}"

if __name__ == "__main__":
    # Force unbuffered output for container logging
    import sys
    sys.stdout.flush()
    sys.stderr.flush()
    
    print(f"[{DEPLOYMENT_MODE.upper()} Runtime] Starting Strands Agent with ADOT observability")
    print(f"[{DEPLOYMENT_MODE.upper()} Runtime] Available tools: execute_sql_query, search_web")
    print(f"[{DEPLOYMENT_MODE.upper()} Runtime] Deployment mode: {DEPLOYMENT_MODE}")
    # amazonq-ignore-next-line
    app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=False)