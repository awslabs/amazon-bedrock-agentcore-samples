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
    # Note: boto3 automatically handles multiple credential sources:
    # 1. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    # 2. IAM role (EC2 instance profile, Cloud9, ECS task role)
    # 3. Credentials file (~/.aws/credentials)
    # 4. Config file (~/.aws/config)

    # Validate AWS credentials by making an actual API call
    # boto3 will automatically use credentials from (in order):
    # 1. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    # 2. IAM role (EC2 instance profile, Cloud9, ECS task role)
    # 3. Credentials file (~/.aws/credentials)
    # 4. Config file (~/.aws/config)
    #
    # Note: boto3 may log warnings about missing config files, but this is fine.
    # As long as credentials can be obtained from another source (like IAM role),
    # the validation will succeed.

    try:
        # Suppress config file warnings by pointing to /dev/null
        # This allows boto3 to skip config file and use IAM role directly
        import os
        if not os.path.exists(os.path.expanduser('~/.aws/config')):
            os.environ['AWS_CONFIG_FILE'] = '/dev/null'

        # Create session - boto3 will try all credential sources automatically
        session = boto3.Session()
        sts = session.client('sts')

        # Validate credentials work by making an API call
        identity = sts.get_caller_identity()
        logger.info(f"AWS Account ID: {identity['Account']}")
        logger.info(f"AWS User/Role ARN: {identity['Arn']}")

        # Determine credential source for informational purposes
        try:
            credentials = session.get_credentials()
            if credentials:
                cred_method = credentials.method
                if cred_method == 'iam-role':
                    logger.info("Credential source: IAM role (EC2/Cloud9 instance profile)")
                elif cred_method == 'assume-role':
                    logger.info("Credential source: Assumed role")
                elif cred_method == 'env':
                    logger.info("Credential source: Environment variables")
                elif cred_method == 'shared-credentials-file':
                    logger.info("Credential source: ~/.aws/credentials")
                else:
                    logger.info(f"Credential source: {cred_method}")
        except Exception:
            # Credential method detection failed, but that's okay - credentials work
            pass

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to validate AWS credentials: {error_msg}")
        logger.error("")
        logger.error("Please configure AWS credentials using one of:")
        logger.error("  1. IAM role (if running on EC2/Cloud9) - instance must have role attached")
        logger.error("  2. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)")
        logger.error("  3. AWS CLI: aws configure")
        logger.error("  4. Credentials file: ~/.aws/credentials")
        logger.error("")
        logger.error("To verify your credentials work, try: aws sts get-caller-identity")
        sys.exit(1)


def _deploy_agent(
    agent_name: str,
    region: str,
    entrypoint: str,
    requirements_file: str,
    script_dir: Path,
    braintrust_api_key: str = None,
    braintrust_project_id: str = None
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

    Returns:
        Dictionary with deployment results
    """
    from bedrock_agentcore_starter_toolkit import Runtime
    from boto3.session import Session

    logger.info("Initializing AgentCore Runtime deployment...")

    boto_session = Session(region_name=region)
    agentcore_runtime = Runtime()

    # Determine observability configuration
    enable_braintrust = bool(braintrust_api_key and braintrust_project_id)

    # Configure the agent
    logger.info("Configuring agent deployment...")
    logger.info(f"  Agent name: {agent_name}")
    logger.info(f"  Entrypoint: {entrypoint}")
    logger.info(f"  Requirements: {requirements_file}")
    logger.info(f"  Region: {region}")
    logger.info(f"  Braintrust observability: {'Enabled' if enable_braintrust else 'Disabled (CloudWatch only)'}")

    configure_kwargs = {
        "entrypoint": entrypoint,
        "auto_create_execution_role": True,
        "auto_create_ecr": True,
        "requirements_file": requirements_file,
        "region": region,
        "agent_name": agent_name
    }

    # Disable AgentCore's built-in OTEL if using Braintrust
    if enable_braintrust:
        configure_kwargs["disable_otel"] = True
        logger.info("  Disabling AgentCore OTEL (using Braintrust)")

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
        launch_kwargs = {}

        # Add Braintrust environment variables if enabled
        if enable_braintrust:
            logger.info("Configuring Braintrust OTEL export...")
            launch_kwargs["env_vars"] = {
                "OTEL_EXPORTER_OTLP_ENDPOINT": "https://api.braintrust.dev/otel",
                "OTEL_EXPORTER_OTLP_HEADERS": f"Authorization=Bearer {braintrust_api_key}, x-bt-parent=project_id:{braintrust_project_id}",
                "DISABLE_ADOT_OBSERVABILITY": "true",
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
        "braintrust_enabled": enable_braintrust
    }

    return deployment_info


def _wait_for_agent_ready(
    agent_id: str,
    region: str
) -> None:
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


def _save_deployment_info(
    deployment_info: dict,
    script_dir: Path
) -> None:
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

Environment variables:
    BRAINTRUST_API_KEY: Braintrust API key (alternative to --braintrust-api-key)
    BRAINTRUST_PROJECT_ID: Braintrust project ID (alternative to --braintrust-project-id)
"""
    )

    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", "us-east-1"),
        help="AWS region for deployment (default: us-east-1)"
    )

    parser.add_argument(
        "--name",
        default="weather_time_observability_agent",
        help="Agent name (default: weather_time_observability_agent)"
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

    parser.add_argument(
        "--braintrust-api-key",
        default=os.environ.get("BRAINTRUST_API_KEY"),
        help="Braintrust API key for observability (optional, can use BRAINTRUST_API_KEY env var)"
    )

    parser.add_argument(
        "--braintrust-project-id",
        default=os.environ.get("BRAINTRUST_PROJECT_ID"),
        help="Braintrust project ID (optional, can use BRAINTRUST_PROJECT_ID env var)"
    )

    args = parser.parse_args()

    # Get script directory
    script_dir = Path(__file__).parent
    parent_dir = script_dir.parent

    # Validate Braintrust configuration
    enable_braintrust = bool(args.braintrust_api_key and args.braintrust_project_id)
    if args.braintrust_api_key and not args.braintrust_project_id:
        logger.error("Both --braintrust-api-key and --braintrust-project-id are required for Braintrust observability")
        sys.exit(1)
    if args.braintrust_project_id and not args.braintrust_api_key:
        logger.error("Both --braintrust-api-key and --braintrust-project-id are required for Braintrust observability")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("AGENTCORE AGENT DEPLOYMENT")
    logger.info("=" * 60)
    logger.info(f"Agent name: {args.name}")
    logger.info(f"Region: {args.region}")
    logger.info(f"Entrypoint: {args.entrypoint}")
    logger.info(f"Requirements: {args.requirements}")
    logger.info(f"Braintrust observability: {'Enabled' if enable_braintrust else 'Disabled (CloudWatch only)'}")
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
        braintrust_project_id=args.braintrust_project_id
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
    logger.info("1. Test the agent: ./test_agent.sh --test weather")
    logger.info("2. Check logs: ./check_logs.sh --time 30m")
    logger.info("3. Run observability demo: uv run python simple_observability.py --scenario success")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
