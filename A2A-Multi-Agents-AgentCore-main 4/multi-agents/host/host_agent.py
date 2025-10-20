"""
Host orchestrator agent for A2A multi-agent communication.

Simplified version that:
1. Fetches IDP config from SSM Parameter Store
2. Discovers and communicates with remote agents via A2A
3. Uses Google ADK for orchestration
"""

import asyncio
import json
import logging
import urllib.parse
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterable, Dict, List, Optional

import boto3
import httpx
import nest_asyncio
import yaml
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import (
    AgentCard,
    MessageSendParams,
    SendMessageRequest,
    SendMessageResponse,
    SendMessageSuccessResponse,
    Task,
)
from dotenv import load_dotenv
from google.adk import Agent
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.tool_context import ToolContext
from google.genai import types


load_dotenv()
nest_asyncio.apply()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)
logger = logging.getLogger(__name__)


def _load_config() -> dict:
    """Load configuration from config.yaml file."""
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        logger.info("Loaded host agent configuration")
        return config


def _fetch_ssm_parameter(
    parameter_path: str,
    region: str,
) -> dict:
    """
    Fetch IDP configuration from SSM Parameter Store.

    Args:
        parameter_path: SSM parameter path (e.g., /a2a/agents/monitoring/idp-config)
        region: AWS region

    Returns:
        Dictionary containing IDP configuration
    """
    logger.info(f"Fetching SSM parameter: {parameter_path}")

    ssm = boto3.client("ssm", region_name=region)
    response = ssm.get_parameter(Name=parameter_path, WithDecryption=True)

    config_str = response["Parameter"]["Value"]
    config = json.loads(config_str)

    logger.info(f"Successfully fetched IDP config from SSM: {config}")
    return config


def _extract_runtime_url(
    runtime_arn: str,
    region: str,
) -> str:
    """
    Extract runtime URL from ARN.

    Args:
        runtime_arn: Runtime ARN
        region: AWS region

    Returns:
        Runtime URL for A2A communication
    """
    # ARN format: arn:aws:bedrock-agentcore:region:account:runtime/agent-id
    endpoint = f"https://bedrock-agentcore.{region}.amazonaws.com"
    escaped = urllib.parse.quote(runtime_arn, safe="")
    # Construct the agent runtime URL
    return f"{endpoint}/runtimes/{escaped}/invocations"


