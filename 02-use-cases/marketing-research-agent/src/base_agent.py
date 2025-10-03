import boto3
from abc import ABC
from strands.models import BedrockModel
from .config import Configuration

class BaseAgent(ABC):
    def __init__(self, config: Configuration):
        self.config = config

    def _init_model(self, bedrock_model_id: str, thinking_enabled: bool = False, thinking_budget_tokens: int = 4096):
        """Initialize the appropriate model based on configuration."""
        try:
            session = boto3.Session(region_name=self.config.aws_region)

            model_kwargs = {
                "model_id": bedrock_model_id,
                "boto_session": session,
                "boto_client_config": self.config.boto_config
            }

            if thinking_enabled:
                model_kwargs["additional_request_fields"] = {
                    "thinking": {
                        "type": "enabled",
                        "budget_tokens": thinking_budget_tokens
                    }
                }

            return BedrockModel(**model_kwargs)
        except Exception as e:
            # Handle all initialization errors
            raise RuntimeError(f"Failed to initialize AWS session or BedrockModel: {str(e)}")
