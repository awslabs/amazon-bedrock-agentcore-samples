"""Application settings using Pydantic Settings."""

from os import environ

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )

    # API Settings
    api_title: str = "CX Agent Clean"
    api_version: str = "1.0.0"
    api_description: str = "Clean Architecture CX Agent"

    # Server Settings
    host: str = Field(default="0.0.0.0", description="Server host")  # nosec B104
    port: int = Field(default=8080, description="Server port")
    debug: bool = Field(default=False, description="Debug mode")

    # LLM Settings
    default_model: str = Field(
        default="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
        description="Default LLM model",
    )

    # AWS Settings
    aws_region: str = Field(
        default=environ.get(
            "AWS_REGION", environ.get("AWS_DEFAULT_REGION", "us-west-2")
        ),
        description="AWS region",
    )

    # Logging
    log_level: str = Field(default="INFO", description="Log level")

    # Langfuse Settings
    langfuse_enabled: bool = Field(default=True, description="Enable Langfuse tracing")

    # Guardrail Settings
    bedrock_guardrail_id: str | None = Field(
        default=None, description="Bedrock Guardrail ID"
    )
    guardrails_enabled: bool = Field(
        default=True, description="Enable content guardrails"
    )

    # Knowledge Base Settings
    bedrock_kb_id: str | None = Field(
        default=None, description="Bedrock Knowledge Base ID"
    )


# Global settings instance
settings = Settings()
