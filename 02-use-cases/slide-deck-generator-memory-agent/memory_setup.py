"""
AgentCore Memory setup for slide deck agent with user preferences strategy
"""

import logging
import json
import boto3
from botocore.exceptions import ClientError

# Memory management modules (based on sample)
from bedrock_agentcore_starter_toolkit.operations.memory.manager import (
    Memory,
    MemoryManager,
)
from bedrock_agentcore_starter_toolkit.operations.memory.models.strategies import (
    CustomUserPreferenceStrategy,
    ExtractionConfig,
    ConsolidationConfig,
)
from bedrock_agentcore.memory.session import MemorySessionManager

from config import AWS_REGION, MEMORY_NAME, MEMORY_EXPIRY_DAYS

logger = logging.getLogger(__name__)


class SlideMemoryManager:
    """Manages AgentCore Memory for slide deck user preferences"""

    def __init__(self, region: str = AWS_REGION):
        self.region = region
        self.memory_manager = MemoryManager(region_name=region)
        self.memory_name = MEMORY_NAME
        self.memory_id = None
        self.memory_execution_role_arn = None

    def create_memory_execution_role(self) -> str:
        """Create IAM role for AgentCore Memory custom strategies"""
        iam_client = boto3.client("iam", region_name=self.region)

        # Get current AWS account ID
        sts_client = boto3.client("sts", region_name=self.region)
        account_id = sts_client.get_caller_identity()["Account"]

        role_name = "SlideDeckAgentMemoryExecutionRole"
        role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"

        # Trust policy for AgentCore Memory service
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": ["bedrock-agentcore.amazonaws.com"]},
                    "Action": "sts:AssumeRole",
                    "Condition": {
                        "StringEquals": {"aws:SourceAccount": account_id},
                        "ArnLike": {
                            "aws:SourceArn": f"arn:aws:bedrock-agentcore:{self.region}:{account_id}:*"
                        },
                    },
                }
            ],
        }

        # Permissions policy for Bedrock model invocation
        permissions_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "bedrock:InvokeModel",
                        "bedrock:InvokeModelWithResponseStream",
                    ],
                    "Resource": [
                        "arn:aws:bedrock:*::foundation-model/*",
                        "arn:aws:bedrock:*:*:inference-profile/*",
                    ],
                    "Condition": {"StringEquals": {"aws:ResourceAccount": account_id}},
                }
            ],
        }

        try:
            # Check if role already exists
            try:
                iam_client.get_role(RoleName=role_name)
                logger.info(f"✅ IAM role already exists: {role_arn}")
                return role_arn
            except ClientError as e:
                if e.response["Error"]["Code"] != "NoSuchEntity":
                    raise

            # Create the role
            logger.info(f"Creating IAM role: {role_name}")
            iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description="Execution role for Slide Deck Agent Memory",
            )

            # Attach the permissions policy
            iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName="SlideDeckMemoryBedrockAccess",
                PolicyDocument=json.dumps(permissions_policy),
            )

            logger.info(f"✅ Successfully created IAM role: {role_arn}")

            # Wait for role propagation
            import time

            logger.info("⏳ Waiting for role propagation...")
            time.sleep(10)

            return role_arn

        except Exception as e:
            logger.error(f"❌ Failed to create IAM role: {e}")
            raise

    def create_user_preference_strategy(self) -> CustomUserPreferenceStrategy:
        """Create user preferences strategy for slide deck styling"""

        return CustomUserPreferenceStrategy(
            name="SlideStylePreferences",
            description="Captures user preferences for slide deck styling, themes, colors, and presentation types",
            extraction_config=ExtractionConfig(
                append_to_prompt="""
                Extract user preferences for slide presentations including:
                - Color schemes (blue, green, purple, red) and when they prefer each
                - Font families (modern, classic, technical, creative) and usage contexts
                - Presentation types (tech, business, academic, creative) and associated styles
                - Content types (legal, compliance, technical, business, creative) and their preferred color schemes
                - Visual preferences (gradients, shadows, spacing: compact/comfortable/spacious)
                - Theme styles (professional, elegant, minimal) and preferred combinations
                - Any patterns in their choices for different audiences or topics

                Focus on explicit preferences and recurring patterns in their choices.
                """,
                model_id="global.anthropic.claude-sonnet-4-5-20250929-v1:0",
            ),
            consolidation_config=ConsolidationConfig(
                append_to_prompt="""
                Consolidate user slide deck style preferences into a comprehensive profile:
                - Default color scheme and when they deviate from it
                - Preferred font combinations for different presentation contexts
                - Style patterns for tech vs business vs academic presentations
                - Visual design preferences (modern vs classic, minimal vs detailed)
                - Consistent choices that indicate strong preferences

                Create a clear preference profile for future slide generation.
                """,
                model_id="global.anthropic.claude-sonnet-4-5-20250929-v1:0",
            ),
            namespaces=["slidedecks/user/{actorId}/style_preferences"],
        )

    def create_memory(self) -> Memory:
        """Create the slide deck memory resource with user preferences strategy"""

        # Create IAM role
        self.memory_execution_role_arn = self.create_memory_execution_role()

        # Create single user preference strategy
        strategy = self.create_user_preference_strategy()

        logger.info(f"✅ Configured memory strategy: {strategy.name}")
        logger.info(f"   Description: {strategy.description}")
        logger.info(f"   Namespaces: {strategy.namespaces}")

        try:
            memory = self.memory_manager.get_or_create_memory(
                name=self.memory_name,
                strategies=[strategy],  # Single strategy focused on user preferences
                description="Memory for slide deck agent user style preferences",
                event_expiry_days=MEMORY_EXPIRY_DAYS,
                memory_execution_role_arn=self.memory_execution_role_arn,
            )

            self.memory_id = memory.id
            logger.info("✅ Memory created successfully:")
            logger.info(f"   Memory ID: {memory.id}")
            logger.info(f"   Memory Name: {memory.name}")

            return memory

        except Exception as e:
            logger.error(f"❌ Memory creation failed: {e}")
            raise

    def get_session_manager(self, memory_id: str) -> MemorySessionManager:
        """Get a memory session manager for the created memory"""
        return MemorySessionManager(memory_id=memory_id, region_name=self.region)

    def cleanup_memory(self, memory_id: str):
        """Clean up memory resource"""
        try:
            self.memory_manager.delete_memory(memory_id)
            logger.info(f"✅ Successfully deleted memory: {memory_id}")
        except Exception as e:
            logger.error(f"❌ Failed to delete memory: {e}")

    def delete_existing_memory(self) -> bool:
        """Find and delete existing memory by name"""
        try:
            logger.info(f"🔍 Searching for existing memory: {self.memory_name}")

            # List all memories to find the one with matching name
            memories = self.memory_manager.list_memories()

            for memory in memories:
                if memory.name == self.memory_name:
                    logger.info(f"📦 Found existing memory: {memory.id}")
                    logger.info("⚠️  Deleting memory to apply new configuration...")
                    self.cleanup_memory(memory.id)
                    logger.info("✅ Memory deleted successfully")
                    return True

            logger.info(f"ℹ️  No existing memory found with name: {self.memory_name}")
            return False

        except Exception as e:
            logger.error(f"❌ Failed to delete existing memory: {e}")
            return False


# Initialize logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def setup_slide_deck_memory() -> tuple:
    """Setup slide deck memory and return memory object and session manager"""

    logger.info("🚀 Setting up Slide Deck Agent Memory (User Preferences Only)...")

    # Create memory manager
    memory_mgr = SlideMemoryManager()

    # Create memory resource
    memory = memory_mgr.create_memory()

    # Create session manager
    session_manager = memory_mgr.get_session_manager(memory.id)

    logger.info("🎉 Slide Deck Agent Memory Ready!")

    return memory, session_manager, memory_mgr


if __name__ == "__main__":
    # Demo the memory setup
    try:
        memory, session_mgr, mgr = setup_slide_deck_memory()
        print(f"Memory ID: {memory.id}")
        print(f"Memory Name: {memory.name}")
        print("✅ Memory setup complete - ready for user preference learning!")
    except Exception as e:
        print(f"❌ Error setting up memory: {e}")
