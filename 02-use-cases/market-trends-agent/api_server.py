"""
FastAPI backend for Market Trends Agent React UI.
Proxies chat requests to the deployed AgentCore Runtime agent.
"""

import json
import os
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import boto3
from botocore.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Market Trends Agent API")

# Allow React dev server to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# AWS region for AgentCore Runtime
REGION = os.getenv("AWS_REGION", "us-east-1")

# Boto3 client with extended timeout for agent responses (browser + LLM calls can be slow)
boto_config = Config(read_timeout=300, retries={"max_attempts": 2})
agentcore_client = boto3.client("bedrock-agentcore", region_name=REGION, config=boto_config)


def load_agent_arn() -> str | None:
    """Load deployed agent ARN from the .agent_arn file created by deploy.py"""
    arn_file = Path(__file__).parent / ".agent_arn"
    if arn_file.exists():
        return arn_file.read_text().strip()
    return None


class ChatRequest(BaseModel):
    message: str = Field(..., max_length=4000)
    session_id: str = Field(default="", max_length=100)


@app.get("/api/health")
def health():
    """Health check — also reports whether the agent is deployed"""
    arn = load_agent_arn()
    return {"status": "ok", "agent_deployed": arn is not None, "region": REGION}


@app.post("/api/chat")
def chat(req: ChatRequest):
    """Send a message to the deployed AgentCore agent and return the response"""
    arn = load_agent_arn()
    if not arn:
        return {"error": "Agent not deployed. Run 'uv run python deploy.py' first."}

    try:
        # Build invocation payload matching the agent's expected format
        payload = json.dumps({"prompt": req.message, "session_id": req.session_id}).encode("utf-8")
        params: dict = {"agentRuntimeArn": arn, "payload": payload}

        # Pass session ID for memory continuity across messages
        if req.session_id:
            params["runtimeSessionId"] = req.session_id

        logger.info(f"Invoking agent | session={req.session_id[:24]}...")
        response = agentcore_client.invoke_agent_runtime(**params)

        # Read the response body (handles both streaming and standard responses)
        if "response" in response:
            body = response["response"].read().decode("utf-8")
        else:
            body = str(response)

        # AgentCore often returns a JSON-encoded string (e.g. "\"hello\\nworld\"")
        # Unwrap it so the frontend receives clean text with real newlines
        try:
            parsed = json.loads(body)
            if isinstance(parsed, str):
                body = parsed
        except (json.JSONDecodeError, TypeError):
            pass

        # Final safety: replace any remaining literal \n sequences with real newlines
        body = body.replace("\\n", "\n")

        return {"response": body, "session_id": req.session_id}

    except Exception as e:
        logger.error(f"Agent invocation error: {e}")
        return {"error": "Agent request failed. Check server logs for details."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
