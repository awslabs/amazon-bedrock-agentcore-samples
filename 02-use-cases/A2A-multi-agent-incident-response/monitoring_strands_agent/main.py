from bedrock_agentcore.memory import MemoryClient
from context import MonitoringAgentContext
from contextlib import asynccontextmanager
from datetime import timedelta
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mcp.client.streamable_http import streamablehttp_client
from memory_hook import MonitoringMemoryHooks
from prompt import SYSTEM_PROMPT
from strands import Agent
from strands.models import BedrockModel
from strands.multiagent.a2a import A2AServer
from strands.tools.mcp.mcp_client import MCPClient
import asyncio
import boto3
import logging
import os
import uvicorn

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

ssm = boto3.client("ssm")
agentcore_client = boto3.client("bedrock-agentcore")

# Configuration with validation
MODEL_ID = os.getenv("MODEL_ID", "global.anthropic.claude-sonnet-4-20250514-v1:0")

MEMORY_ID = os.getenv("MEMORY_ID")
if not MEMORY_ID:
    raise RuntimeError("Missing MEMORY_ID environment variable")

GATEWAY_PROVIDER_NAME = os.getenv("GATEWAY_PROVIDER_NAME")
if not GATEWAY_PROVIDER_NAME:
    raise RuntimeError("Missing GATEWAY_PROVIDER_NAME environment variable")

AWS_REGION = os.getenv("MCP_REGION")
if not AWS_REGION:
    raise RuntimeError("Missing MCP_REGION environment variable")

# Use the complete runtime URL from environment variable, fallback to local
runtime_url = os.environ.get("AGENTCORE_RUNTIME_URL", "http://127.0.0.1:9000/")
host, port = "0.0.0.0", 9000

logger.info(f"Configuration loaded - Runtime URL: {runtime_url}, Region: {AWS_REGION}")

# Initialization lock to prevent race conditions
initialization_lock = asyncio.Lock()


def get_ssm_parameter(name: str, with_decryption: bool = True) -> str:
    """Fetch parameter from SSM."""
    try:
        response = ssm.get_parameter(Name=name, WithDecryption=with_decryption)
        return response["Parameter"]["Value"]
    except Exception as e:
        logger.error(f"Failed to fetch SSM parameter '{name}': {e}")
        raise RuntimeError(f"Failed to fetch SSM parameter '{name}': {e}") from e


def get_gateway_url() -> str:
    """Lazy load gateway URL from SSM."""
    url = MonitoringAgentContext.get_gateway_url()
    if url is None:
        url = get_ssm_parameter("/monitoragent/agentcore/gateway/gateway_url")
        MonitoringAgentContext.set_gateway_url(url)
        logger.info("Gateway URL loaded from SSM")
    return url


def create_gateway_client() -> MCPClient:
    """Create and return a gateway MCP client with OAuth2 authentication."""
    agent_identity_token = MonitoringAgentContext.get_agent_identity_token()

    if not agent_identity_token:
        raise RuntimeError("Agent identity token not available")

    response = agentcore_client.get_resource_oauth2_token(
        workloadIdentityToken=agent_identity_token,
        resourceCredentialProviderName=GATEWAY_PROVIDER_NAME,
        scopes=[],
        oauth2Flow="M2M",
        forceAuthentication=False,
    )

    gateway_access_token = response["accessToken"]
    url = get_gateway_url()

    logger.info("Gateway access token obtained successfully")
    return MCPClient(
        lambda: streamablehttp_client(
            url=url,
            headers={"Authorization": f"Bearer {gateway_access_token}"},
            timeout=timedelta(seconds=120),
        )
    )


client = MemoryClient(region_name=AWS_REGION)

bedrock_model = BedrockModel(
    model_id=MODEL_ID,
    region_name=AWS_REGION,
)


# Lifespan context manager for shutdown cleanup
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

    # Shutdown: Stop gateway client if it was initialized
    logger.info("Shutting down...")
    gateway_client = MonitoringAgentContext.get_gateway_client()
    if gateway_client:
        logger.info("Stopping gateway client...")
        gateway_client.stop()
        logger.info("Gateway client stopped successfully")


app = FastAPI(title="Monitoring Agent A2A Server", lifespan=lifespan)


