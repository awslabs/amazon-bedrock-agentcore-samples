from pydantic_settings import BaseSettings
from botocore.config import Config as BotocoreConfig
from functools import cached_property
from typing import List, Dict, Any

class Configuration(BaseSettings):
    aws_region: str = "us-east-1"

    # Research agent
    research_model: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    research_thinking_enabled: bool = False
    research_thinking_tokens: int = 4096

    # Supervisor agent
    supervisor_model: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    supervisor_thinking_enabled: bool = False
    supervisor_thinking_tokens: int = 4096

    # Database agent
    database_model: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    database_thinking_enabled: bool = False
    database_thinking_tokens: int = 4096

    # Code generator agent
    code_generator_model: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    code_generator_thinking_enabled: bool = False
    code_generator_thinking_tokens: int = 4096

    # Reporting agent
    reporting_model: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    reporting_thinking_enabled: bool = False
    reporting_thinking_tokens: int = 4096

    # Memory configuration
    memory_enabled: bool = True
    memory_event_expiry_days: int = 1
    memory_name: str = "MarketingResearchAgentMemory"
    memory_description: str = "Memory for marketing research agent system with competitive intelligence and team preferences"

    # DynamoDB Table Configuration (matches CDK stack definition)
    customer_data_table: str = "marketing-customer-data"
    marketing_channel_gsi: str = "marketing-channel-index"
    customer_segment_gsi: str = "customer-segment-index"

    # Boto config parameters
    boto_max_attempts: int = 10
    boto_connect_timeout: int = 10
    boto_read_timeout: int = 120

    @cached_property
    def boto_config(self) -> BotocoreConfig:
        return BotocoreConfig(
            retries={"max_attempts": self.boto_max_attempts, "mode": "adaptive"},
            connect_timeout=self.boto_connect_timeout,
            read_timeout=self.boto_read_timeout
        )
    
    @cached_property
    def memory_strategies(self) -> List[Dict[str, Any]]:
        """Memory strategy definitions for AgentCore Memory."""
        return [
            {
                "semanticMemoryStrategy": {
                    "name": "MarketIntelligence",
                    "description": "Captures market research facts and competitor intelligence",
                    "namespaces": ["marketing/{actorId}/intelligence"]
                }
            },
            {
                "userPreferenceMemoryStrategy": {
                    "name": "TeamPreferences", 
                    "description": "Tracks marketing team preferences and methodologies",
                    "namespaces": ["marketing/{actorId}/preferences"]
                }
            }
        ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

config = Configuration()
