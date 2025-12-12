"""
Simple AgentCore Observability Demo with Dual Platform Support.

This demo shows how Amazon Bedrock AgentCore automatic OpenTelemetry instrumentation
works with both AWS-native CloudWatch and partner platform Braintrust.

Architecture:
    Local Script (this file)
        ↓ boto3 API call
    AgentCore Runtime (managed service)
        ↓ agent execution with automatic OTEL
    MCP Tools (weather, time, calculator)
        ↓ traces exported
    CloudWatch (GenAI Observability or APM) + Braintrust

Agent runs in AgentCore Runtime - a fully managed service for hosting agents.
"""

import argparse
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


# Constants
DEFAULT_REGION: str = "us-east-1"
DEFAULT_TIMEOUT: int = 300


def _get_env_var(var_name: str, default: str | None = None, required: bool = False) -> str | None:
    """
    Get environment variable with optional default and required check.

    Args:
        var_name: Name of environment variable
        default: Default value if not found
        required: Raise error if not found and no default

    Returns:
        Environment variable value or default

    Raises:
        ValueError: If required and not found
    """
    value = os.getenv(var_name, default)

    if required and value is None:
        raise ValueError(
            f"Required environment variable '{var_name}' not found. "
            f"Set it via environment or command-line argument."
        )

    return value


def _load_deployment_metadata() -> dict[str, Any] | None:
    """
    Load agent deployment metadata from .deployment_metadata.json.

    Returns:
        Deployment metadata dictionary or None if file doesn't exist
    """
    metadata_file = Path("scripts/.deployment_metadata.json")

    if metadata_file.exists():
        try:
            with open(metadata_file) as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load deployment metadata: {e}")
            return None
    return None


def _is_braintrust_enabled(metadata: dict[str, Any] | None) -> bool:
    """
    Check if Braintrust observability is enabled for the deployed agent.

    Args:
        metadata: Deployment metadata dictionary

    Returns:
        True if Braintrust is enabled, False otherwise
    """
    if metadata is None:
        return False

    return metadata.get("braintrust_enabled", False)


def _create_bedrock_client(region: str) -> boto3.client:
    """
    Create Amazon Bedrock AgentCore client.

    Args:
        region: AWS region

    Returns:
        Configured boto3 client
    """
    try:
        client = boto3.client("bedrock-agentcore", region_name=region)
        logger.info(f"Created Bedrock AgentCore client for region: {region}")
        return client

    except Exception as e:
        logger.exception(f"Failed to create Bedrock client: {e}")
        raise


def _generate_session_id() -> str:
    """
    Generate unique session ID for trace correlation.

    Session ID must be at least 33 characters for bedrock-agentcore API.

    Returns:
        UUID-based session ID (36 characters)
    """
    session_id = str(uuid.uuid4())
    logger.debug(f"Generated session ID: {session_id}")
    return session_id


def _invoke_agent(
    client: boto3.client, agent_arn: str, query: str, session_id: str, enable_trace: bool = True
) -> dict[str, Any]:
    """
    Invoke AgentCore Runtime agent with automatic OTEL instrumentation.

    The agent runs in AgentCore Runtime (managed service) with automatic
    OpenTelemetry tracing. Traces are exported to both CloudWatch (via GenAI
    Observability or APM) and Braintrust (if configured).

    Args:
        client: Bedrock AgentCore client
        agent_arn: ARN of deployed agent runtime
        query: User query
        session_id: Session ID for correlation
        enable_trace: Enable detailed tracing (not used in current API)

    Returns:
        Agent response with output and metadata

    Raises:
        ClientError: If agent invocation fails
    """
    logger.info(f"Invoking agent: {agent_arn}")
    logger.info(f"Query: {query}")
    logger.info(f"Session ID: {session_id}")

    start_time = time.time()

    try:
        # Prepare payload
        payload = json.dumps({"prompt": query})

        response = client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn, runtimeSessionId=session_id, payload=payload
        )

        elapsed_time = time.time() - start_time
        logger.info(f"Agent response received in {elapsed_time:.2f}s")

        # Parse response - handle StreamingBody
        agent_response = None
        if "response" in response:
            response_body = response["response"]

            if hasattr(response_body, "read"):
                raw_data = response_body.read()
                if isinstance(raw_data, bytes):
                    agent_response = raw_data.decode("utf-8")
                else:
                    agent_response = str(raw_data)
            elif isinstance(response_body, str):
                agent_response = response_body

        return {
            "output": agent_response or "",
            "trace_id": response.get("traceId", ""),
            "session_id": session_id,
            "elapsed_time": elapsed_time,
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))

        logger.error(f"Agent invocation failed: {error_code} - {error_message}")
        raise

    except Exception as e:
        logger.exception(f"Unexpected error during agent invocation: {e}")
        raise


