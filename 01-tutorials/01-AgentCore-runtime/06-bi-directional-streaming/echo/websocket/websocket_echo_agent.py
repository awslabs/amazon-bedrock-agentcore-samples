import asyncio
import logging
import os
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.responses import JSONResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.get("/ping")
async def ping():
    logger.debug("Ping endpoint called")
    return JSONResponse({"status": "ok"})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info(f"Agent runtime WebSocket connection established: {websocket.client}")
    
    try:
        while True:
            try:
                # Try to receive text message
                message = await websocket.receive_text()
                logger.info(f"Agent runtime received text: {message}")
                await websocket.send_text(message)
            except:
                # Try to receive binary message
                try:
                    data = await websocket.receive_bytes()
                    logger.info(f"Agent runtime received binary: {len(data)} bytes")
                    await websocket.send_bytes(data)
                except:
                    # If neither works, break the loop
                    break
            
    except WebSocketDisconnect:
        logger.info(f"Agent runtime WebSocket connection closed: {websocket.client}")
    except Exception as e:
        logger.error(f"Agent runtime WebSocket error: {e}")
        try:
            await websocket.close()
        except:
            pass

async def run_server(host: str, port: int):
    """Run server on specified host and port."""
    config = uvicorn.Config(
        app, 
        host=host, 
        port=port, 
        log_level="info",
        ws="websockets"  # Use websockets library
    )
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    """Run the Agent Runtime WebSocket Echo Server on both ports."""
    host = os.environ.get("AGENT_RUNTIME_HOST", "0.0.0.0")
    
    logger.info(f"Starting Agent Runtime WebSocket Echo Server on {host}:8080 and {host}:8081")
    
    # Run servers on both ports concurrently
    await asyncio.gather(
        run_server(host, 8080),
        run_server(host, 8081)
    )

if __name__ == "__main__":
    asyncio.run(main())

