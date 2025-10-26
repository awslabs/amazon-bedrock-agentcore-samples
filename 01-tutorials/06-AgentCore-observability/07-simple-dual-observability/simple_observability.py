"""
Simple AgentCore Observability Demo with Dual Platform Support.

This demo shows how Amazon Bedrock AgentCore automatic OpenTelemetry instrumentation
works with both AWS-native CloudWatch and partner platform Braintrust.

Architecture:
    Local Script (this file)
        ↓ boto3 API call
    AgentCore Runtime (managed service)
        ↓ agent execution with automatic OTEL
    AgentCore Gateway (managed service)
        ↓ tool calls via MCP
    MCP Tools (weather, time, calculator)
        ↓ traces exported
    CloudWatch X-Ray + Braintrust

Agent runs in AgentCore Runtime - a fully managed service for hosting agents.
"""

import argparse
import logging
import os
import sys
import time
import uuid
from typing import Any, Dict, Optional

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


def _get_env_var(
    var_name: str,
    default: Optional[str] = None,
    required: bool = False
) -> Optional[str]:
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


def _create_bedrock_client(region: str) -> boto3.client:
    """
    Create Amazon Bedrock AgentCore Runtime client.

    Args:
        region: AWS region

    Returns:
        Configured boto3 client
    """
    try:
        client = boto3.client(
            "bedrock-agentcore-runtime",
            region_name=region
        )
        logger.info(f"Created Bedrock AgentCore Runtime client for region: {region}")
        return client

    except Exception as e:
        logger.exception(f"Failed to create Bedrock client: {e}")
        raise


def _generate_session_id() -> str:
    """
    Generate unique session ID for trace correlation.

    Returns:
        UUID-based session ID
    """
    session_id = f"demo_session_{uuid.uuid4().hex[:16]}"
    logger.debug(f"Generated session ID: {session_id}")
    return session_id


def _invoke_agent(
    client: boto3.client,
    agent_id: str,
    query: str,
    session_id: str,
    enable_trace: bool = True
) -> Dict[str, Any]:
    """
    Invoke AgentCore Runtime agent with automatic OTEL instrumentation.

    The agent runs in AgentCore Runtime (managed service) with automatic
    OpenTelemetry tracing. Traces are exported to both CloudWatch X-Ray
    and Braintrust (if configured).

    Args:
        client: Bedrock AgentCore Runtime client
        agent_id: ID of deployed agent
        query: User query
        session_id: Session ID for correlation
        enable_trace: Enable detailed tracing

    Returns:
        Agent response with output and metadata

    Raises:
        ClientError: If agent invocation fails
    """
    logger.info(f"Invoking agent: {agent_id}")
    logger.info(f"Query: {query}")
    logger.info(f"Session ID: {session_id}")

    start_time = time.time()

    try:
        response = client.invoke_agent(
            agentId=agent_id,
            sessionId=session_id,
            inputText=query,
            enableTrace=enable_trace
        )

        elapsed_time = time.time() - start_time
        logger.info(f"Agent response received in {elapsed_time:.2f}s")

        return {
            "output": response.get("output", ""),
            "trace_id": response.get("traceId", ""),
            "session_id": session_id,
            "elapsed_time": elapsed_time
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))

        logger.error(f"Agent invocation failed: {error_code} - {error_message}")
        raise

    except Exception as e:
        logger.exception(f"Unexpected error during agent invocation: {e}")
        raise


def _print_result(
    result: Dict[str, Any],
    scenario_name: str
) -> None:
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


def _print_observability_links(
    region: str,
    trace_id: str
) -> None:
    """
    Print links to observability platforms for trace inspection.

    Args:
        region: AWS region
        trace_id: Trace ID to look up
    """
    print("\nView: VIEW TRACES IN:")
    print(f"\n1. CloudWatch X-Ray:")
    print(f"   https://console.aws.amazon.com/cloudwatch/home?region={region}#xray:traces")
    print(f"   Search for trace ID: {trace_id}")

    print(f"\n2. Braintrust Dashboard:")
    print(f"   https://www.braintrust.dev/app")
    print(f"   Search for trace ID: {trace_id}")

    print(f"\n3. CloudWatch Logs:")
    print(f"   https://console.aws.amazon.com/cloudwatch/home?region={region}#logsV2:log-groups")
    print(f"   Filter by session ID or trace ID\n")


