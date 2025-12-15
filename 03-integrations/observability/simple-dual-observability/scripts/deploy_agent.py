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
        import boto3  # noqa: F401
        from bedrock_agentcore_starter_toolkit import Runtime  # noqa: F401

        logger.info("Required packages found: boto3, bedrock-agentcore-starter-toolkit")

    except ImportError as e:
        logger.error(f"Missing required package: {e}")
        logger.error("Please install: pip install -r requirements.txt")
        sys.exit(1)

    # Validate AWS credentials by making an API call
    # boto3 automatically figures out credentials from various sources:
    # - Environment variables
    # - IAM role (EC2/Cloud9/ECS)
    # - Credentials file
    # - Config file
    # We don't care which - just validate it works
    try:
        sts = boto3.client("sts")
        identity = sts.get_caller_identity()
        logger.info(f"AWS Account ID: {identity['Account']}")
        logger.info(f"AWS Identity ARN: {identity['Arn']}")

    except Exception as e:
        logger.error(f"Failed to validate AWS credentials: {e}")
        logger.error("")
        logger.error("Ensure AWS credentials are configured.")
        logger.error("Test with: aws sts get-caller-identity")
        sys.exit(1)


def _deploy_agent(
    agent_name: str,
    region: str,
    entrypoint: str,
    requirements_file: str,
    script_dir: Path,
    braintrust_api_key: str = None,
    braintrust_project_id: str = None,
    auto_update_on_conflict: bool = False,
) -> dict:
    """
    Deploy agent to AgentCore Runtime.

    Args:
        agent_name: Name for the deployed agent
        region: AWS region for deployment
        entrypoint: Path to agent entrypoint file
        requirements_file: Path to requirements.txt
        script_dir: Script directory for saving outputs
        braintrust_api_key: Optional Braintrust API key for observability
        braintrust_project_id: Optional Braintrust project ID
        auto_update_on_conflict: Whether to automatically update existing agent if it already exists

    Returns:
        Dictionary with deployment results
    """
    from bedrock_agentcore_starter_toolkit import Runtime

    logger.info("Initializing AgentCore Runtime deployment...")

    agentcore_runtime = Runtime()

    # Determine observability configuration
    enable_braintrust = bool(braintrust_api_key and braintrust_project_id)

    # Configure the agent
    logger.info("Configuring agent deployment...")
    logger.info(f"  Agent name: {agent_name}")
    logger.info(f"  Entrypoint: {entrypoint}")
    logger.info(f"  Requirements: {requirements_file}")
    logger.info(f"  Region: {region}")
    logger.info(
        f"  Braintrust observability: {'Enabled' if enable_braintrust else 'Disabled (CloudWatch only)'}"
    )

    configure_kwargs = {
        "entrypoint": entrypoint,
        "auto_create_execution_role": True,
        "auto_create_ecr": True,
        "requirements_file": requirements_file,
        "region": region,
        "agent_name": agent_name,
    }

    # Disable AgentCore's built-in OTEL if using Braintrust
    # When Braintrust is enabled, Strands telemetry handles OTEL instrumentation
    if enable_braintrust:
        configure_kwargs["disable_otel"] = True
        logger.info("  Disabling AgentCore OTEL (using Braintrust)")
    else:
        logger.info("  AgentCore OTEL instrumentation: Enabled (CloudWatch only)")

    configure_response = agentcore_runtime.configure(**configure_kwargs)

    logger.info("Agent configuration completed")
    logger.info(f"Configuration response: {json.dumps(configure_response, indent=2, default=str)}")

    # Launch the agent
    logger.info("Launching agent to AgentCore Runtime...")
    logger.info("This will:")
    logger.info("  1. Build Docker container with your agent code")
    logger.info("  2. Push container to Amazon ECR")
    logger.info("  3. Deploy to AgentCore Runtime")
    logger.info("  This may take several minutes...")

    try:
        launch_kwargs = {
            "auto_update_on_conflict": auto_update_on_conflict,
        }

        # Add Braintrust environment variables if enabled
        if enable_braintrust:
            logger.info("Configuring Braintrust OTEL export...")
            launch_kwargs["env_vars"] = {
                "OTEL_EXPORTER_OTLP_ENDPOINT": "https://api.braintrust.dev/otel",
                "OTEL_EXPORTER_OTLP_HEADERS": f"authorization=Bearer {braintrust_api_key},x-bt-parent=project_id:{braintrust_project_id}",
                "BRAINTRUST_API_KEY": braintrust_api_key,
                "BRAINTRUST_PROJECT_ID": braintrust_project_id,
            }

        launch_result = agentcore_runtime.launch(**launch_kwargs)
    except Exception as e:
        error_msg = str(e)

        # Check for common IAM permission errors
        if "codebuild:CreateProject" in error_msg or "AccessDeniedException" in error_msg:
            logger.error("=" * 70)
            logger.error("IAM PERMISSION ERROR")
            logger.error("=" * 70)
            logger.error("The deployment requires additional IAM permissions.")
            logger.error("")
            logger.error("Missing permission: codebuild:CreateProject")
            logger.error("")
            logger.error("Solution:")
            logger.error("  1. Attach the policy from: docs/iam-policy-deployment.json")
            logger.error("")
            logger.error("  Using AWS CLI:")
            logger.error("     aws iam put-role-policy \\")
            logger.error("       --role-name YOUR_ROLE_NAME \\")
            logger.error("       --policy-name BedrockAgentCoreDeployment \\")
            logger.error("       --policy-document file://docs/iam-policy-deployment.json")
            logger.error("")
            logger.error("  Or see README for complete IAM setup instructions.")
            logger.error("=" * 70)

        # Re-raise the exception with more context
        raise RuntimeError(f"Deployment failed: {error_msg}") from e

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
        "agent_name": agent_name,
        "braintrust_enabled": enable_braintrust,
    }

    return deployment_info


