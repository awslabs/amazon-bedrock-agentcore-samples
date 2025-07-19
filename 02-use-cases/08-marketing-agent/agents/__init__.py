import os
from strands.models import BedrockModel
from constants import SESSION_ID

# --- Shared Configuration ---

# Set to "enabled" to see rich UI for tools in the console.
os.environ["STRANDS_TOOL_CONSOLE_MODE"] = "enabled"

# Centralized model definition for all agents
# Using Claude 3.5 Sonnet on AWS Bedrock as requested.
# Ensure your AWS credentials are configured correctly.
default_model = BedrockModel(
    model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
    # Pass the session ID to the model for tracing purposes
    trace_attributes={"session.id": SESSION_ID},
) 