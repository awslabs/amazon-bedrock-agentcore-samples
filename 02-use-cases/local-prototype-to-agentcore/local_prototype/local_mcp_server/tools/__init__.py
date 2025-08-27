"""
Tools package for LocalMCP MCP Server
"""

from .system_tools import register_system_tools
from .insurance_tools import register_insurance_tools

__all__ = [
    'register_system_tools',
    'register_insurance_tools'
]
