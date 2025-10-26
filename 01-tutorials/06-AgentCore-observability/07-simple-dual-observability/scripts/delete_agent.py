#!/usr/bin/env python3
"""
Delete AgentCore Runtime agent using bedrock-agentcore-starter-toolkit.

This script deletes a deployed agent from Amazon Bedrock AgentCore Runtime.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from bedrock_agentcore_starter_toolkit import Runtime


# Configure logging with basicConfig
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


def _load_agent_id(
    script_dir: Path
) -> Optional[str]:
    """Load agent ID from local file."""
    agent_id_file = script_dir / ".agent_id"
    if agent_id_file.exists():
        return agent_id_file.read_text().strip()
    return None


def _delete_agent(
    agent_id: str,
    region: str
) -> None:
    """
    Delete the agent from AgentCore Runtime.

    Args:
        agent_id: The agent ID to delete
        region: AWS region
    """
    logger.info(f"Deleting agent: {agent_id}")
    logger.info(f"Region: {region}")

    try:
        agentcore_runtime = Runtime()

        # The delete() method needs the agent to be configured first
        # We can use the agent_id directly
        agentcore_runtime.delete(agent_id=agent_id, region=region)

        logger.info("=" * 70)
        logger.info("AGENT DELETED SUCCESSFULLY")
        logger.info("=" * 70)
        logger.info(f"Agent ID: {agent_id}")
        logger.info("The agent has been removed from AgentCore Runtime")

    except Exception as e:
        logger.error("=" * 70)
        logger.error("DELETION FAILED")
        logger.error("=" * 70)
        logger.error(f"Error: {str(e)}")
        raise RuntimeError(f"Agent deletion failed: {str(e)}") from e


def main() -> None:
    """Main entry point for agent deletion."""
    parser = argparse.ArgumentParser(
        description="Delete AgentCore Runtime agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
    # Delete agent (reads agent ID from .agent_id file)
    uv run python -m scripts.delete_agent --region us-east-1

    # Delete specific agent ID
    uv run python -m scripts.delete_agent --region us-east-1 --agent-id my-agent-id
""",
    )

    parser.add_argument(
        "--region",
        required=True,
        help="AWS region",
    )

    parser.add_argument(
        "--agent-id",
        help="Agent ID to delete (if not provided, reads from .agent_id file)",
    )

    args = parser.parse_args()

    # Get script directory
    script_dir = Path(__file__).parent

    # Get agent ID
    agent_id = args.agent_id
    if not agent_id:
        agent_id = _load_agent_id(script_dir)
        if not agent_id:
            logger.error("No agent ID provided and .agent_id file not found")
            logger.error("Specify --agent-id or ensure .agent_id file exists")
            sys.exit(1)

    # Delete the agent
    try:
        _delete_agent(
            agent_id=agent_id,
            region=args.region,
        )
    except Exception as e:
        logger.error(f"Failed to delete agent: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
