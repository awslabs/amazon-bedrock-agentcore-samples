#!/usr/bin/env python3
"""
Deploy Strands agent to Amazon Bedrock AgentCore Runtime.

This script uses the bedrock-agentcore-starter-toolkit to deploy the agent
with automatic Docker containerization and OTEL instrumentation.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


def _validate_environment() -> None:
    """Validate required environment and dependencies."""
    try:
        import boto3
        from bedrock_agentcore_starter_toolkit import Runtime

        logger.info("Required packages found: boto3, bedrock-agentcore-starter-toolkit")

    except ImportError as e:
        logger.error(f"Missing required package: {e}")
        logger.error("Please install: pip install -r requirements.txt")
        sys.exit(1)

    # Validate AWS credentials
    try:
        session = boto3.Session()
        sts = session.client('sts')
        identity = sts.get_caller_identity()
        logger.info(f"AWS Account ID: {identity['Account']}")

    except Exception as e:
        logger.error(f"Failed to validate AWS credentials: {e}")
        sys.exit(1)


def _deploy_agent(
    agent_name: str,
    region: str,
    entrypoint: str,
    requirements_file: str,
    script_dir: Path
) -> dict:
    """
    Deploy agent to AgentCore Runtime.

    Args:
        agent_name: Name for the deployed agent
        region: AWS region for deployment
        entrypoint: Path to agent entrypoint file
        requirements_file: Path to requirements.txt
        script_dir: Script directory for saving outputs

    Returns:
        Dictionary with deployment results
    """
    from bedrock_agentcore_starter_toolkit import Runtime
    from boto3.session import Session

    logger.info("Initializing AgentCore Runtime deployment...")

    boto_session = Session(region_name=region)
    agentcore_runtime = Runtime()

    # Configure the agent
    logger.info("Configuring agent deployment...")
    logger.info(f"  Agent name: {agent_name}")
    logger.info(f"  Entrypoint: {entrypoint}")
    logger.info(f"  Requirements: {requirements_file}")
    logger.info(f"  Region: {region}")

    configure_response = agentcore_runtime.configure(
        entrypoint=entrypoint,
        auto_create_execution_role=True,
        auto_create_ecr=True,
        requirements_file=requirements_file,
        region=region,
        agent_name=agent_name
    )

    logger.info("Agent configuration completed")
    logger.info(f"Configuration response: {json.dumps(configure_response, indent=2, default=str)}")

    # Launch the agent
    logger.info("Launching agent to AgentCore Runtime...")
    logger.info("This will:")
    logger.info("  1. Build Docker container with your agent code")
    logger.info("  2. Push container to Amazon ECR")
    logger.info("  3. Deploy to AgentCore Runtime")
    logger.info("  This may take several minutes...")

    launch_result = agentcore_runtime.launch()

    logger.info("Agent launched successfully!")

    # Extract deployment information
    agent_id = launch_result.agent_id
    agent_arn = launch_result.agent_arn
    ecr_uri = launch_result.ecr_uri

    logger.info(f"Agent ID: {agent_id}")
    logger.info(f"Agent ARN: {agent_arn}")
    logger.info(f"ECR URI: {ecr_uri}")

    # Save deployment info
    deployment_info = {
        "agent_id": agent_id,
        "agent_arn": agent_arn,
        "ecr_uri": ecr_uri,
        "region": region,
        "agent_name": agent_name
    }

    return deployment_info


def _wait_for_agent_ready(
    agent_id: str,
    region: str
) -> None:
    """
    Wait for agent to be ready.

    Args:
        agent_id: Agent ID to check
        region: AWS region
    """
    from bedrock_agentcore_starter_toolkit import Runtime
    import time

    logger.info("Checking agent status...")

    agentcore_runtime = Runtime()

    max_attempts = 60
    attempt = 0

    end_status = ['READY', 'CREATE_FAILED', 'DELETE_FAILED', 'UPDATE_FAILED']

    while attempt < max_attempts:
        try:
            status_response = agentcore_runtime.status()
            status = status_response.endpoint.get('status', 'UNKNOWN')

            logger.info(f"Agent status: {status}")

            if status in end_status:
                if status == 'READY':
                    logger.info("Agent is ready!")
                    return
                else:
                    logger.error(f"Agent deployment failed with status: {status}")
                    sys.exit(1)

            time.sleep(10)
            attempt += 1

        except Exception as e:
            logger.warning(f"Error checking status: {e}")
            time.sleep(10)
            attempt += 1

    logger.error("Timeout waiting for agent to be ready")
    sys.exit(1)


def _save_deployment_info(
    deployment_info: dict,
    script_dir: Path
) -> None:
    """
    Save deployment information to files.

    Args:
        deployment_info: Deployment information dictionary
        script_dir: Directory to save files
    """
    # Save agent ID
    agent_id_file = script_dir / ".agent_id"
    agent_id_file.write_text(deployment_info["agent_id"])
    logger.info(f"Agent ID saved to: {agent_id_file}")

    # Save environment configuration
    env_file = script_dir / ".env"
    env_content = f"""# AgentCore Runtime Agent Configuration
