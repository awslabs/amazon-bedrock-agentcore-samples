"""
LlamaIndex integration with Amazon Bedrock AgentCore Browser Tool.

This package provides LlamaIndex tools and utilities for integrating with
AgentCore's enterprise-grade browser automation capabilities.
"""

__version__ = "0.1.0"
__author__ = "AWS AgentCore Team"

from integration import LlamaIndexAgentCoreIntegration
from client import AgentCoreBrowserClient
from config import BrowserConfiguration, IntegrationConfig

__all__ = [
    "LlamaIndexAgentCoreIntegration",
    "AgentCoreBrowserClient", 
    "BrowserConfiguration",
    "IntegrationConfig"
]