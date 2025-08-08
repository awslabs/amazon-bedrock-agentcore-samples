#!/usr/bin/env python3
"""
Entry point for LocalMCP MCP Server
Run this file to start the server
"""

import sys
import logging
from pathlib import Path

# Add the current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from mcp.server.fastmcp import FastMCP
from config import SERVER_NAME, SERVER_VERSION, PROJECTS_DIR, AUTO_INSURANCE_API_URL
from utils.helpers import app_lifespan
from tools.system_tools import register_system_tools
from tools.insurance_tools import register_insurance_tools
from resources.resource_handlers import register_resources


# Create FastMCP server with lifespan management at module level
mcp = FastMCP(
    name=SERVER_NAME,
    dependencies=["psutil", "requests", "beautifulsoup4"],
    lifespan=app_lifespan,
)

# Register only essential tools
register_system_tools(mcp)
register_insurance_tools(mcp)

# Register resources
register_resources(mcp)


def create_server():
    """Create and configure the MCP server (for backwards compatibility)"""
    return mcp


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    print(f"🚀 Starting {SERVER_NAME} v{SERVER_VERSION} MCP server...")
    print(f"📂 Projects directory: {PROJECTS_DIR}")
    print(f"🔌 Insurance API URL: {AUTO_INSURANCE_API_URL}")
    print("✅ Server is running. Press CTRL+C to stop.")
    
    try:
        print("Starting with streamable-http transport...")
        mcp.run(transport="streamable-http")
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user.")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)
