"""
System information tools for LocalMCP MCP Server
"""

import os
import platform
import sys
from pathlib import Path
import psutil

# Add parent directory to path for imports
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

try:
    from ..config import PROJECTS_DIR
    from ..models import TEMPLATES
except ImportError:
    from config import PROJECTS_DIR
    from models.templates import TEMPLATES


def register_system_tools(mcp):
    """Register all system information tools with the MCP server"""
    
    @mcp.tool()
    def system_info() -> str:
        """
        Get comprehensive system information.
        
        Returns:
            Detailed system information including hardware, OS, and server stats
        """
        try:
            result = "🖥️  System Information\n\n"
            
            # Platform information
            result += "Platform:\n"
            result += f"  System: {platform.system()}\n"
            result += f"  Release: {platform.release()}\n"
            result += f"  Version: {platform.version()}\n"
            result += f"  Machine: {platform.machine()}\n"
            result += f"  Processor: {platform.processor()}\n"
            result += f"  Architecture: {platform.architecture()[0]}\n\n"
            
            # CPU information
            result += "CPU:\n"
            result += f"  Physical cores: {psutil.cpu_count(logical=False)}\n"
            result += f"  Total cores: {psutil.cpu_count(logical=True)}\n"
            
            # Get CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            result += f"  CPU Usage: {cpu_percent}%\n\n"
            
            # Memory information
            memory = psutil.virtual_memory()
            result += "Memory:\n"
            result += f"  Total: {memory.total // (1024**3)} GB\n"
            result += f"  Available: {memory.available // (1024**3)} GB\n"
            result += f"  Used: {memory.used // (1024**3)} GB\n"
            result += f"  Percentage: {memory.percent}%\n\n"
            
            # Disk information
            disk = psutil.disk_usage('/')
            result += "Disk:\n"
            result += f"  Total: {disk.total // (1024**3)} GB\n"
            result += f"  Used: {disk.used // (1024**3)} GB\n"
            result += f"  Free: {disk.free // (1024**3)} GB\n"
            result += f"  Percentage: {(disk.used / disk.total) * 100:.1f}%\n\n"
            
            # Environment information
            result += "Environment:\n"
            result += f"  Python Version: {platform.python_version()}\n"
            result += f"  Current Directory: {os.getcwd()}\n"
            result += f"  Home Directory: {Path.home()}\n\n"
            
            # Server statistics
            ctx = mcp.get_context()
            if hasattr(ctx, 'lifespan_context'):
                result += "LocalMCP Server Stats:\n"
                result += f"  Projects Created: {ctx.lifespan_context.projects_created}\n"
                result += f"  Commands Executed: {ctx.lifespan_context.commands_executed}\n"
                result += f"  Available Templates: {len(TEMPLATES)}\n"
                result += f"  Projects Directory: {PROJECTS_DIR}\n"
            
            return result
            
        except Exception as e:
            return f"Error getting system information: {str(e)}"
