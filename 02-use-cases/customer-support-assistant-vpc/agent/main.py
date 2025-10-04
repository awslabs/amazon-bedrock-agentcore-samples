from bedrock_agentcore.identity.auth import requires_access_token
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.runtime.context import BedrockAgentCoreContext
from context import CustomerSupportContext
from contextlib import asynccontextmanager
from mcp import stdio_client, StdioServerParameters
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from typing import Optional
from utils import get_ssm_parameter
import logging
import os
import traceback
import urllib.parse

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def get_required_env(name: str) -> str:
    """Get required environment variable or raise error."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} environment variable is required")
    return value


# Environment variables - validated but not initialized
MODEL_ID = os.getenv("MODEL_ID", "us.anthropic.claude-3-5-haiku-20241022-v1:0")
MCP_REGION = get_required_env("MCP_REGION")
MCP_ARN = get_required_env("MCP_ARN")
GATEWAY_PROVIDER_NAME = get_required_env("GATEWAY_PROVIDER_NAME")
MCP_PROVIDER_NAME = get_required_env("MCP_PROVIDER_NAME")

# Aurora PostgreSQL environment variables
AURORA_CLUSTER_ARN = get_required_env("AURORA_CLUSTER_ARN")
AURORA_SECRET_ARN = get_required_env("AURORA_SECRET_ARN")
AURORA_DATABASE = get_required_env("AURORA_DATABASE")
AWS_REGION = os.getenv("AWS_REGION", MCP_REGION)

# Lazy-loaded configuration
_gateway_url: Optional[str] = None
_mcp_url: Optional[str] = None


def get_gateway_url() -> str:
    """Lazily load gateway URL from SSM."""
    global _gateway_url
    if _gateway_url is None:
        try:
            _gateway_url = get_ssm_parameter(
                "/app/customersupportvpc/gateway/gateway_url"
            )
            logger.info("Gateway URL loaded from SSM")
        except Exception as e:
            logger.error(f"Failed to load gateway URL from SSM: {e}")
            raise
    return _gateway_url


def get_mcp_url() -> str:
    """Lazily construct MCP URL."""
    global _mcp_url
    if _mcp_url is None:
        escaped_arn = urllib.parse.quote(MCP_ARN, safe="")
        _mcp_url = f"https://bedrock-agentcore.{MCP_REGION}.amazonaws.com/runtimes/{escaped_arn}/invocations?qualifier=DEFAULT"
        logger.info("MCP URL constructed")
    return _mcp_url


@requires_access_token(
    provider_name=GATEWAY_PROVIDER_NAME,
    scopes=[],
    auth_flow="M2M",
)
async def get_gateway_access_token(access_token: str) -> str:
    """Get OAuth2 access token for gateway."""
    return access_token


@requires_access_token(
    provider_name=MCP_PROVIDER_NAME,
    scopes=[],
    auth_flow="M2M",
)
async def get_mcp_access_token(access_token: str) -> str:
    """Get OAuth2 access token for MCP."""
    return access_token


async def initialize_clients():
    """Initialize MCP clients and agent. Called by middleware on first request."""
    agent = CustomerSupportContext.get_agent_ctx()

    # Check if agent already initialized
    if agent is not None:
        logger.info("Agent already initialized, skipping setup")
        return

    # Get or fetch access tokens
    # gateway_access_token = CustomerSupportContext.get_gateway_token_ctx()
    # if not gateway_access_token:
    #     logger.info("Fetching gateway access token")
    #     gateway_access_token = await get_gateway_access_token()
    #     CustomerSupportContext.set_gateway_token_ctx(gateway_access_token)

    # mcp_access_token = CustomerSupportContext.get_mcp_token_ctx()
    # if not mcp_access_token:
    #     logger.info("Fetching MCP access token")
    #     mcp_access_token = await get_mcp_access_token()
    #     CustomerSupportContext.set_mcp_token_ctx(mcp_access_token)

    # # Validate tokens
    # if not gateway_access_token:
    #     raise RuntimeError("Failed to obtain gateway access token")
    # if not mcp_access_token:
    #     raise RuntimeError("Failed to obtain MCP access token")

    # # Initialize MCP clients
    # logger.info("Initializing MCP clients")
    # mcp_url = get_mcp_url()
    # gateway_url = get_gateway_url()

    # mcp_client = MCPClient(
    #     lambda: streamablehttp_client(
    #         url=mcp_url,
    #         headers={"Authorization": f"Bearer {mcp_access_token}"},
    #     )
    # )

    # gateway_client = MCPClient(
    #     lambda: streamablehttp_client(
    #         url=gateway_url,
    #         headers={"Authorization": f"Bearer {gateway_access_token}"},
    #     )
    # )

    # # Start clients and list tools
    # logger.info("Starting MCP clients")
    # gateway_client.start()
    # mcp_client.start()

    # # Store clients in context
    # CustomerSupportContext.set_mcp_client_ctx(mcp_client)
    # CustomerSupportContext.set_gateway_client_ctx(gateway_client)

    # logger.info("Listing tools from clients")
    # gateway_tools = gateway_client.list_tools_sync()
    # mcp_tools = mcp_client.list_tools_sync()
    # logger.info(
    #     f"Loaded {len(gateway_tools)} gateway tools and {len(mcp_tools)} MCP tools"
    # )

    # Initialize Aurora PostgreSQL MCP client
    try:
        logger.info("Initializing Aurora PostgreSQL MCP client")
        aurora_client = MCPClient(
            lambda: stdio_client(
                StdioServerParameters(
                    command="uvx",
                    args=[
                        "awslabs.postgres-mcp-server@latest",
                        "--resource_arn", AURORA_CLUSTER_ARN,
                        "--secret_arn", AURORA_SECRET_ARN,
                        "--database", AURORA_DATABASE,
                        "--region", AWS_REGION,
                        "--readonly", "True",
                    ]
                )
            )
        )

        aurora_client.start()
        CustomerSupportContext.set_aurora_mcp_client_ctx(aurora_client)
        logger.info("Aurora PostgreSQL MCP client started")
    except Exception as e:
        logger.error(f"Failed to initialize Aurora MCP client: {e}", exc_info=True)
        print("\n🔍 Full error traceback:")
        traceback.print_exc()
        raise

    # Initialize agent
    logger.info(f"Initializing agent with model: {MODEL_ID}")
    model = BedrockModel(model_id=MODEL_ID)
    agent = Agent(
        model=model,
        # tools=gateway_tools + mcp_tools,
        tools=aurora_client.list_tools_sync(),
        system_prompt="You're a helpful customer support assistant",
    )

    CustomerSupportContext.set_agent_ctx(agent)
    logger.info("Agent initialized successfully")


@asynccontextmanager
async def lifespan(app):
    """Application lifespan manager for startup and cleanup."""
    try:
        logger.info("Application starting")
        yield  # Application runs here

    except Exception as e:
        logger.error(f"Error during application lifespan: {e}", exc_info=True)
        raise

    finally:
        # Cleanup
        logger.info("Cleaning up resources")

        mcp_client = CustomerSupportContext.get_mcp_client_ctx()
        if mcp_client is not None:
            try:
                mcp_client.stop()
                logger.info("MCP client stopped")
            except Exception as e:
                logger.error(f"Error stopping MCP client: {e}")

        gateway_client = CustomerSupportContext.get_gateway_client_ctx()
        if gateway_client is not None:
            try:
                gateway_client.stop()
                logger.info("Gateway client stopped")
            except Exception as e:
                logger.error(f"Error stopping gateway client: {e}")

        aurora_client = CustomerSupportContext.get_aurora_mcp_client_ctx()
        if aurora_client is not None:
            try:
                aurora_client.stop()
                logger.info("Aurora client stopped")
            except Exception as e:
                logger.error(f"Error stopping Aurora client: {e}")


app = BedrockAgentCoreApp(lifespan=lifespan)


@app.middleware("http")
async def initialization_middleware(request, call_next):
    """Middleware to initialize clients and set workload access token before request."""
    # Extract and set workload access token from headers
    headers = request.headers
    agent_identity_token = headers.get("WorkloadAccessToken")
    if agent_identity_token:
        BedrockAgentCoreContext.set_workload_access_token(agent_identity_token)

    # Initialize clients on first request
    await initialize_clients()

    # Pass request to next handler
    response = await call_next(request)

    return response


@app.entrypoint
async def strands_agent_bedrock(payload: dict, context) -> str:
    """
    Invoke the agent with a user prompt.

    Args:
        payload: Dictionary containing the user's prompt
        context: Request context with session information

    Returns:
        Agent's response string

    Raises:
        RuntimeError: If agent is not initialized
        KeyError: If prompt is missing from payload
    """
    try:
        # Get agent from context
        agent = CustomerSupportContext.get_agent_ctx()
        if agent is None:
            logger.error("Agent not initialized")
            raise RuntimeError("Agent not initialized. Check application startup logs.")

        # Extract user message
        user_message = payload.get("prompt")
        if not user_message:
            raise KeyError("'prompt' field is required in payload")

        # Log request
        session_id = getattr(context, "session_id", "unknown")
        logger.info(f"Processing request for session: {session_id}")
        logger.debug(f"User prompt: {user_message[:100]}...")  # Log first 100 chars

        # Invoke agent
        response = agent(user_message)
        logger.info(f"Request completed for session: {session_id}")

        return response

    except Exception as e:
        logger.error(f"Error processing request: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    app.run()
