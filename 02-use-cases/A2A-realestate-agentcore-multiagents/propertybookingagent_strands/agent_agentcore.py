"""
Property Booking Agent - AgentCore Runtime Entry Point
A2A server for deployment to Bedrock AgentCore with OAuth authentication
"""

import os
import logging
import uvicorn
from fastapi import FastAPI
from agent import create_property_booking_agent
from strands.multiagent.a2a import A2AServer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get runtime URL from environment variable
# AgentCore sets this automatically when deployed
runtime_url = os.environ.get('AGENTCORE_RUNTIME_URL', 'http://0.0.0.0:9000/')

logger.info(f"Starting Property Booking Agent A2A Server")
logger.info(f"Runtime URL: {runtime_url}")

# Create the Strands agent
strands_agent = create_property_booking_agent()

# Create A2A server
# Port 9000 is required for AgentCore A2A protocol
host = "0.0.0.0"  # nosec B104 - required for AgentCore A2A protocol
port = 9000

# Create A2A server with serve_at_root=True for AgentCore
a2a_server = A2AServer(
    agent=strands_agent,
    http_url=runtime_url,
    serve_at_root=True  # Required for AgentCore deployment
)

# Create FastAPI app
app = FastAPI(title="Property Booking Agent")

# Health check endpoint
@app.get("/ping")
def ping():
    """Health check endpoint."""
    return {"status": "healthy", "agent": "property_booking_agent"}

# Mount A2A server at root path
app.mount("/", a2a_server.to_fastapi_app())

logger.info(f"A2A server configured on {host}:{port}")
logger.info(f"Agent card available at: /.well-known/agent-card.json")

if __name__ == "__main__":
    # Run the server
    logger.info("Starting uvicorn server...")
    uvicorn.run(app, host=host, port=port)
