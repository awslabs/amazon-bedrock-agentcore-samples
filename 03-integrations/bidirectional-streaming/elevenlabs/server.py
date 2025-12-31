"""FastAPI WebSocket server for bidirectional agent with ElevenLabs integration.

Handles WebSocket connections from React frontend, manages audio streaming,
and coordinates between the frontend and the bidirectional agent.
"""

import asyncio
import base64
import json
import logging
import os
from typing import Any
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from strands.experimental.bidi.agent.agent import BidiAgent
from strands.experimental.bidi.models.nova_sonic import BidiNovaSonicModel
from strands import tool
from strands.experimental.bidi.types.events import BidiInputEvent
from elevenlabs_io import NovaElevenLabsIO

# Load environment variables

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="BidiAgent WebSocket Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@tool
def weather(location: str):
    """Get the weather at a specific location

    Args:
        location (str): the location

    Returns:
        dict: a dictionary containing the wether data
    """

    return {
        "location": location,
        "temperature": "24",
        "unit": "celsius",
        "condition": "Sunny",
    }


class BidiAgentHandler:
    """Handler for bidirectional agent WebSocket connections."""

    def __init__(
        self,
        elevenlabs_api_key: str,
        aws_region: str = "us-east-1",
        voice_id: str = "21m00Tcm4TlvDq8ikWAM",
    ):
        """Initialize handler.

        Args:
            elevenlabs_api_key: ElevenLabs API key
            aws_region: AWS region for Bedrock
            voice_id: ElevenLabs voice ID
        """
        self.elevenlabs_api_key = elevenlabs_api_key
        self.aws_region = aws_region
        self.voice_id = voice_id

    async def handle_connection(self, websocket: WebSocket) -> None:
        """Handle individual WebSocket connection.

        Args:
            websocket: FastAPI WebSocket connection
        """
        await websocket.accept()
        logger.info("client_connected=<true> | new client connected")

        # Create queue for audio data from client
        audio_queue: asyncio.Queue[BidiInputEvent] = asyncio.Queue()

        # Create WebSocket send function
        async def websocket_send(data: dict[str, Any]) -> None:
            await websocket.send_json(data)

        # Initialize Nova Sonic + ElevenLabs I/O
        nova_elevenlabs_io = NovaElevenLabsIO(
            audio_queue=audio_queue,
            websocket_send=websocket_send,
            api_key=self.elevenlabs_api_key,
            voice_id=self.voice_id,
        )

        # Initialize agent with Nova Sonic model (Nova 2 Lite)
        # Note: You can change the model_id to use different models
        model = BidiNovaSonicModel(
            region="us-east-1",
            model_id="amazon.nova-sonic-v1:0",
            provider_config={
                "audio": {
                    "input_sample_rate": 16000,
                    "output_sample_rate": 16000,
                    "voice": "matthew",
                }
            },
        )

        agent = BidiAgent(
            model=model,
            system_prompt="You are a helpful assistant. You always answer in the language spoken by the user",
            tools=[weather],
        )

        agent_task: asyncio.Task[None] | None = None
        try:
            # Start agent in background
            agent_task = asyncio.create_task(
                agent.run(
                    inputs=[nova_elevenlabs_io.input()],
                    outputs=[nova_elevenlabs_io.output()],
                )
            )

            # Handle incoming messages from client
            while True:
                try:
                    # Receive message from WebSocket
                    message = await websocket.receive_json()
                    await audio_queue.put(message)
                    logger.debug(
                        "msg_received |  queue_size=<%d>",
                        audio_queue.qsize(),
                    )

                except json.JSONDecodeError:
                    logger.warning("invalid json received from client")
                except WebSocketDisconnect:
                    logger.info("client_disconnected=<true> | client connection closed")
                    break
                except Exception as e:
                    logger.error("error=<%s> | error processing message", str(e))
                    break

        except WebSocketDisconnect:
            logger.info("client_disconnected=<true> | client connection closed")
        except Exception as e:
            logger.error("error=<%s> | unexpected error in connection handler", str(e))
        finally:
            # Clean up
            logger.info("cleaning up agent resources")
            if agent_task:
                agent_task.cancel()
                try:
                    await agent_task
                except asyncio.CancelledError:
                    pass
            await agent.stop()
            logger.info("agent stopped successfully")


# Initialize handler
handler = BidiAgentHandler(
    elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY", ""),
    aws_region=os.getenv("AWS_REGION", "us-east-1"),
    voice_id=os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM"),
)


@app.get("/")
async def root():
    """Root endpoint for health check."""
    return {
        "status": "ok",
        "message": "BidiAgent WebSocket Server",
        "websocket_endpoint": "/ws",
    }


@app.get("/ping")
async def ping():
    """Root endpoint for health check."""
    return {
        "status": "Healthy",
        "time_of_last_update": time.time(),
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for bidirectional agent conversations.

    Args:
        websocket: FastAPI WebSocket connection
    """
    await handler.handle_connection(websocket)


if __name__ == "__main__":
    import uvicorn

    # Validate environment variables
    if not os.getenv("ELEVENLABS_API_KEY"):
        raise ValueError(
            "ELEVENLABS_API_KEY environment variable not set. "
            "Add it to your .env file."
        )

    # Run server with uvicorn
    logger.info("starting fastapi server with uvicorn")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info",
    )
