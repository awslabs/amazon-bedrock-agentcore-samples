"""Configuration management for agents using Pydantic Settings."""

from typing import Optional, Dict
from pydantic_settings import BaseSettings
from pydantic import Field


class AgentSettings(BaseSettings):
    """Base settings for all agents.
    
    This class provides configuration management for Strands agents,
    loading settings from environment variables or .env files.
    """
    
    # Agent configuration
    agent_name: str = Field(..., description="Name of the agent")
    agent_description: str = Field(..., description="Description of agent capabilities")
    agent_port: int = Field(default=5000, description="Port for A2A server")
    agent_version: str = Field(default="1.0.0", description="Agent version")
    
    # Model configuration
    model_id: str = Field(
        default="bedrock/anthropic.claude-3-5-haiku-20241022-v1:0",
        description="Bedrock model ID for agent inference"
    )
    aws_region: str = Field(default="us-east-1", description="AWS region for Bedrock")
    
    # API keys (optional, agent-specific)
    tavily_api_key: Optional[str] = Field(default=None, description="Tavily API key for web search")
    
    # Remote agent URLs (for host agent)
    websearch_agent_url: Optional[str] = Field(
        default=None,
        description="URL of the web search agent for A2A communication"
    )
    currency_agent_url: Optional[str] = Field(
        default=None,
        description="URL of the currency converter agent for A2A communication"
    )
    
    # Logging configuration
    log_level: str = Field(default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR)")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


class DeploymentConfig(BaseSettings):
    """Configuration for AgentCore deployment.
    
    This class manages settings specific to deploying agents
    on Bedrock AgentCore runtime.
    """
    
    agent_name: str = Field(..., description="Name of the agent to deploy")
    entrypoint_file: str = Field(..., description="Path to the AgentCore entrypoint file")
    requirements_file: str = Field(
        default="requirements.txt",
        description="Path to requirements.txt file"
    )
    python_version: str = Field(default="3.11", description="Python version for runtime")
    
    # Environment variables to pass to AgentCore
    environment_variables: Dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables for the deployed agent"
    )
    
    # AgentCore specific settings
    memory_size: int = Field(default=512, description="Memory allocation in MB")
    timeout: int = Field(default=300, description="Timeout in seconds")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