def _print_result(result: dict[str, Any], scenario_name: str) -> None:
    """
    Print agent invocation result in formatted output.

    Args:
        result: Agent response dictionary
        scenario_name: Name of scenario for context
    """
    print("\n" + "=" * 80)
    print(f"SCENARIO: {scenario_name}")
    print("=" * 80)
    print(f"\nOutput:\n{result['output']}\n")
    print(f"Trace ID: {result['trace_id']}")
    print(f"Session ID: {result['session_id']}")
    print(f"Elapsed Time: {result['elapsed_time']:.2f}s")
    print("\n" + "=" * 80 + "\n")


def _print_observability_links(region: str, trace_id: str) -> None:
    """
    Print links to observability platforms for trace inspection.

    Args:
        region: AWS region
        trace_id: Trace ID to look up
    """
    print("\nView: VIEW TRACES IN:")
    print("\n1. CloudWatch GenAI Observability (Recommended):")
    print(f"   https://console.aws.amazon.com/cloudwatch/home?region={region}#cloudwatch-home:")
    print("   Navigate to GenAI Observability > Bedrock AgentCore")
    print("   View metrics under Agents, traces under Sessions > Traces")
    print("   Or use APM > Servers, select agent to monitor")

    print("\n2. Braintrust Dashboard:")
    print("   https://www.braintrust.dev/app")

    print("\n3. CloudWatch Logs:")
    print(f"   https://console.aws.amazon.com/cloudwatch/home?region={region}#logsV2:log-groups")
    print("   Filter by session ID or trace ID\n")


def scenario_success(
    client: boto3.client, agent_arn: str, region: str, braintrust_enabled: bool = False
) -> None:
    """
    Scenario 1: Successful multi-tool query.

    Demonstrates:
    - Agent selecting multiple tools (weather + time)
    - Successful tool execution
    - Response aggregation
    - Clean trace with all spans

    Expected trace:
    - Agent invocation span
    - Tool selection span
    - Tool execution spans (weather, time)
    - Response formatting span

    Args:
        client: Bedrock AgentCore client
        agent_arn: ARN of deployed agent
        region: AWS region
        braintrust_enabled: Whether Braintrust observability is enabled
    """
    logger.info("Starting Scenario 1: Successful Multi-Tool Query")

    session_id = _generate_session_id()
    query = "What's the weather in Seattle and what time is it there?"

    result = _invoke_agent(client=client, agent_arn=agent_arn, query=query, session_id=session_id)

    _print_result(result, "Scenario 1: Successful Multi-Tool Query")
    _print_observability_links(region, result["trace_id"])

    print("✓ Expected in CloudWatch GenAI Observability:")
    print("   - Agent invocation span")
    print("   - Tool selection span (reasoning)")
    print("   - Tool execution spans: weather tool, time tool")
    print("   - Total latency: ~1-2 seconds")

    if braintrust_enabled:
        print("\n✓ Expected in Braintrust:")
        print("   - LLM call details (model, tokens, cost)")
        print("   - Tool execution timeline")
        print("   - Latency breakdown by component")
        print("   - View at: https://www.braintrust.dev/app")
    else:
        print("\n⚠ Braintrust Integration:")
        print("   - Not configured for this deployment")
        print("   - To enable: Redeploy with --braintrust-api-key and --braintrust-project-id")
        print("   - See README.md for setup instructions")


