from strands.models.bedrock import BedrockModel

from config import AGENT_MODEL_ID


def load_model() -> BedrockModel:
    """Get Bedrock model client using IAM credentials."""
    return BedrockModel(model_id=AGENT_MODEL_ID)