def _wait_for_agent_ready(agent_id: str, region: str) -> None:
    """
    Wait for agent to be ready.

    The launch() method already waits for the agent to be ready,
    so this is just a placeholder for now.

    Args:
        agent_id: Agent ID to check
        region: AWS region
    """
    logger.info("Agent deployment completed successfully")
    logger.info("The launch() method already verified the agent is ready")
    # No additional status check needed - launch() already handles this
    return


def _save_deployment_info(deployment_info: dict, script_dir: Path) -> None:
    """
    Save deployment information to .deployment_metadata.json.

    Args:
        deployment_info: Deployment information dictionary
        script_dir: Directory to save files
    """
    # Save deployment metadata as single source of truth
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
    # Deploy with CloudWatch observability only (default)
    uv run python deploy_agent.py

    # Deploy with Braintrust observability
    uv run python deploy_agent.py \\
        --braintrust-api-key YOUR_KEY \\
        --braintrust-project-id YOUR_PROJECT_ID

    # Deploy to specific region
    uv run python deploy_agent.py --region us-west-2

    # Deploy with custom agent name
    uv run python deploy_agent.py --name MyCustomAgent

    # Update existing agent (auto-update on conflict)
    uv run python deploy_agent.py --auto-update-on-conflict

Environment variables:
    BRAINTRUST_API_KEY: Braintrust API key (alternative to --braintrust-api-key)
    BRAINTRUST_PROJECT_ID: Braintrust project ID (alternative to --braintrust-project-id)
""",
    )

    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", "us-east-1"),
        help="AWS region for deployment (default: us-east-1)",
    )

    parser.add_argument(
        "--name",
        default="weather_time_observability_agent",
        help="Agent name (default: weather_time_observability_agent)",
    )

    parser.add_argument(
        "--entrypoint",
        default="agent/weather_time_agent.py",
        help="Path to agent entrypoint (default: agent/weather_time_agent.py)",
    )

    parser.add_argument(
        "--requirements",
        default="requirements.txt",
        help="Path to requirements file (default: requirements.txt)",
    )

    parser.add_argument(
        "--braintrust-api-key",
        default=os.environ.get("BRAINTRUST_API_KEY"),
        help="Braintrust API key for observability (optional, can use BRAINTRUST_API_KEY env var)",
    )

    parser.add_argument(
        "--braintrust-project-id",
        default=os.environ.get("BRAINTRUST_PROJECT_ID"),
        help="Braintrust project ID (optional, can use BRAINTRUST_PROJECT_ID env var)",
    )

    parser.add_argument(
        "--auto-update-on-conflict",
        action="store_true",
        help="Automatically update existing agent if it already exists (default: false)",
    )

    args = parser.parse_args()

    # Get script directory
    script_dir = Path(__file__).parent
    parent_dir = script_dir.parent

    # Validate Braintrust configuration
    # Only consider credentials valid if they are non-empty and not placeholder values
    braintrust_api_key_valid = (
        args.braintrust_api_key
        and args.braintrust_api_key.strip()
        and "your-" not in args.braintrust_api_key.lower()
    )
    braintrust_project_valid = (
        args.braintrust_project_id
        and args.braintrust_project_id.strip()
        and "your-" not in args.braintrust_project_id.lower()
    )

    enable_braintrust = braintrust_api_key_valid and braintrust_project_valid

    # If one credential is provided but not both, warn and disable Braintrust
    if (braintrust_api_key_valid or braintrust_project_valid) and not (
        braintrust_api_key_valid and braintrust_project_valid
    ):
        logger.warning(
            "Incomplete Braintrust credentials - disabling Braintrust observability (using CloudWatch only)"
        )
        enable_braintrust = False

    logger.info("=" * 60)
    logger.info("AGENTCORE AGENT DEPLOYMENT")
    logger.info("=" * 60)
    logger.info(f"Agent name: {args.name}")
    logger.info(f"Region: {args.region}")
    logger.info(f"Entrypoint: {args.entrypoint}")
    logger.info(f"Requirements: {args.requirements}")
    logger.info(
        f"Braintrust observability: {'Enabled' if enable_braintrust else 'Disabled (CloudWatch only)'}"
    )
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
        script_dir=script_dir,
        braintrust_api_key=args.braintrust_api_key,
        braintrust_project_id=args.braintrust_project_id,
        auto_update_on_conflict=args.auto_update_on_conflict,
    )

    # Wait for agent to be ready
    _wait_for_agent_ready(agent_id=deployment_info["agent_id"], region=args.region)

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
    logger.info("1. Test the agent: ./scripts/tests/test_agent.py --test weather")
    logger.info("2. Check logs: ./scripts/check_logs.sh --time 30m")
    logger.info("3. Run observability demo: uv run python simple_observability.py --scenario all")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