def scenario_error(
    client: boto3.client, agent_arn: str, region: str, braintrust_enabled: bool = False
) -> None:
    """
    Scenario 2: Error handling demonstration.

    Demonstrates:
    - Agent correctly selecting calculator tool
    - Tool returning error (invalid input)
    - Error propagation through spans
    - Graceful error handling

    Expected trace:
    - Agent invocation span
    - Tool selection span
    - Tool execution span (calculator) - ERROR
    - Error details in span attributes

    Args:
        client: Bedrock AgentCore client
        agent_arn: ARN of deployed agent
        region: AWS region
        braintrust_enabled: Whether Braintrust observability is enabled
    """
    logger.info("Starting Scenario 2: Error Handling")

    session_id = _generate_session_id()
    query = "Calculate the factorial of -5"

    result = _invoke_agent(client=client, agent_arn=agent_arn, query=query, session_id=session_id)

    _print_result(result, "Scenario 2: Error Handling")
    _print_observability_links(region, result["trace_id"])

    print("✓ Expected in CloudWatch GenAI Observability:")
    print("   - Error span highlighted in red")
    print("   - Error status code and message in attributes")
    print("   - Calculator tool span shows failure")
    print("   - Agent handles error gracefully")

    if braintrust_enabled:
        print("\n✓ Expected in Braintrust:")
        print("   - Error flagged with details")
        print("   - Failure rate metrics updated")
        print("   - Error categorization and tracking")
        print("   - View at: https://www.braintrust.dev/app")
    else:
        print("\n⚠ Braintrust Integration:")
        print("   - Not configured for this deployment")
        print("   - To enable: Redeploy with --braintrust-api-key and --braintrust-project-id")
        print("   - See README.md for setup instructions")


def scenario_dashboard(region: str, braintrust_enabled: bool = False) -> None:
    """
    Scenario 3: Dashboard walkthrough.

    Shows what to look for in pre-configured dashboards:
    - CloudWatch: request rate, latency, errors, token usage
    - Braintrust: LLM-specific metrics, quality scores (if enabled)

    Args:
        region: AWS region
        braintrust_enabled: Whether Braintrust observability is enabled
    """
    logger.info("Starting Scenario 3: Dashboard Walkthrough")

    print("\n" + "=" * 80)
    print("SCENARIO: Dashboard Walkthrough")
    print("=" * 80)

    print("\nView: CloudWatch Dashboard:")
    print(f"   https://console.aws.amazon.com/cloudwatch/home?region={region}#dashboards:")
    print("\n   Key Metrics to Review:")
    print("   1. Request Rate (requests/minute)")
    print("   2. Latency Distribution (P50, P90, P99)")
    print("   3. Error Rate by Tool")
    print("   4. Token Consumption over Time")
    print("   5. Success Rate by Query Type")

    if braintrust_enabled:
        print("\n✓ Braintrust Dashboard:")
        print("   https://www.braintrust.dev/app")
        print("\n   Key Metrics to Review:")
        print("   1. LLM Cost Tracking (per invocation)")
        print("   2. Model Performance Metrics")
        print("   3. Quality Scores and Evaluations")
        print("   4. Prompt/Response Analysis")
        print("   5. Token Usage Breakdown")
    else:
        print("\n⚠ Braintrust Dashboard (Not Configured):")
        print("   https://www.braintrust.dev/app")
        print("\n   To enable Braintrust observability:")
        print("   1. Get Braintrust API key from: https://www.braintrust.dev/app/settings/api-keys")
        print("   2. Get project ID from your Braintrust project URL")
        print(
            "   3. Redeploy agent with: scripts/deploy_agent.sh --braintrust-api-key KEY --braintrust-project-id ID"
        )
        print("\n   See README.md for detailed setup instructions")

    print("\n" + "=" * 80 + "\n")