def scenario_success(
    client: boto3.client,
    agent_id: str,
    region: str
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
    - Gateway execution spans (weather, time)
    - Response formatting span
    """
    logger.info("Starting Scenario 1: Successful Multi-Tool Query")

    session_id = _generate_session_id()
    query = "What's the weather in Seattle and what time is it there?"

    result = _invoke_agent(
        client=client,
        agent_id=agent_id,
        query=query,
        session_id=session_id
    )

    _print_result(result, "Scenario 1: Successful Multi-Tool Query")
    _print_observability_links(region, result["trace_id"])

    print("✓ Expected in CloudWatch X-Ray:")
    print("   - Agent invocation span")
    print("   - Tool selection span (reasoning)")
    print("   - Gateway spans: weather tool, time tool")
    print("   - Total latency: ~1-2 seconds")

    print("\n✓ Expected in Braintrust:")
    print("   - LLM call details (model, tokens, cost)")
    print("   - Tool execution timeline")
    print("   - Latency breakdown by component")


def scenario_error(
    client: boto3.client,
    agent_id: str,
    region: str
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
    - Gateway execution span (calculator) - ERROR
    - Error details in span attributes
    """
    logger.info("Starting Scenario 2: Error Handling")

    session_id = _generate_session_id()
    query = "Calculate the factorial of -5"

    result = _invoke_agent(
        client=client,
        agent_id=agent_id,
        query=query,
        session_id=session_id
    )

    _print_result(result, "Scenario 2: Error Handling")
    _print_observability_links(region, result["trace_id"])

    print("✓ Expected in CloudWatch X-Ray:")
    print("   - Error span highlighted in red")
    print("   - Error status code and message in attributes")
    print("   - Calculator tool span shows failure")
    print("   - Agent handles error gracefully")

    print("\n✓ Expected in Braintrust:")
    print("   - Error marked in timeline")
    print("   - Exception details recorded")
    print("   - Tool failure reason visible")


def scenario_dashboard(region: str) -> None:
    """
    Scenario 3: Dashboard walkthrough.

    Shows what to look for in pre-configured dashboards:
    - CloudWatch: request rate, latency, errors, token usage
    - Braintrust: LLM-specific metrics, quality scores
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

    print("\nView: Braintrust Dashboard:")
    print("   https://www.braintrust.dev/app")
    print("\n   Key Metrics to Review:")
    print("   1. LLM Performance (latency, tokens)")
    print("   2. Token Costs (input, output, total)")
    print("   3. Quality Scores (if evaluations configured)")
    print("   4. Trace Search and Filtering")
    print("   5. Error Analysis")

    print("\nNote: Comparison:")
    print("   - CloudWatch: AWS-native, integrates with alarms/dashboards")
    print("   - Braintrust: AI-focused, specialized LLM metrics")
    print("   - Both: Receive same OTEL traces (vendor neutral!)")
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
    # Run all scenarios
    python simple_observability_demo.py --agent-id abc123 --scenario all

    # Run specific scenario
    python simple_observability_demo.py --agent-id abc123 --scenario success

    # With environment variables
    export AGENTCORE_AGENT_ID=abc123
    python simple_observability_demo.py

    # Enable debug logging
    python simple_observability_demo.py --agent-id abc123 --debug
        """
    )

    parser.add_argument(
        "--agent-id",
        type=str,
        default=_get_env_var("AGENTCORE_AGENT_ID"),
        help="AgentCore Runtime agent ID (or set AGENTCORE_AGENT_ID env var)"
    )

    parser.add_argument(
        "--region",
        type=str,
        default=_get_env_var("AWS_REGION", DEFAULT_REGION),
        help=f"AWS region (default: {DEFAULT_REGION})"
    )

    parser.add_argument(
        "--scenario",
        type=str,
        choices=["success", "error", "dashboard", "all"],
        default="all",
        help="Which scenario to run (default: all)"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.agent_id:
        logger.error("Agent ID is required. Provide via --agent-id or AGENTCORE_AGENT_ID env var")
        sys.exit(1)

    logger.info("Starting Simple Observability Demo")
    logger.info(f"Agent ID: {args.agent_id}")
    logger.info(f"Region: {args.region}")
    logger.info(f"Scenario: {args.scenario}")

    client = _create_bedrock_client(args.region)

    try:
        if args.scenario in ["success", "all"]:
            scenario_success(client, args.agent_id, args.region)

            if args.scenario == "all":
                print("\nWaiting: Waiting 10 seconds for traces to propagate...\n")
                time.sleep(10)

        if args.scenario in ["error", "all"]:
            scenario_error(client, args.agent_id, args.region)

            if args.scenario == "all":
                print("\nWaiting: Waiting 10 seconds for traces to propagate...\n")
                time.sleep(10)

        if args.scenario in ["dashboard", "all"]:
            scenario_dashboard(args.region)

        logger.info("Demo completed successfully!")
        print("\n✓ Demo Complete!")
        print("\nNext Steps:")
        print("1. Open CloudWatch X-Ray to view traces")
        print("2. Open Braintrust dashboard to compare")
        print("3. Examine span attributes and custom metrics")
        print("4. Review dashboard panels for aggregated metrics\n")

    except Exception as e:
        logger.exception(f"Demo failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
