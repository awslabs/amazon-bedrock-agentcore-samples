# This is the operations agent that is responsible for
# getting the latest status from the JIRA dashboard and then
# provide some documentation and remediation on the solution.
# It does the follows: 
# 1. It provides documentation and reports on the fixes on the JIRA ticket
# by searching the web for AWS documentation.
# 2. It provides the documentation and updates on slack as there are any updates.
# In this case, this agent acts as an ambient agent.
import os
import sys
import json
import uuid
import time
import glob
import boto3
import shutil
import logging
import base64
import asyncio
import argparse
import uvicorn
import datetime
from dotenv import load_dotenv
from typing import Dict, Any, Optional, AsyncIterator
from starlette.responses import JSONResponse
# To correlate traces across multiple agent runs,
# we will associate a session ID with our telemetry data using the
# Open Telemetry baggage
from opentelemetry import context, baggage
from botocore.exceptions import ClientError

# these are imports from the A2A library to instantiate the this agent
# as an A2A server
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.agent_execution.agent_executor import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

# Load environment variables first (fallback)
load_dotenv()

# This is a parse argument function which will take in arguments for example the session id 
# in this case. A session is a complete interaction consisting of traces and spans within a 
# user interaction with an agent
def parse_arguments():
    try:
        logger.info("Parsing CLI args")
        parser = argparse.ArgumentParser(description="Monitoring agent with session tracking")
        parser.add_argument("--session_id", type=str, default=str(uuid.uuid4()),
                            help="Session ID for the agent")
        parser.add_argument("--interactive", action="store_true",
                            help="Run an interactive CLI chat instead of the HTTP server")
        args = parser.parse_args()
        if not args.session_id:
            args.session_id = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
            print(f"Session ID not provided, generating a new one: {args.session_id}")
        return args
    except Exception as e:
        logger.error(f"Error while parsing arguments: {e}")
        raise

# Now, assuming that this agent is running in agentcore runtime or in compute or containers outside of 
# agentcore, we will need to enable observability for adding baggage for OTEL compatible tracing and logging
def set_session_context(session_id: str):
    """
    This sets the session ID in OpenTelemetry baggage for trace correlation.
    This function is used to set the baggage for the context session id that is provided as an 
    OTEL metric for tracking agents that are hosted outside of Bedrock Agentcore runtime
    """
    try:
        # create the context session id
        ctx = baggage.set_baggage("session_id", session_id)
        token = context.attach(ctx)
        logger.info(f"Session ID set in baggage: {session_id}")
    except Exception as e:
        logger.error(f"Error while setting session context: {e}")
        raise e
    return token

# We will now initialize the OTEL variables that will be used from the
# environment variables to enable python distro, python configurator,
# protocol over which the telemetry data will be sent,
# the headers (session id, trace id, etc), etc.
# Disable OTLP trace exporter to prevent CloudWatch Logs configuration errors
# This prevents "Failed to export batch code: 400" errors from OTLP exporter
os.environ.setdefault("OTEL_TRACES_EXPORTER", "none")
os.environ.setdefault("OTEL_METRICS_EXPORTER", "none")

# Only show OTEL config in non-interactive mode
if "--interactive" not in sys.argv:
    otel_vars = [
        "OTEL_PYTHON_DISTRO",
        "OTEL_PYTHON_CONFIGURATOR",
        "OTEL_EXPORTER_OTLP_PROTOCOL",
        "OTEL_EXPORTER_OTLP_LOGS_HEADERS",
        "OTEL_RESOURCE_ATTRIBUTES",
        "AGENT_OBSERVABILITY_ENABLED",
        "OTEL_TRACES_EXPORTER"
    ]
    print("Open telemetry configuration:")
    for var in otel_vars:
        value = os.getenv(var)
        if value:
            print(f"{var}: {value}")


from bedrock_agentcore.memory import MemoryClient
# This will help set up for strategies that can then be used 
# across the code - user preferences, semantic memory or even
# summarizations across the sessions along with custom strategies
# for this monitoring agent
from bedrock_agentcore.memory.constants import StrategyType
# Configure the root strands logger
logging.getLogger("strands").setLevel(logging.DEBUG)
# Import Cognito authentication setup from utils
# These are openAI tools created to extract from, retrieve, store and manage memory through
# the amazon bedrock agentcore service
from openAI_memory_tools import create_memory_tools
# Local search functionality only - no gateway dependencies
# define openAI specific import statements
from agents import Agent, Runner

