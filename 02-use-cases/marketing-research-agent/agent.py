from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime
import logging
import uvicorn
from src.supervisor_agent import SupervisorAgent
from src.config import config
from src.memory.memory_manager import MarketingMemoryManager
# Set logger
logging.basicConfig(level=logging.INFO)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()]
)

app = FastAPI(title="Marketing Research Agent", version="0.1.0")

# Initialize memory manager and agent with memory
memory_manager: Optional[MarketingMemoryManager] = None
agent: Optional[SupervisorAgent] = None

def initialize_agent():
    """Initialize the agent with memory integration."""
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

# Initialize agent on startup
initialize_agent()

class InvocationRequest(BaseModel):
    input: Dict[str, Any]

class InvocationResponse(BaseModel):
    output: Dict[str, Any]

@app.post("/invocations", response_model=InvocationResponse)
async def invoke_agent(request: InvocationRequest):
    try:
        user_message = request.input.get("prompt", "")
        if not user_message:
            raise HTTPException(
                status_code=400,
                detail="No prompt found in input. Please provide a 'prompt' key in the input."
            )

        result = agent(user_message)
        response = {
            "message": result.message,
            "timestamp": datetime.utcnow().isoformat(),
            "model": "marketing-research-agent",
        }

        return InvocationResponse(output=response)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent processing failed: {str(e)}")

@app.get("/ping")
async def ping():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
