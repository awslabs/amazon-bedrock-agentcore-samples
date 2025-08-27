"""
Resource handlers for LocalMCP MCP Server
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))


def register_resources(mcp):
    """Register all resources with the MCP server"""
    
    @mcp.resource("projects://all")
    def list_all_projects() -> str:
        """Resource providing complete list of all created projects"""
        # We need to create a temporary instance to call list_projects
        # This is a bit of a hack, but works for the resource system
        from ..tools.project_tools import register_project_tools
        
        # Create a mock MCP object to get the list_projects function
        class MockMCP:
            def tool(self):
                def decorator(func):
                    return func
                return decorator
        
        mock_mcp = MockMCP()
        register_project_tools(mock_mcp)
        
        # Import the function we need
        try:
            from ..config import PROJECTS_DIR
        except ImportError:
            from config import PROJECTS_DIR
        
        if not PROJECTS_DIR.exists():
            return "No projects directory found. Create a project first."
        
        projects = []
        for item in PROJECTS_DIR.iterdir():
            if item.is_dir():
                # Get basic info
                project_info = {
                    "name": item.name,
                    "path": str(item),
                    "created": item.stat().st_ctime,
                    "files": len(list(item.glob("*"))) if item.exists() else 0
                }
                
                # Try to detect project type
                if (item / "package.json").exists():
                    project_info["type"] = "Node.js"
                elif (item / "requirements.txt").exists():
                    project_info["type"] = "Python"
                elif (item / "index.html").exists():
                    project_info["type"] = "Web"
                else:
                    project_info["type"] = "Unknown"
                
                projects.append(project_info)
        
        if not projects:
            return "No projects found in " + str(PROJECTS_DIR)
        
        # Format output
        result = f"Found {len(projects)} project(s) in {PROJECTS_DIR}:\n\n"
        for project in sorted(projects, key=lambda x: x["name"]):
            result += f"📁 {project['name']}\n"
            result += f"   Type: {project['type']}\n"
            result += f"   Path: {project['path']}\n"
            result += f"   Files: {project['files']}\n"
            result += f"   Created: {project['created']}\n\n"
        
        return result

    @mcp.resource("templates://all")
    def list_all_templates() -> str:
        """Resource providing available project templates"""
        try:
            from ..models import TEMPLATES
        except ImportError:
            from models.templates import TEMPLATES
        
        result = f"Available Project Templates ({len(TEMPLATES)}):\n\n"
        
        for template_id, template_data in TEMPLATES.items():
            result += f"🏗️  {template_id}\n"
            result += f"   Name: {template_data['name']}\n"
            result += f"   Description: {template_data['description']}\n"
            result += f"   Files: {len(template_data['files'])}\n"
            result += f"   Includes: {', '.join(template_data['files'].keys())}\n\n"
        
        return result

    @mcp.resource("system://info")
    def get_system_info() -> str:
        """Resource providing current system status and server information"""
        import os
        import platform
        from pathlib import Path
        import psutil
        try:
            from ..config import PROJECTS_DIR
            from ..models import TEMPLATES
        except ImportError:
            from config import PROJECTS_DIR
            from models.templates import TEMPLATES
        
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
            result += "LocalMCP Server Stats:\n"
            result += f"  Available Templates: {len(TEMPLATES)}\n"
            result += f"  Projects Directory: {PROJECTS_DIR}\n"
            
            return result
            
        except Exception as e:
            return f"Error getting system information: {str(e)}"