# Add a handler to see the logs
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()]
)

# Suppress OpenTelemetry OTLP exporter errors to prevent error spam
# These errors occur when CloudWatch Logs isn't configured as trace destination
logging.getLogger("opentelemetry.exporter.otlp.proto.http.trace_exporter").setLevel(logging.CRITICAL)
logging.getLogger("opentelemetry.exporter.otlp.proto.http.metric_exporter").setLevel(logging.CRITICAL)

sys.path.insert(0, ".")
sys.path.insert(1, "..")
from utils import *
from constants import *

# Set logger with appropriate level based on mode
if "--interactive" in sys.argv:
    logging.basicConfig(format='%(levelname)s - %(message)s', level=logging.WARNING)
else:
    logging.basicConfig(format='[%(asctime)s] p%(process)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Load the config file.
config_data = load_config('config.yaml')
logger.info(f"Configuration loaded successfully")

# Load API keys from SSM Parameter Store
print("\n" + "="*80)
print("Loading API Keys from AWS Systems Manager Parameter Store")
print("="*80)
api_keys = load_api_keys_from_ssm(config_data)

# Set global variables for API keys
TAVILY_API_KEY = api_keys.get('TAVILY_API_KEY')
OPENAI_API_KEY = api_keys.get('OPENAI_API_KEY')
JIRA_API_KEY = api_keys.get('JIRA_API_KEY')

# Set environment variables for compatibility with libraries that read from os.environ
if TAVILY_API_KEY:
    os.environ['TAVILY_API_KEY'] = TAVILY_API_KEY
if OPENAI_API_KEY:
    os.environ['OPENAI_API_KEY'] = OPENAI_API_KEY
if JIRA_API_KEY:
    os.environ['JIRA_API_KEY'] = JIRA_API_KEY

print("\nAPI Keys Status:")
print(f"TAVILY_API_KEY: {'✅ Loaded' if TAVILY_API_KEY else '❌ Not Found'}")
print(f"OPENAI_API_KEY: {'✅ Loaded' if OPENAI_API_KEY else '❌ Not Found'}")
print(f"JIRA_API_KEY: {'✅ Loaded' if JIRA_API_KEY else '❌ Not Found'}")
print("="*80 + "\n")
from typing import Dict, List

# Initialize observability for this agent
cloudwatch_agent_info: Dict = config_data['cloudwatch_agent_resources']
print(f"Going to use cloudwatch agent info: {cloudwatch_agent_info}")

# initialize the cloudwatch client
cloudwatch_logs_client = boto3.client("logs")
print(f"Initialized the cloudwatch logs client: {cloudwatch_logs_client}")

# Now, let's create the cloudwatch log group, if this log group is already provided
# as an environment variable, it will be used
try:
    response = cloudwatch_logs_client.create_log_group(logGroupName=cloudwatch_agent_info.get('log_group_name'))
    print(f"Created the log group: {response}")
except ClientError as e:
    if e.response['Error']['Code'] == 'ResourceAlreadyExistsException':
        print(f"Log group already exists: {e}")
        # This is expected behavior, continue without error
        pass
    else:
        print(f"Error while creating log group: {e}")
        print("Continuing without creating log group...")
        # Continue execution instead of raising the error
        pass
except Exception as e:
    print(f"Unexpected error while creating log group: {e}")
    print("Continuing without creating log group...")
    # Continue execution for any other unexpected errors
    pass

# Next, we will create a log stream for the same
try:
    response = cloudwatch_logs_client.create_log_stream(
        logGroupName=cloudwatch_agent_info.get('log_group_name'), 
        logStreamName=cloudwatch_agent_info.get('log_stream_name')  
    )
    print(f"Created the log stream: {response}")
except ClientError as e:
    if e.response['Error']['Code'] == 'ResourceAlreadyExistsException':
        print(f"Log stream '{cloudwatch_agent_info.get('log_stream_name')}' already exists, continuing...")
        # This is expected behavior, continue without error
        pass
    else:
        print(f"Error while creating log stream: {e}")
        print("Continuing without creating log stream...")
        # Continue execution instead of raising the error
        pass
except Exception as e:
    print(f"Unexpected error while creating log stream: {e}")
    print("Continuing without creating log stream...")
    # Continue execution for any other unexpected errors
    pass

# ────────────────────────────────────────────────────────────────────────────────────
# AGENTCORE MEMORY INITIALIZATION
# ────────────────────────────────────────────────────────────────────────────────────

# Initialize the memory client
client = MemoryClient(region_name=REGION_NAME)

# Read the custom extraction prompt
def read_prompt_file(filepath: str) -> str:
    with open(filepath, 'r') as f:
        return f.read()

CUSTOM_EXTRACTION_PROMPT = read_prompt_file(OPS_ORCHESTRATOR_CUSTOM_EXTRACTION_PROMPT_FPATH)
print(f"Going to use a custom extraction prompt: {CUSTOM_EXTRACTION_PROMPT}")

# Check if we should use existing memory from config
use_existing_memory = config_data['agent_information']['ops_orchestrator_agent_model_info'].get('use_existing_memory', False)
existing_memory_id = config_data['agent_information']['ops_orchestrator_agent_model_info'].get('memory_credentials', {}).get('id')

# Set the memory and the memory id for initialization
memory_id = None
memory = None

if use_existing_memory and existing_memory_id:
    print(f"Using existing memory from config with ID: {existing_memory_id}")
    memory = {"id": existing_memory_id}
    memory_id = existing_memory_id
else:
    # Create new memory if none exists
    if not memory:
        print("Creating new memory...")
        # Define memory strategies for ops orchestrator agent
        strategies = [
            {
                "userPreferenceMemoryStrategy": {
                    "name": "UserPreference",
                    "namespaces": ["/users/{actorId}"]
                }
            },
            {
                "semanticMemoryStrategy": {
                    "name": "SemanticMemory",
                    "namespaces": ["/knowledge/{actorId}"]
                }
            },
            {
                "summaryMemoryStrategy": {
                    "name": "SessionSummarizer",
                    "namespaces": ["/summaries/{actorId}/{sessionId}"]
                }
            },
            {
                "customMemoryStrategy": {
                    "name": "OpsIssueTracker",
                    "namespaces": ["/technical-issues/{actorId}"],
                    "configuration": {
                        "semanticOverride": {
                            "extraction": {
                                "modelId": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                                "appendToPrompt": CUSTOM_EXTRACTION_PROMPT
                            }
                        }
                    }
                }
            }
        ]

        try:
            logger.info(f"Going to use the following memory execution role: {config_data['agent_information']['ops_orchestrator_agent_model_info'].get('memory_execution_role')}")
            memory = client.create_memory_and_wait(
                name=f"{OPS_ORCHESTRATOR_GATEWAY_NAME}_memory_{int(time.time())}",
                memory_execution_role_arn=config_data['agent_information']['ops_orchestrator_agent_model_info'].get('memory_execution_role'),
                strategies=strategies,
                description="Memory for ops orchestrator agent with custom issue tracking",
                event_expiry_days=7,  # short term conversation expires after 7 days
                max_wait=300,
                poll_interval=10
            )
            # Create and get the memory id
            memory_id = memory.get("id")
            logger.info(f"✅ Created memory: {memory_id}")
        except Exception as e:
            logger.error(f"❌ ERROR creating memory: {e}")
            import traceback
            traceback.print_exc()
            # Cleanup on error - delete the memory if it was partially created
            if memory_id:
                try:
                    client.delete_memory_and_wait(memoryId=memory_id, max_wait=300)
                    logger.info(f"Cleaned up memory: {memory_id}")
                except Exception as cleanup_error:
                    logger.error(f"Failed to clean up memory: {cleanup_error}")
            raise
logger.info(f"Using memory with ID: {memory_id}")

# Continue with the rest of your agent initialization...
print("🚀 Continuing with ops orchestrator multi-agent setup...")

# Load prompt templates
prompt_template_path_lead_agent: str = "prompt_template/ops_orchestrator_agent_prompt.txt"
logger.info(f"Going to read the ops orchestrator agent prompt template from: {prompt_template_path_lead_agent}")
OPS_ORCHESTRATOR_AGENT_SYSTEM_PROMPT = read_prompt_file(prompt_template_path_lead_agent)
print(f"Going to read the ops orchestrator agent prompt template from: {OPS_ORCHESTRATOR_AGENT_SYSTEM_PROMPT}")

# ────────────────────────────────────────────────────────────────────────────────────
# SPECIALIZED AGENT CLASSES FOR OPENAI AGENTS SDK - USING ONLY LOCAL TOOLS
# ────────────────────────────────────────────────────────────────────────────────────
"""
OpenAI Agents SDK implementation with local tools
Agents get only local file search and web search tools - no external dependencies
"""
# Removed requests import - not needed for local tools
from agents import Agent, Runner, function_tool
import os, asyncio, datetime
import httpx
from tavily import TavilyClient

# TAVILY_API_KEY already loaded from SSM Parameter Store above
# Use the global variable set earlier

@function_tool
async def web_search_impl(query: str, top_k: int = 5, recency_days: int | None = None):
    """
    Uses Tavily's search API to return top web results with snippets.
    """
    if not TAVILY_API_KEY:
        raise RuntimeError("Missing TAVILY_API_KEY env var")

    client = TavilyClient(api_key=TAVILY_API_KEY)
    search_kwargs = {
        "query": query,
        "max_results": max(1, min(top_k, 10)),
        "include_domains": None,
        "exclude_domains": None,
    }
    if recency_days:
        # Tavily supports time windows like 'd7', 'd30'
        if recency_days <= 1:
            search_kwargs["time_range"] = "d1"
        elif recency_days <= 7:
            search_kwargs["time_range"] = "d7"
        elif recency_days <= 30:
            search_kwargs["time_range"] = "d30"
        else:
            search_kwargs["time_range"] = "y1"

    res = client.search(**search_kwargs)
    results = []
    for item in res.get("results", []):
        results.append({
            "title": item.get("title"),
            "url": item.get("url"),
            "snippet": item.get("content") or item.get("snippet"),
            "score": item.get("score"),
        })
    return {"results": results, "provider": "tavily", "query": query}

@function_tool
def list_local_tools() -> list:
    """List available local tools"""
    return [
        {
            'name': 'web_search_impl',
            'description': 'Search the web using Tavily API',
            'parameters': {
                'query': 'Search query string',
                'top_k': 'Number of results to return (max 10)',
                'recency_days': 'Filter results by recency in days'
            }
        }
    ]

def _get_memory_tools():
    """Get memory tools using the initialized memory_id"""
    if memory_id:
        return create_memory_tools(
            memory_id,
            client,
            actor_id=config_data['agent_information']['ops_orchestrator_agent_model_info'].get('memory_allocation', {}).get('actor_id', 'default_actor'),
            session_id='default_session'
        )
    return []
    
async def create_lead_orchestrator_agent(memory_tools: list):
    """Create lead orchestrator agent with local tools only"""

    # Disable OpenAI tracing to prevent span_data.result errors
    os.environ["OPENAI_ENABLE_TRACING"] = "false"

    # Use the memory tools passed as parameter, or get them if not provided
    if not memory_tools:
        memory_tools = _get_memory_tools()
    print(f"Going to add memory tools: {memory_tools}")

    # Add only local tools - no gateway dependencies
    agent_tools = [web_search_impl, *memory_tools]

    print(f"✅ Local tools initialized: web search and {len(memory_tools)} memory tools")

    # Create the orchestrator agent with local tools only
    orchestrator = Agent(
        name="Ops_Orchestrator",
        instructions=OPS_ORCHESTRATOR_AGENT_SYSTEM_PROMPT,  # Use your existing prompt
        model=config_data['agent_information']['ops_orchestrator_agent_model_info'].get('model_id'),
        tools=agent_tools
    )
    print(f"✅ Orchestrator Agent created with local tools: {len(agent_tools)} total tools")
    return orchestrator

# ────────────────────────────────────────────────────────────────────────────────────
# ENTRYPOINT FUNCTION FOR BEDROCK AGENTCORE INVOCATION
# ────────────────────────────────────────────────────────────────────────────────────

# Import only what's needed for the AgentCore app entrypoint
print(f"Going to start the app.entrypoint from where this invocations will process...")
from bedrock_agentcore.runtime import BedrockAgentCoreApp

async def get_lead_orchestrator():
    """
    Build and return the lead orchestrator Agent.
    You already define create_lead_orchestrator_agent(memory_tools: list) above.
    """
    # If you want to pass explicit memory tools, replace [] with your list.
    return await create_lead_orchestrator_agent([])

async def _call_agent(agent, prompt: str):
    """
    Call agent using the proper OpenAI Agents SDK Runner with detailed logging.
    """
    try:
        print(f"📝 Calling agent with prompt: {prompt[:100]}...")
        print(f"🤖 Agent type: {type(agent)}")
        print(f"🤖 Agent name: {agent.name if hasattr(agent, 'name') else 'unknown'}")
        
        # Use the proper OpenAI Agents SDK Runner
        runner = Runner()
        print("🏃 Created Runner instance")
        
        result = await runner.run(agent, prompt)
        print(f"✅ Agent execution completed")
        print(f"📤 Result type: {type(result)}")
        print(f"📤 Result attributes: {dir(result)}")
        
        # Try to get the output in different ways
        output = None
        if hasattr(result, 'final_output'):
            output = result.final_output
            print(f"📤 Got final_output: {output[:200] if output else 'None'}...")
        elif hasattr(result, 'output'):
            output = result.output
            print(f"📤 Got output: {output[:200] if output else 'None'}...")
        elif hasattr(result, 'text'):
            output = result.text
            print(f"📤 Got text: {output[:200] if output else 'None'}...")
        else:
            output = str(result)
            print(f"📤 Converted result to string: {output[:200]}...")
        
        return {"output": output}
    except Exception as e:
        logger.error(f"❌ Error running agent: {str(e)}", exc_info=True)
        import traceback
        traceback.print_exc()
        return {"output": f"Error running agent: {str(e)}"}

# ──────────────────────────────────────────────────────────────────────────────
# A2A AGENT EXECUTOR
# ──────────────────────────────────────────────────────────────────────────────

class OpsRemediationAgentExecutor(AgentExecutor):
    """
    Agent executor that wraps the OpenAI-based ops remediation agent
    for A2A server compatibility
    """

    def __init__(self):
        """Initialize the executor"""
        self._agent = None
        self._active_tasks = {}
        logger.info("OpsRemediationAgentExecutor initialized")

    async def _get_agent(self):
        """Lazily initialize and return the agent"""
        if self._agent is None:
            logger.info("Creating lead orchestrator agent...")
            self._agent = await get_lead_orchestrator()
            logger.info("Lead orchestrator agent created successfully")
        return self._agent

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Execute the agent's logic for a given request context.
        """
        try:
            task_id = context.task_id
            logger.info(f"Executing task {task_id}")

            # Extract the user message from context
            user_message = ""

            if context.message and context.message.parts:
                for part in context.message.parts:
                    # A2A protocol wraps TextPart in a Part container with 'root' attribute
                    if hasattr(part, 'root') and hasattr(part.root, 'text'):
                        user_message += part.root.text
                    # Fallback: direct text attribute
                    elif hasattr(part, 'text'):
                        user_message += part.text
                    # Fallback: dict access
                    elif isinstance(part, dict) and 'text' in part:
                        user_message += part['text']

            logger.info(f"📝 User message extracted: '{user_message}'")

            # Get the agent instance
            agent = await self._get_agent()

            # Mark task as active
            self._active_tasks[task_id] = True

            # Call the agent
            logger.info("Calling agent with user message...")
            result = await _call_agent(agent, user_message)

            # Check if task was cancelled
            if not self._active_tasks.get(task_id, False):
                logger.info(f"Task {task_id} was cancelled")
                return

            # Publish completion event
            from a2a.types import TaskStatusUpdateEvent, TaskState, TaskStatus, Message, TextPart, Role
            import uuid

            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    context_id=context.context_id,
                    task_id=task_id,
                    final=True,
                    status=TaskStatus(
                        state=TaskState.completed,
                        message=Message(
                            messageId=str(uuid.uuid4()),
                            role=Role.user,  # Use Role.user
                            parts=[TextPart(text=result.get("output", ""))]
                        ),
                        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
                    )
                )
            )

            logger.info(f"Task {task_id} completed successfully")

        except Exception as e:
            logger.error(f"Error executing task {task_id}: {e}", exc_info=True)

            # Publish failure event
            from a2a.types import TaskStatusUpdateEvent, TaskState, TaskStatus, Message, TextPart, Role
            import uuid

            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    context_id=context.context_id,
                    task_id=task_id,
                    final=True,
                    status=TaskStatus(
                        state=TaskState.failed,
                        message=Message(
                            messageId=str(uuid.uuid4()),
                            role=Role.user,  # Use Role.user
                            parts=[TextPart(text=str(e))]
                        ),
                        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
                    )
                )
            )
        finally:
            # Clean up task from active tasks
            self._active_tasks.pop(task_id, None)

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Request the agent to cancel an ongoing task.
        """
        try:
            task_id = context.task_id
            logger.info(f"Cancelling task {task_id}")

            # Mark task as cancelled
            self._active_tasks[task_id] = False

            # Publish cancellation event
            from a2a.types import TaskStatusUpdateEvent, TaskState, TaskStatus, Message, TextPart, Role
            import uuid

            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    context_id=context.context_id,
                    task_id=task_id,
                    final=True,
                    status=TaskStatus(
                        state=TaskState.canceled,
                        message=Message(
                            messageId=str(uuid.uuid4()),
                            role=Role.user,  # Use Role.user
                            parts=[TextPart(text="Task cancelled by user")]
                        ),
                        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
                    )
                )
            )

            logger.info(f"Task {task_id} cancelled successfully")

        except Exception as e:
            logger.error(f"Error cancelling task {task_id}: {e}", exc_info=True)
    
