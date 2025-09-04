"""
Application context models
"""

from dataclasses import dataclass


@dataclass
class AppContext:
    """Application context for managing server state"""
    projects_created: int = 0
    commands_executed: int = 0
