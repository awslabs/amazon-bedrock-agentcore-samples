#!/usr/bin/env python3
"""
Test the deployed AgentCore Runtime agent.

This script invokes the agent with test prompts and displays responses.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError


# Configure logging with basicConfig
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


# Test prompts for different tools
TEST_PROMPTS: Dict[str, str] = {
    "weather": "What's the weather like in Seattle?",
    "time": "What time is it in Tokyo?",
    "calculator": "What is 25 times 8?",
    "combined": "What's the weather in Paris and what time is it there?",
}


def _load_agent_metadata(
    script_dir: Path
) -> Dict[str, Any]:
    """Load agent metadata from deployment files."""
    metadata_file = script_dir / ".deployment_metadata.json"
    agent_id_file = script_dir / ".agent_id"

    if metadata_file.exists():
        with open(metadata_file) as f:
            return json.load(f)
    elif agent_id_file.exists():
        agent_id = agent_id_file.read_text().strip()
        return {"agent_id": agent_id}
    else:
        raise FileNotFoundError(
            "No deployment metadata found. "
            "Deploy the agent first with: ./deploy_agent.sh"
        )


def _invoke_agent(
    agent_arn: str,
    prompt: str,
    region: str,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Invoke the agent with a prompt.

    Args:
        agent_arn: The agent ARN
        prompt: The prompt to send
        region: AWS region
        session_id: Optional session ID for conversation context

    Returns:
        Response from the agent
    """
    import uuid

    client = boto3.client("bedrock-agentcore", region_name=region)

    # Generate session ID if not provided
    if not session_id:
        session_id = str(uuid.uuid4())

    try:
        # Prepare payload
        payload = json.dumps({"prompt": prompt})

        response = client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            runtimeSessionId=session_id,
            payload=payload
        )

        # Parse response - handle StreamingBody
        agent_response = None
        if "response" in response:
            response_body = response["response"]

            # Handle StreamingBody
            if hasattr(response_body, "read"):
                raw_data = response_body.read()
                if isinstance(raw_data, bytes):
                    agent_response = raw_data.decode("utf-8")
                else:
                    agent_response = str(raw_data)
            elif isinstance(response_body, str):
                agent_response = response_body

        return {
            "response": agent_response,
            "session_id": session_id,
            "raw_response": response
        }

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]

        if error_code == "ResourceNotFoundException":
            raise RuntimeError(
                f"Agent not found: {agent_arn}\n"
                f"Make sure the agent is deployed and the ARN is correct."
            ) from e
        elif error_code == "AccessDeniedException":
            raise RuntimeError(
                f"Access denied when invoking agent.\n"
                f"Make sure your IAM role has bedrock-agentcore:InvokeAgentRuntime permission."
            ) from e
        else:
            raise RuntimeError(f"Failed to invoke agent: {error_msg}") from e


def _display_response(
    response: Dict[str, Any],
    show_full: bool = False
) -> None:
    """Display the agent response."""
    logger.info("=" * 70)
    logger.info("AGENT RESPONSE")
    logger.info("=" * 70)

    # Extract response text
    if "response" in response and response["response"]:
        logger.info("\n%s\n", response["response"])
    else:
        logger.info("Raw response:\n%s", json.dumps(response, indent=2, default=str))

    # Show session ID
    if "session_id" in response:
        logger.info("Session ID: %s", response["session_id"])

    # Show full raw response if requested
    if show_full and "raw_response" in response:
        logger.info("\nFull Raw Response:")
        logger.info(json.dumps(response["raw_response"], indent=2, default=str))

    logger.info("=" * 70)


def _run_interactive_mode(
    agent_arn: str,
    region: str
) -> None:
    """Run interactive testing mode."""
    logger.info("=" * 70)
    logger.info("INTERACTIVE MODE")
    logger.info("=" * 70)
    logger.info("Type your prompts and press Enter.")
    logger.info("Type 'quit' or 'exit' to stop.")
    logger.info("Type 'test' to see available test prompts.")
    logger.info("=" * 70)
    logger.info("")

    while True:
        try:
            prompt = input("\n🤖 Prompt: ").strip()

            if not prompt:
                continue

            if prompt.lower() in ["quit", "exit", "q"]:
                logger.info("Exiting interactive mode.")
                break

            if prompt.lower() == "test":
                logger.info("\nAvailable test prompts:")
                for name, test_prompt in TEST_PROMPTS.items():
                    logger.info("  %s: %s", name, test_prompt)
                continue

            logger.info("\nInvoking agent...")
            response = _invoke_agent(agent_arn, prompt, region)
            _display_response(response)

        except KeyboardInterrupt:
            logger.info("\n\nExiting interactive mode.")
            break
        except Exception as e:
            logger.error("Error: %s", str(e))


def main() -> None:
    """Main entry point for agent testing."""
    parser = argparse.ArgumentParser(
        description="Test the deployed AgentCore Runtime agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
    # Run a specific test prompt
    uv run python -m scripts.test_agent --test weather

    # Run a custom prompt
    uv run python -m scripts.test_agent --prompt "What is 100 divided by 4?"

    # Interactive mode
    uv run python -m scripts.test_agent --interactive

    # Show full response including traces
    uv run python -m scripts.test_agent --test combined --full

Available test prompts:
    weather   - Test weather tool
    time      - Test time tool
    calculator - Test calculator tool
    combined  - Test multiple tools
""",
    )

    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1)",
    )

    parser.add_argument(
        "--agent-id",
        help="Agent ID (if not provided, reads from deployment metadata)",
    )

    parser.add_argument(
        "--test",
        choices=list(TEST_PROMPTS.keys()),
        help="Run a predefined test prompt",
    )

    parser.add_argument(
        "--prompt",
        help="Custom prompt to test",
    )

    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Run in interactive mode",
    )

    parser.add_argument(
        "--full",
        action="store_true",
        help="Show full response including traces",
    )

    args = parser.parse_args()

    # Get script directory
    script_dir = Path(__file__).parent

    # Load agent metadata
    try:
        metadata = _load_agent_metadata(script_dir)
        agent_arn = args.agent_id or metadata.get("agent_arn")
        region = args.region or metadata.get("region", "us-east-1")
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    if not agent_arn:
        logger.error("No agent ARN found. Deploy the agent first.")
        sys.exit(1)

    logger.info("Testing agent: %s", agent_arn)
    logger.info("Region: %s", region)
    logger.info("")

    # Run in interactive mode
    if args.interactive:
        _run_interactive_mode(agent_arn, region)
        return

    # Determine which prompt to use
    if args.test:
        prompt = TEST_PROMPTS[args.test]
        logger.info("Running test: %s", args.test)
    elif args.prompt:
        prompt = args.prompt
        logger.info("Running custom prompt")
    else:
        logger.error("Must specify --test, --prompt, or --interactive")
        parser.print_help()
        sys.exit(1)

    logger.info("Prompt: %s", prompt)
    logger.info("")

    # Invoke the agent
    try:
        response = _invoke_agent(agent_arn, prompt, region)
        _display_response(response, show_full=args.full)
    except Exception as e:
        logger.error("Failed to test agent: %s", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
