"""
Memory management package for marketing research agents.

This package provides AgentCore Memory integration for the marketing research agent system,
enabling persistent memory capabilities across agent interactions.
"""

from .memory_manager import MarketingMemoryManager
from .hooks import MarketingMemoryHookProvider

__all__ = [
    "MarketingMemoryManager",
    "MarketingMemoryHookProvider",
]