"""
Real Estate Coordinator Agent - AgentCore Entrypoint

This file provides the entrypoint for deploying the Real Estate Coordinator to Bedrock AgentCore.
It uses FastAPI with A2AServer for A2A protocol support.
"""

import os
import sys
import logging
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn
from strands.multiagent.a2a import A2AServer
from agent import create_realestate_coordinator, cleanup, set_request_bearer_token, _bearer_token_var, _bearer_token_store

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from common.utils.logging_config import setup_logging

# Configure structured logging
logger = setup_logging("realestate_coordinator", level=os.getenv("LOG_LEVEL", "INFO"), use_json=True)

# Middleware to extract bearer token from requests
class BearerTokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        logger.info(f"=== MIDDLEWARE START === Path: {request.url.path}")
        
        # Extract Authorization header
        auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove 'Bearer ' prefix
            set_request_bearer_token(token)
            logger.info(f"✓ Extracted bearer token from incoming request: {token[:20]}...")
            logger.info(f"✓ Token set in context var and backup store")
        else:
            logger.warning(f"✗ No bearer token found in request!")
            logger.warning(f"  Available headers: {list(request.headers.keys())}")
        
        response = await call_next(request)
        
        logger.info(f"=== MIDDLEWARE END === Path: {request.url.path}")
        return response

# AgentCore runtime URL
runtime_url = os.environ.get('AGENTCORE_RUNTIME_URL', 'http://127.0.0.1:9000/')
host = os.getenv("AGENT_HOST", "0.0.0.0")  # nosec B104 - required for AgentCore A2A protocol
port = int(os.getenv("AGENT_PORT", "9000"))

# Create the coordinator agent
agent = create_realestate_coordinator()

# Create A2A server
a2a_server = A2AServer(
    agent=agent,
    http_url=runtime_url,
    serve_at_root=True
)

# Get the FastAPI app from A2A server and add middleware to it
app = a2a_server.to_fastapi_app()

# Add bearer token middleware to the A2A server's app
app.add_middleware(BearerTokenMiddleware)

@app.get("/ping")
def ping():
    """Health check endpoint"""
    return {"status": "healthy", "agent": "realestate-coordinator"}

@app.get("/test-token")
async def test_token():
    """Test endpoint to check if bearer token is in context"""
    token = _bearer_token_var.get()
    backup_token = _bearer_token_store.get('current')
    return {
        "context_var_token": token[:20] + "..." if token else None,
        "backup_store_token": backup_token[:20] + "..." if backup_token else None
    }

@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    logger.info("Real Estate Coordinator starting up")
    logger.info(f"Runtime URL: {runtime_url}")
    logger.info(f"Server: {host}:{port}")
    
    # Log configured agent URLs
    search_url = os.getenv("PROPERTY_SEARCH_AGENT_URL", "NOT_SET")
    booking_url = os.getenv("PROPERTY_BOOKING_AGENT_URL", "NOT_SET")
    logger.info(f"Property Search Agent URL: {search_url}")
    logger.info(f"Property Booking Agent URL: {booking_url}")

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler"""
    logger.info("Real Estate Coordinator shutting down")
    await cleanup()

if __name__ == "__main__":
    logger.info("Starting Real Estate Coordinator...")
    logger.info(f"Agent card: http://{host}:{port}/.well-known/agent-card.json")
    uvicorn.run(app, host=host, port=port)
