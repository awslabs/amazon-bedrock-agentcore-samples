#!/usr/bin/env python3
"""
Delete AgentCore Runtime agent using bedrock-agentcore-starter-toolkit.

This script deletes a deployed agent from Amazon Bedrock AgentCore Runtime.
"""

import argparse
import logging
import sys
from pathlib import Path

# Configure logging with basicConfig
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


def _load_deployment_metadata(script_dir: Path) -> dict:
    """Load deployment metadata from .deployment_metadata.json file."""
    import json

    metadata_file = script_dir / ".deployment_metadata.json"
    if metadata_file.exists():
        try:
            return json.loads(metadata_file.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def _delete_agent(agent_id: str, region: str) -> None:
    """
    Delete the agent from AgentCore Runtime.

    Args:
        agent_id: The agent ID to delete
        region: AWS region
    """
    logger.info(f"Deleting agent: {agent_id}")
    logger.info(f"Region: {region}")

    try:
        import boto3

        # Delete the agent endpoint using boto3
        client = boto3.client("bedrock-agentcore", region_name=region)

        logger.info("Deleting agent runtime endpoint...")
        client.delete_agent_runtime_endpoint(agentId=agent_id, endpointName="DEFAULT")

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
    # Delete agent (reads from .deployment_metadata.json automatically)
    uv run python scripts/delete_agent.py

    # Delete with explicit region
    uv run python scripts/delete_agent.py --region us-west-2

    # Delete specific agent ID
    uv run python scripts/delete_agent.py --agent-id my-agent-id --region us-east-1

Environment variables:
    AWS_REGION: AWS region (if --region not specified)
""",
    )

    parser.add_argument(
        "--region",
        default=None,
        help="AWS region (default: reads from .deployment_metadata.json or AWS_REGION env var)",
    )

    parser.add_argument(
        "--agent-id",
        default=None,
        help="Agent ID to delete (default: reads from .deployment_metadata.json)",
    )

    args = parser.parse_args()

    # Get script directory
    script_dir = Path(__file__).parent

    # Load deployment metadata
    metadata = _load_deployment_metadata(script_dir)

    # Get agent ID
    agent_id = args.agent_id or metadata.get("agent_id")
    if not agent_id:
        logger.error("No agent ID provided via --agent-id and .deployment_metadata.json not found")
        logger.error("Specify --agent-id or ensure .deployment_metadata.json exists")
        sys.exit(1)

    # Get region
    region = args.region or metadata.get("region") or __import__("os").environ.get("AWS_REGION")
    if not region:
        logger.error("No region specified")
        logger.error(
            "Specify --region, ensure .deployment_metadata.json contains 'region', or set AWS_REGION env var"
        )
        sys.exit(1)

    # Delete the agent
    try:
        _delete_agent(
            agent_id=agent_id,
            region=region,
        )
    except Exception as e:
        logger.error(f"Failed to delete agent: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
