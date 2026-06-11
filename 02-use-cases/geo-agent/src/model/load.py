"""Centralized Amazon Bedrock model configuration.

Loads the BedrockModel with optional Amazon Bedrock Guardrail support.
All sub-agents (rewriter, scorer, etc.) share this configuration via load_model().
"""

import os
from strands.models import BedrockModel

MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
GUARDRAIL_ID = os.environ.get("BEDROCK_GUARDRAIL_ID", "")
GUARDRAIL_VERSION = os.environ.get("BEDROCK_GUARDRAIL_VERSION", "DRAFT")


def load_model(temperature: float | None = None) -> BedrockModel:
    """Create an Amazon Bedrock model client with optional Guardrail.

    Guardrail is automatically enabled when the BEDROCK_GUARDRAIL_ID
    environment variable is set. All sub-agents (rewriter, scorer, etc.)
    share this configuration.

    Args:
        temperature: Optional temperature override (e.g., 0.1 for scoring consistency).
    """
    kwargs = dict(model_id=MODEL_ID, region_name=AWS_REGION)

    if GUARDRAIL_ID:
        kwargs["guardrail_id"] = GUARDRAIL_ID
        kwargs["guardrail_version"] = GUARDRAIL_VERSION

    if temperature is not None:
        kwargs["temperature"] = temperature

    return BedrockModel(**kwargs)