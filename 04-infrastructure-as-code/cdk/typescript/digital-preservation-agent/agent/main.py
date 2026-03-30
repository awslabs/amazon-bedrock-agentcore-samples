"""
Strands agent for digital preservation with Apache Tika, Siegfried, DROID, and MediaInfo.

Deployed to AgentCore Runtime, connects to an AgentCore Gateway
that exposes tools via MCP. Uses SigV4 signing for IAM-authenticated
Gateway access.
"""

import os
import logging

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()

# --- Module-level config (read once at container startup) ---
GATEWAY_URL = os.environ.get("GATEWAY_URL", "")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get("MODEL_ID", "eu.anthropic.claude-3-5-haiku-20241022-v1:0")
AGENT_INSTRUCTION = os.environ.get(
    "AGENT_INSTRUCTION",
    "You are a digital preservation assistant with access to Apache Tika, "
    "Siegfried, DROID, and MediaInfo for file format identification, text "
    "extraction, metadata retrieval, and media analysis. You can also "
    "extract archives and save analysis reports to S3. Apache Tika can "
    "process archives directly, but Siegfried, DROID, and MediaInfo require "
    "files to be extracted first using extract_archive before analysis.",
)

# Cache the model instance — it's stateless and safe to reuse across requests.
model = BedrockModel(inference_profile_id=MODEL_ID, region_name=AWS_REGION)


def _create_mcp_client():
    """Create an MCP client factory for the AgentCore Gateway."""
    return MCPClient(
        lambda: aws_iam_streamablehttp_client(
            endpoint=GATEWAY_URL,
            aws_region=AWS_REGION,
            aws_service="bedrock-agentcore",
        )
    )


@app.entrypoint
def handler(payload: dict) -> dict:
    """Handle incoming agent requests from AgentCore Runtime."""
    prompt = payload.get("prompt", payload.get("message", ""))
    if not prompt:
        return {"error": "No prompt provided", "status": "error"}

    logger.info(
        "Received prompt: %s | model=%s region=%s", prompt[:200], MODEL_ID, AWS_REGION
    )

    # MCPClient uses a context manager to manage the MCP session lifecycle.
    # Each request gets its own session to avoid stale connection issues.
    mcp_client = _create_mcp_client()

    with mcp_client:
        tools = list(mcp_client.list_tools_sync())
        logger.info("Available tools: %s", [t.tool_name for t in tools])

        agent = Agent(
            model=model,
            tools=tools,
            system_prompt=AGENT_INSTRUCTION,
        )

        result = agent(prompt)
        return {"response": str(result.message), "status": "success"}


if __name__ == "__main__":
    app.run()
