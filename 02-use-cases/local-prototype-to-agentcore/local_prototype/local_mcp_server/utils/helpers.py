"""
Helper utilities for LocalMCP MCP Server
"""

import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

# Add parent directory to path for imports
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

try:
    from ..config import PROJECTS_DIR
    from ..models import AppContext
except ImportError:
    from config import PROJECTS_DIR
    from models.context import AppContext


@asynccontextmanager
async def app_lifespan(server) -> AsyncIterator[AppContext]:
    """Manage application lifecycle with server context"""
    # Ensure projects directory exists
    PROJECTS_DIR.mkdir(exist_ok=True)
    
    # Initialize context
    context = AppContext()
    
    # Log startup
    logging.info(f"Server startup complete - context initialized ${context}")
    
    try:
        yield context
    finally:
        # Log shutdown
        logging.info("Server shutting down - cleaning up resources")
        # Cleanup if needed
        pass