# ──────────────────────────────────────────────────────────────────────────────
# INTERACTIVE MODE & SINGLE-COMMAND MODE
# (Use the same lead orchestrator in both)
# ──────────────────────────────────────────────────────────────────────────────

import asyncio
import argparse
import sys
from typing import Optional

def _parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Ops Orchestrator Agent")
    parser.add_argument('-i', '--interactive', action='store_true', help='Run in interactive mode')
    parser.add_argument('-c', '--command', type=str, help='Execute a single command and exit')
    parser.add_argument('--server', action='store_true', help='Run as AgentCore server (default)')
    parser.add_argument('--a2a', action='store_true', help='Run as A2A server on port 9000')
    parser.add_argument('--port', type=int, default=9000, help='Port for A2A server (default: 9000)')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='Host for A2A server (default: 127.0.0.1)')
    return parser.parse_args()

def run_a2a_server(host: str = '127.0.0.1', port: int = 9000):
    """
    Run the ops remediation agent as an A2A server

    Args:
        host: Host to bind the server to
        port: Port to bind the server to
    """
    print(f"🚀 Starting Ops Remediation Agent A2A Server on {host}:{port}")

    # Create agent card
    agent_card = AgentCard(
        name="Ops Remediation Agent",
        description="Operations remediation agent that provides documentation and solutions for JIRA tickets by searching AWS documentation",
        url=f"http://{host}:{port}",
        version="1.0.0",
        defaultInputModes=["text/plain"],
        defaultOutputModes=["text/plain"],
        capabilities=AgentCapabilities(
            streaming=False,
            pushNotifications=False
        ),
        skills=[
            AgentSkill(
                id="ops-remediation",
                name="Operations Remediation",
                description="Search AWS documentation and provide remediation strategies for operational issues",
                tags=["operations", "remediation", "aws", "documentation"],
                examples=[
                    "Find documentation for fixing high CPU usage in EC2",
                    "Search for solutions to RDS connection timeout issues",
                    "Get remediation steps for Lambda function errors"
                ]
            ),
            AgentSkill(
                id="jira-documentation",
                name="JIRA Documentation",
                description="Provide documentation and updates for JIRA tickets",
                tags=["jira", "documentation", "ticketing"],
                examples=[
                    "Document the fix for JIRA ticket OPS-123",
                    "Provide status update for incident ticket"
                ]
            )
        ]
    )

    # Create request handler with executor
    request_handler = DefaultRequestHandler(
        agent_executor=OpsRemediationAgentExecutor(),
        task_store=InMemoryTaskStore()
    )

    # Create A2A server
    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler
    )

    # Build the app and add health endpoint
    app = server.build()

    @app.route("/health", methods=["GET"])
    async def health_check(request):
        """Health check endpoint"""
        return JSONResponse({
            "status": "healthy",
            "agent": "ops_remediation_agent",
            "version": "1.0.0"
        })

    @app.route("/ping", methods=["GET"])
    async def ping(request):
        """Ping endpoint"""
        return JSONResponse({"message": "pong"})

    print(f"✅ A2A Server configured")
    print(f"📍 Server URL: http://{host}:{port}")
    print(f"🏥 Health check: http://{host}:{port}/health")
    print(f"🏓 Ping: http://{host}:{port}/ping")

    # Run the server
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    args = _parse_arguments()
    run_a2a_server(host=args.host, port=args.port)