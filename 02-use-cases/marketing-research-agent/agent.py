from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime
import logging
import json
import uvicorn
import asyncio
import queue
from src.supervisor_agent import SupervisorAgent
from src.config import config
from src.memory.memory_manager import MarketingMemoryManager

logging.basicConfig(level=logging.INFO)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()]
)

app = FastAPI(title="Marketing Research Agent", version="0.1.0")

memory_manager: Optional[MarketingMemoryManager] = None
agent: Optional[SupervisorAgent] = None

class StreamHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.log_queue = queue.Queue()
    
    def emit(self, record):
        log_entry = self.format(record)
        self.log_queue.put(log_entry)

def initialize_agent():
    global memory_manager, agent
    
    memory_config = None
    
    if config.memory_enabled:
        memory_manager = MarketingMemoryManager(config)
        memory_id = memory_manager.initialize_memory()
        memory_manager.validate_memory_access()
        memory_config = memory_manager.get_memory_config_for_agent("supervisor")
        logging.info(f"Memory initialized: {memory_id}")
    
    agent = SupervisorAgent(config, memory_config)
    logging.info(f"Agent created {'with' if memory_config else 'without'} memory")

initialize_agent()

class InvocationRequest(BaseModel):
    input: Dict[str, Any]

@app.post("/invocations")
async def invoke_agent(request: InvocationRequest):
    try:
        user_message = request.input.get("prompt", "")
        if not user_message:
            raise HTTPException(status_code=400, detail="No prompt found in input.")

        stream_handler = StreamHandler()
        stream_handler.setFormatter(logging.Formatter("%(levelname)s | %(name)s | %(message)s"))
        
        root_logger = logging.getLogger()
        root_logger.addHandler(stream_handler)
        
        async def generate_response():
            try:
                def run_agent():
                    return agent(user_message)
                
                loop = asyncio.get_event_loop()
                agent_task = loop.run_in_executor(None, run_agent)
                
                while not agent_task.done():
                    try:
                        log_entry = stream_handler.log_queue.get_nowait()
                        yield f"data: {log_entry}\n\n"
                    except queue.Empty:
                        await asyncio.sleep(0.1)
                
                result = await agent_task
                
                while not stream_handler.log_queue.empty():
                    try:
                        log_entry = stream_handler.log_queue.get_nowait()
                        yield f"data: {log_entry}\n\n"
                    except queue.Empty:
                        break
                
                response = {
                    "message": result.message,
                    "timestamp": datetime.utcnow().isoformat(),
                    "model": "marketing-research-agent",
                }
                yield f"data: RESULT: {json.dumps(response)}\n\n"
                
            except Exception as e:
                yield f"data: ERROR: {str(e)}\n\n"
            finally:
                root_logger.removeHandler(stream_handler)

        return StreamingResponse(
            generate_response(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"}
        )

    except Exception as e:
        logging.error(f"Agent error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent processing failed: {str(e)}")

@app.get("/ping")
async def ping():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)