# Middleware to capture session ID and initialize agent
@app.middleware("http")
async def capture_session_id(request: Request, call_next):
    # Capture workload identity token if present
    if request.headers.get("x-amzn-bedrock-agentcore-runtime-workload-accesstoken"):
        token = request.headers.get(
            "x-amzn-bedrock-agentcore-runtime-workload-accesstoken"
        )
        MonitoringAgentContext.set_agent_identity_token(token)
        logger.debug("Agent identity token captured from request headers")

    session_id = request.headers.get("x-amzn-bedrock-agentcore-runtime-session-id")

    # Initialize agent components if we have a session ID and haven't initialized yet
    current_session_id = MonitoringAgentContext.get_session_id()
    # actor_id = request_headers["x-amzn-bedrock-agentCore-runtime-custom-actor"]

    # if not actor_id:
    #     raise Exception("Actor id is not is not set")
    actor_id = "Actor1"  # TODO: Extract actor_id from headers or context
    if session_id and not current_session_id:
        async with initialization_lock:
            # Double-check after acquiring lock
            if MonitoringAgentContext.get_session_id():
                response = await call_next(request)
                return response

            MonitoringAgentContext.set_session_id(session_id)
            logger.info(
                f"Initializing agent components for session: {session_id[:8]}..."
            )

            # Initialize monitoring hooks with the captured session ID
            monitoring_hooks = MonitoringMemoryHooks(
                memory_id=MEMORY_ID,
                client=client,
                actor_id=actor_id,
                session_id=session_id,
            )
            MonitoringAgentContext.set_monitoring_hooks(monitoring_hooks)
            logger.info("Monitoring hooks initialized")

            # Initialize and start gateway client (needs request context for access token)
            logger.info("Initializing gateway client...")
            gateway_client = create_gateway_client()
            gateway_client.start()
            MonitoringAgentContext.set_gateway_client(gateway_client)
            logger.info("Gateway client started successfully")

            # Get gateway tools from MCP client
            gateway_tools = gateway_client.list_tools_sync()
            logger.info(f"Loaded {len(gateway_tools)} tools from gateway client")

            # Create strands agent with hooks and gateway tools
            strands_agent = Agent(
                name="Monitoring Agent",
                description="A monitoring agent that handles CloudWatch logs, metrics, dashboards, and AWS service monitoring",
                system_prompt=SYSTEM_PROMPT,
                model=bedrock_model,
                tools=gateway_tools,
                hooks=[monitoring_hooks],
            )
            MonitoringAgentContext.set_agent(strands_agent)
            logger.info(
                f"Strands Agent created with {len(gateway_tools)} tools and monitoring hooks"
            )

            # Create A2A server with the initialized agent
            a2a_server = A2AServer(
                agent=strands_agent,
                http_url=runtime_url,
                serve_at_root=True,
                host=host,
                port=port,
                version="1.0.0",
            )
            MonitoringAgentContext.set_a2a_server(a2a_server)
            logger.info("A2A Server created successfully")

    response = await call_next(request)
    return response


@app.get("/ping")
def ping():
    """Health check endpoint with agent status."""

    return {
        "status": "healthy",
    }


# Conditional mount - only mount if a2a_server is initialized
@app.middleware("http")
async def mount_a2a_conditionally(request: Request, call_next):
    a2a_server = MonitoringAgentContext.get_a2a_server()

    # If a2a_server exists and hasn't been mounted yet, log readiness
    if a2a_server is not None and not hasattr(app, "_a2a_mounted"):
        # Mark as mounted to avoid re-logging
        app._a2a_mounted = True
        logger.info("A2A server ready to handle requests")

    response = await call_next(request)
    return response


# Handle routing - check if a2a_server exists before forwarding
@app.api_route(
    "/{full_path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
)
async def proxy_to_a2a(request: Request):
    """Proxy requests to the A2A server once initialized."""
    a2a_server = MonitoringAgentContext.get_a2a_server()

    if a2a_server is None:
        return JSONResponse(
            status_code=503,
            content={
                "error": "Agent not initialized",
                "message": "Waiting for session ID to initialize agent",
            },
        )

    # Forward request to a2a_server
    a2a_app = a2a_server.to_fastapi_app()
    return await a2a_app(request.scope, request.receive, request._send)


if __name__ == "__main__":
    uvicorn.run(app, host=host, port=port)