async def _get_bearer_token(
    idp_config: dict,
) -> str:
    """
    Get OAuth bearer token using client credentials flow.

    Args:
        idp_config: IDP configuration dictionary

    Returns:
        Bearer token string
    """
    logger.info("Fetching bearer token from Cognito")

    # Use the domain field to construct the token endpoint
    domain = idp_config["domain"]
    region = idp_config["user_pool_id"].split("_")[0]  # Extract region from user_pool_id
    token_endpoint = f"https://{domain}.auth.{region}.amazoncognito.com/oauth2/token"
    # Build scope string
    scopes = idp_config.get("scopes", [])
    resource_server = idp_config["resource_server_identifier"]
    scope_str = " ".join([f"{resource_server}/{scope}" for scope in scopes])
    # OAuth client credentials request
    token_data = {
        "grant_type": "client_credentials",
        "client_id": idp_config["client_id"],
        "client_secret": idp_config["client_secret"],
        "scope": scope_str,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            token_endpoint,
            data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        token_response = response.json()
        access_token = token_response["access_token"]
        logger.info("Successfully obtained bearer token")
        return access_token


class RemoteAgent:
    """Represents a remote agent with A2A communication capabilities."""
    def __init__(
        self,
        name: str,
        description: str,
        runtime_url: str,
        bearer_token: str,
    ):
        """
        Initialize remote agent.

        Args:
            name: Agent name
            description: Agent description
            runtime_url: Runtime URL for A2A communication
            bearer_token: OAuth bearer token
        """
        self.name = name
        self.description = description
        self.runtime_url = runtime_url
        self.bearer_token = bearer_token

        # HTTP client with auth headers
        # Increased timeout to 300s (5 minutes) for long-running operations like CloudWatch queries
        self.httpx_client = httpx.AsyncClient(
            timeout=300.0,
            headers={
                "Authorization": f"Bearer {bearer_token}",
                "Content-Type": "application/json",
            },
        )
        # Agent card and A2A client (initialized during discovery)
        self.agent_card: Optional[AgentCard] = None
        self.a2a_client: Optional[A2AClient] = None

    async def discover(self):
        """Discover agent capabilities by fetching agent card."""
        logger.info(f"Discovering agent card for {self.name} at {self.runtime_url}")
        card_resolver = A2ACardResolver(self.httpx_client, self.runtime_url)
        self.agent_card = await card_resolver.get_agent_card()
        logger.info(f"Successfully discovered {self.name}")
        # Initialize A2A client
        self.a2a_client = A2AClient(
            self.httpx_client,
            self.agent_card,
            url=self.runtime_url,
        )

    async def send_message(
        self,
        message_request: SendMessageRequest,
    ) -> SendMessageResponse:
        """
        Send a message to the agent using A2A protocol.

        Args:
            message_request: A2A message request

        Returns:
            A2A message response
        """
        if not self.a2a_client:
            raise RuntimeError(f"A2A client not initialized for {self.name}")

        logger.info(f"Sending message to {self.name}")
        response = await self.a2a_client.send_message(message_request)
        logger.info(f"Received response from {self.name}")
        return response

    async def close(self):
        """Close HTTP client and cleanup resources."""
        await self.httpx_client.aclose()
        logger.info(f"Closed client for {self.name}")


class HostAgent:
    """
    Host orchestrator agent that manages A2A communication with remote agents.

    This agent discovers remote agents, fetches their capabilities,
    and routes user requests to appropriate specialist agents.
    """

    def __init__(self):
        """Initialize the host agent."""
        self.config = _load_config()
        self.remote_agents: Dict[str, RemoteAgent] = {}
        self.agents_info: str = ""

        # Create orchestrator agent
        self._agent = self._create_agent()

        # Runner for the orchestrator agent
        self._runner = Runner(
            app_name=self._agent.name,
            agent=self._agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )

        self._user_id = "a2a_host_orchestrator_user"
        logger.info("Host agent initialized")

    async def _discover_remote_agents(self):
        """
        Discover remote agents by:
        1. Fetching IDP config from SSM
        2. Getting bearer tokens
        3. Discovering agent cards
        """
        logger.info("Starting remote agent discovery")

        agents_config = self.config.get("agents")
        logger.info(f"Going to create a remote connection with {len(agents_config)} agents...")
        for agent_config in agents_config:
            agent_name = agent_config["name"]
            runtime_arn = agent_config["runtime_arn"]
            region = agent_config["region"]
            ssm_path = agent_config["ssm_idp_config_path"]
            logger.info(f"Discovering agent: {agent_name}")

            try:
                # Fetch IDP config from SSM
                idp_config = _fetch_ssm_parameter(ssm_path, region)
                # Get bearer token
                bearer_token = await _get_bearer_token(idp_config)
                # Extract runtime URL
                runtime_url = _extract_runtime_url(runtime_arn, region)
                logger.info(f"Runtime URL for agent {agent_name}: {runtime_url}")
                # Create remote agent
                remote_agent = RemoteAgent(
                    name=agent_name,
                    description=agent_config["description"],
                    runtime_url=runtime_url,
                    bearer_token=bearer_token,
                )
                # Discover agent card
                await remote_agent.discover()
                # Store agent
                self.remote_agents[agent_name] = remote_agent
                logger.info(f"Successfully discovered {agent_name}")
            except Exception as e:
                logger.error(f"Failed to discover {agent_name}: {e}")

        # Build agent information for system prompt
        if self.remote_agents:
            self.agents_info = "\n".join(
                json.dumps({"name": agent.name, "description": agent.description})
                for agent in self.remote_agents.values()
            )
            logger.info(f"Discovered {len(self.remote_agents)} agents")
        else:
            self.agents_info = "No agents available"
            logger.warning("No agents were discovered")

    @classmethod
    async def create(cls):
        """
        Create and initialize a HostAgent instance.

        Returns:
            Initialized HostAgent instance
        """
        instance = cls()
        await instance._discover_remote_agents()
        return instance

    def _create_agent(self) -> Agent:
        """Create the Google ADK orchestrator agent."""
        model_config = self.config["model"]

        return Agent(
            model=model_config.get("id"),
            name=model_config.get("name"),
            instruction=self._get_system_instruction,
            description="Orchestrator agent that routes requests to specialized agents",
            tools=[self.send_message_to_agent],
        )

    def _get_system_instruction(self, context) -> str:
        """Generate system instruction for the orchestrator agent."""
        return f"""
Role: You are the Lead Orchestrator, an expert triage and coordination agent for incident response and operations management. Your primary function is to route user requests to the right specialist agent, track progress, and report back clearly.

Specialist Agents Available:

{self.agents_info}

Core Directives:

1. Initiate Triage: When asked for help, first clarify the objective and relevant scope (AWS account/region/service, time window, urgency).

2. Task Delegation: Use the send_message_to_agent tool to contact the appropriate agent(s).
   - Be explicit: e.g., "Please scan CloudWatch logs and metrics for service X between 2024-08-01 and 2024-08-03."
   - Always pass the official agent name (Monitoring_Agent, OpsRemediation_Agent) when sending messages.

3. Analyze Responses: Correlate findings from all contacted agents. Summarize root causes, evidence (metrics/logs), and proposed actions.

4. Jira Workflow: If Monitoring_Agent reports an issue, ensure a Jira ticket is (or gets) created, capture the ticket ID, status, and assignee, and keep it updated as remediation proceeds.

5. Propose and Confirm: Present recommended actions (and any risk/impact) to the user for confirmation. If the user has pre-approved runbooks, proceed accordingly.

6. Execute Remediation: After confirmation, instruct OpsRemediation_Agent to perform the fix. Track outcomes and validation steps (post-fix metrics, log baselines).

7. Transparent Communication: Relay progress and final results, including Jira IDs/links and any residual follow-ups. Do not ask for permission before contacting specialist agents.

8. Tool Reliance: Strictly rely on available tools to fulfill requests. Do not invent results or act without agent/tool confirmation.

9. Readability: Respond concisely, preferably with bullet points and short sections.

10. Agent Selection: Choose the appropriate agent based on the task:
    - Monitoring_Agent: For AWS metrics, logs, CloudWatch alarms, Jira ticket creation
    - OpsRemediation_Agent: For searching remediation strategies, AWS documentation, troubleshooting guidance

Today's Date (YYYY-MM-DD): {datetime.now().strftime("%Y-%m-%d")}
"""

    async def send_message_to_agent(
        self,
        agent_name: str,
        task: str,
        tool_context: ToolContext,
    ) -> List[Dict[str, Any]]:
        """
        Send a message to a remote agent via A2A protocol.

        Args:
            agent_name: Name of the target agent
            task: Task description or question for the agent
            tool_context: Context from Google ADK

        Returns:
            List of response parts from the agent
        """
        logger.info(f"Sending message to {agent_name}: {task}")

        # Validate agent exists
        if agent_name not in self.remote_agents:
            error_msg = f"Agent {agent_name} not found. Available agents: {list(self.remote_agents.keys())}"
            logger.error(error_msg)
            return [{"type": "text", "text": error_msg}]

        remote_agent = self.remote_agents[agent_name]

        # Get or create task/context IDs from state
        state = tool_context.state
        task_id = state.get("task_id")
        context_id = state.get("context_id", str(uuid.uuid4()))
        message_id = str(uuid.uuid4())

        # Build A2A message payload
        payload = {
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": task}],
                "messageId": message_id,
                "contextId": context_id,
            },
        }

        # Add taskId if continuing existing task
        if task_id:
            payload["message"]["taskId"] = task_id

        # Create A2A message request
        message_request = SendMessageRequest(
            id=message_id,
            params=MessageSendParams.model_validate(payload),
        )

        try:
            # Send message to agent
            response: SendMessageResponse = await remote_agent.send_message(
                message_request
            )

            logger.debug(f"Received response from {agent_name}: {response}")
            # Parse response
            if not isinstance(
                response.root, SendMessageSuccessResponse
            ) or not isinstance(response.root.result, Task):
                error_msg = "Received non-success or non-task response from agent"
                logger.error(error_msg)
                return [{"type": "text", "text": error_msg}]

            # Extract response content
            response_json = json.loads(
                response.root.model_dump_json(exclude_none=True)
            )

            # Log full response for debugging
            logger.info(f"Full response from {agent_name}:\n{json.dumps(response_json, indent=2, default=str)}")

            result_parts = []

            # Check for response in artifacts
            if response_json.get("result", {}).get("artifacts"):
                for artifact in response_json["result"]["artifacts"]:
                    if artifact.get("parts"):
                        result_parts.extend(artifact["parts"])

            # Check for response in status.message.parts (alternative response format)
            if not result_parts:
                status_message = response_json.get("result", {}).get("status", {}).get("message", {})
                if status_message.get("parts"):
                    result_parts.extend(status_message["parts"])

            logger.info(f"Extracted {len(result_parts)} response parts from {agent_name}")
            logger.debug(f"Response parts: {result_parts}")

            if not result_parts:
                logger.warning(f"Agent {agent_name} returned response with no parts. Response structure: {list(response_json.keys())}")

            return result_parts if result_parts else [
                {"type": "text", "text": f"Agent returned empty response. Response keys: {list(response_json.keys())}"}
            ]

        except Exception as e:
            error_msg = f"Failed to send message to {agent_name}: {str(e)}"
            logger.error(error_msg)
            return [{"type": "text", "text": error_msg}]

    async def stream(
        self,
        query: str,
        session_id: str,
    ) -> AsyncIterable[Dict[str, Any]]:
        """
        Stream the agent's response to a query.

        Args:
            query: User query
            session_id: Session ID for conversation continuity

        Yields:
            Response events with task completion status and content
        """
        logger.info(f"Processing query: {query}")

        # Get or create session
        session = await self._runner.session_service.get_session(
            app_name=self._agent.name,
            user_id=self._user_id,
            session_id=session_id,
        )

        content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=query)],
        )

        if session is None:
            session = await self._runner.session_service.create_session(
                app_name=self._agent.name,
                user_id=self._user_id,
                state={},
                session_id=session_id,
            )

        # Stream agent execution
        async for event in self._runner.run_async(
            user_id=self._user_id,
            session_id=session.id,
            new_message=content,
        ):
            if event.is_final_response():
                # Extract final response text
                response = ""
                if event.content and event.content.parts:
                    response_parts = []
                    for part in event.content.parts:
                        if part.text:
                            response_parts.append(part.text)
                        elif hasattr(part, "function_call") and part.function_call:
                            response_parts.append(
                                f"[Function call: {part.function_call}]"
                            )
                    response = "\n".join(response_parts)

                yield {
                    "is_task_complete": True,
                    "content": response,
                }
            else:
                yield {
                    "is_task_complete": False,
                    "updates": "The orchestrator is thinking...",
                }

    async def close(self):
        """Close all remote agents and cleanup resources."""
        logger.info("Closing host agent")
        for agent_name, agent in self.remote_agents.items():
            try:
                await agent.close()
                logger.info(f"Closed {agent_name}")
            except Exception as e:
                logger.error(f"Error closing {agent_name}: {e}")


def _get_initialized_host_agent_sync() -> Agent:
    """
    Synchronously creates and initializes the HostAgent.

    This function is used for ADK web interface compatibility.

    Returns:
        Initialized Google ADK Agent
    """

    async def _async_main():
        logger.info("Initializing host agent")
        host_agent_instance = await HostAgent.create()
        logger.info("Host agent initialized successfully")
        return host_agent_instance._agent

    try:
        return asyncio.run(_async_main())
    except RuntimeError as e:
        if "asyncio.run() cannot be called from a running event loop" in str(e):
            logger.warning(
                f"Could not initialize HostAgent with asyncio.run(): {e}. "
                "Event loop already running (e.g., in Jupyter). "
                "Initialize HostAgent within an async function."
            )
        else:
            raise


# Export for ADK web interface
root_agent = _get_initialized_host_agent_sync()
