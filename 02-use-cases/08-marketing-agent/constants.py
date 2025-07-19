import uuid
import os
from botocore.config import Config as BotocoreConfig
from strands.models import BedrockModel

# A unique session ID for this run, used for observability and tracing.
SESSION_ID = str(uuid.uuid4())

# Create a boto client config with custom settings
BOTO_CONFIG = BotocoreConfig(
    retries={"max_attempts": 3, "mode": "standard"},
    connect_timeout=10,
    read_timeout=300  # 5 minutes for long-running tasks
)

# Create a configured Bedrock model
BEDROCK_MODEL = BedrockModel(
    model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    region_name=os.getenv("AWS_DEFAULT_REGION", "us-west-2"),
    temperature=0.7,
    max_tokens=32000,
    boto_client_config=BOTO_CONFIG,
) 