export AGENTCORE_AGENT_ID={deployment_info["agent_id"]}
export AGENTCORE_AGENT_ARN={deployment_info["agent_arn"]}
export AWS_REGION={deployment_info["region"]}

# OTEL Configuration
export SERVICE_NAME=agentcore-observability-demo
export SERVICE_VERSION=1.0.0
export DEPLOYMENT_ENVIRONMENT=demo

# Braintrust Configuration (optional)
# export BRAINTRUST_API_KEY=your_api_key_here
"""
    env_file.write_text(env_content)
    logger.info(f"Environment configuration saved to: {env_file}")

    # Save deployment metadata
    metadata_file = script_dir / ".deployment_metadata.json"
    metadata_file.write_text(json.dumps(deployment_info, indent=2))
    logger.info(f"Deployment metadata saved to: {metadata_file}")


def main():
    """Main deployment function."""
    parser = argparse.ArgumentParser(
        description="Deploy Strands agent to Amazon Bedrock AgentCore Runtime",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
    # Deploy with defaults
    uv run python deploy_agent.py

    # Deploy to specific region
    uv run python deploy_agent.py --region us-west-2

    # Deploy with custom agent name
    uv run python deploy_agent.py --name MyCustomAgent
"""
    )

    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", "us-east-1"),
        help="AWS region for deployment (default: us-east-1)"
    )

    parser.add_argument(
        "--name",
        default="weather-time-observability-agent",
        help="Agent name (default: weather-time-observability-agent)"
    )

    parser.add_argument(
        "--entrypoint",
        default="agent/weather_time_agent.py",
        help="Path to agent entrypoint (default: agent/weather_time_agent.py)"
    )

    parser.add_argument(
        "--requirements",
        default="requirements.txt",
        help="Path to requirements file (default: requirements.txt)"
    )

    args = parser.parse_args()

    # Get script directory
    script_dir = Path(__file__).parent
    parent_dir = script_dir.parent

    logger.info("=" * 60)
    logger.info("AGENTCORE AGENT DEPLOYMENT")
    logger.info("=" * 60)
    logger.info(f"Agent name: {args.name}")
    logger.info(f"Region: {args.region}")
    logger.info(f"Entrypoint: {args.entrypoint}")
    logger.info(f"Requirements: {args.requirements}")
    logger.info("=" * 60)

    # Validate environment
    _validate_environment()

    # Change to parent directory for deployment
    os.chdir(parent_dir)
    logger.info(f"Working directory: {parent_dir}")

    # Deploy agent
    deployment_info = _deploy_agent(
        agent_name=args.name,
        region=args.region,
        entrypoint=args.entrypoint,
        requirements_file=args.requirements,
        script_dir=script_dir
    )

    # Wait for agent to be ready
    _wait_for_agent_ready(
        agent_id=deployment_info["agent_id"],
        region=args.region
    )

    # Save deployment information
    _save_deployment_info(deployment_info, script_dir)

    # Print success message
    logger.info("")
    logger.info("=" * 60)
    logger.info("DEPLOYMENT COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Agent ID: {deployment_info['agent_id']}")
    logger.info(f"Agent ARN: {deployment_info['agent_arn']}")
    logger.info(f"Region: {args.region}")
    logger.info("")
    logger.info("Next Steps:")
    logger.info(f"1. Source environment: source {script_dir}/.env")
    logger.info("2. Set up CloudWatch: ./setup_cloudwatch.sh")
    logger.info("3. Run demo: uv run python simple_observability.py --scenario success")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