def main() -> None:
    """
    Main entry point for observability demo.

    Supports three scenarios:
    1. success - Multi-tool query with successful execution
    2. error - Error handling demonstration
    3. dashboard - Dashboard walkthrough
    4. all - Run all scenarios sequentially
    """
    parser = argparse.ArgumentParser(
        description="Amazon Bedrock AgentCore Observability Demo with Dual Platform Support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run all scenarios (reads agent ID from .deployment_metadata.json)
    python simple_observability.py --scenario all

    # Run specific scenario
    python simple_observability.py --scenario success

    # Override agent ID
    python simple_observability.py --agent-id abc123 --scenario all

    # With environment variables
    export AGENTCORE_AGENT_ID=abc123
    python simple_observability.py

    # Enable debug logging
    python simple_observability.py --debug
        """,
    )

    parser.add_argument(
        "--agent-id",
        type=str,
        help="AgentCore Runtime agent ID (reads from .deployment_metadata.json if not specified)",
    )

    parser.add_argument(
        "--region",
        type=str,
        help="AWS region (reads from .deployment_metadata.json or uses us-east-1)",
    )

    parser.add_argument(
        "--scenario",
        type=str,
        choices=["success", "error", "dashboard", "all"],
        default="all",
        help="Which scenario to run (default: all)",
    )

    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load deployment metadata if not provided via arguments
    metadata = _load_deployment_metadata()

    # Get agent ARN from args, env var, or metadata
    agent_arn = None
    if args.agent_id:
        # If agent_id is provided as arg, treat it as ARN
        agent_arn = args.agent_id
    elif metadata:
        agent_arn = metadata.get("agent_arn")

    if not agent_arn:
        # Try environment variable (could be ARN or ID)
        env_value = _get_env_var("AGENTCORE_AGENT_ID") or _get_env_var("AGENTCORE_AGENT_ARN")
        if env_value:
            agent_arn = env_value

    if not agent_arn:
        logger.error("Agent ARN is required.")
        logger.error("Provide via:")
        logger.error("  1. --agent-id command-line argument (ARN)")
        logger.error("  2. AGENTCORE_AGENT_ARN environment variable")
        logger.error("  3. Deploy agent first: scripts/deploy_agent.sh")
        sys.exit(1)

    # Get region from args, env var, or metadata
    region = args.region or _get_env_var("AWS_REGION")
    if not region and metadata:
        region = metadata.get("region")
    if not region:
        region = DEFAULT_REGION

    # Check if Braintrust observability is enabled
    braintrust_enabled = _is_braintrust_enabled(metadata)

    logger.info("Starting Simple Observability Demo")
    logger.info(f"Agent ARN: {agent_arn}")
    logger.info(f"Region: {region}")
    logger.info(f"Scenario: {args.scenario}")
    logger.info(
        f"Braintrust observability: {'Enabled' if braintrust_enabled else 'Disabled (CloudWatch only)'}"
    )

    client = _create_bedrock_client(region)

    try:
        if args.scenario in ["success", "all"]:
            scenario_success(client, agent_arn, region, braintrust_enabled)

            if args.scenario == "all":
                print("\nWaiting: Waiting 10 seconds for traces to propagate...\n")
                time.sleep(10)

        if args.scenario in ["error", "all"]:
            scenario_error(client, agent_arn, region, braintrust_enabled)

            if args.scenario == "all":
                print("\nWaiting: Waiting 10 seconds for traces to propagate...\n")
                time.sleep(10)

        if args.scenario in ["dashboard", "all"]:
            scenario_dashboard(region, braintrust_enabled)

        logger.info("Demo completed successfully!")
        print("\n✓ Demo Complete!")
        print("\nNext Steps:")
        print("1. Open CloudWatch GenAI Observability or APM to view traces")
        if braintrust_enabled:
            print("2. Open Braintrust dashboard at https://www.braintrust.dev/app")
            print("3. Compare observability data across both platforms")
        else:
            print(
                "2. To enable Braintrust: Redeploy with --braintrust-api-key and --braintrust-project-id"
            )
        print("3. Examine span attributes and custom metrics")
        print("4. Review dashboard panels for aggregated metrics\n")

    except Exception as e:
        logger.exception(f"Demo failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
