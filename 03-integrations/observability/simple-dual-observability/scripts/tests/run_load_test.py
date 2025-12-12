#!/usr/bin/env python3
"""
Load testing script for AgentCore observability demo.

Generates various types of requests to test agent behavior and create rich
observability data in CloudWatch and Braintrust:
- Single tool invocations
- Multi-tool queries (2-3 tools in parallel)
- Unanswerable questions (no matching tools)
- Error-inducing queries
- Mixed workloads

Configurable parameters:
- Duration (minutes)
- Request rate (requests/minute)
- Request type distribution
"""

import argparse
import json
import logging
import random
import sys
import time
import uuid
from datetime import datetime, timedelta
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


# Test query templates organized by type
TEST_QUERIES = {
    "weather_only": [
        "What's the weather in Seattle?",
        "How's the weather in New York?",
        "Tell me the current weather in Tokyo",
        "What's the temperature in London?",
        "Is it raining in Paris?",
    ],
    "time_only": [
        "What time is it in Tokyo?",
        "What's the current time in London?",
        "Tell me the time in New York",
        "What time is it in Sydney right now?",
        "Show me the time in Berlin",
    ],
    "calculator_only": [
        "What is 25 + 37?",
        "Calculate 144 divided by 12",
        "What's 15 times 8?",
        "Subtract 45 from 100",
        "Calculate the factorial of 5",
    ],
    "weather_and_time": [
        "What's the weather in Seattle and what time is it there?",
        "Tell me the weather and current time in London",
        "How's the weather in Tokyo and what's the local time?",
        "What's the temperature in Paris and what time is it?",
        "Give me weather and time for New York",
    ],
    "multi_tool": [
        "What's the weather in Seattle, the time in Tokyo, and what's 50 + 75?",
        "Tell me the weather in London, time in New York, and calculate 144/12",
        "What's the temperature in Paris, time in Berlin, and what's 25 times 4?",
        "Weather in Tokyo, time in Sydney, and factorial of 6",
        "Temperature in Seattle, current time there, and what's 100 - 33?",
    ],
    "error_inducing": [
        "Calculate the factorial of -5",
        "What's the weather in XYZ123?",
        "Tell me the time in InvalidTimezone",
        "Divide 100 by 0",
        "What's the weather in 12345?",
    ],
    "unanswerable": [
        "What's the capital of France?",
        "Who won the World Cup in 2022?",
        "What's the best programming language?",
        "How do I bake a cake?",
        "What's the meaning of life?",
        "Tell me a joke",
        "What's the stock price of Apple?",
        "How many people live in China?",
    ],
}


def _load_deployment_metadata() -> dict[str, Any] | None:
    """Load agent deployment metadata from .deployment_metadata.json."""
    script_dir = Path(__file__).parent.parent
    metadata_file = script_dir / ".deployment_metadata.json"

    if metadata_file.exists():
        try:
            with open(metadata_file) as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load deployment metadata: {e}")
            return None
    return None


def _create_bedrock_client(region: str) -> boto3.client:
    """Create Amazon Bedrock AgentCore client."""
    return boto3.client("bedrock-agentcore", region_name=region)


def _generate_session_id() -> str:
    """Generate a unique session ID (minimum 33 characters)."""
    return str(uuid.uuid4())


def _invoke_agent(
    client: boto3.client, agent_arn: str, query: str, session_id: str
) -> dict[str, Any]:
    """
    Invoke the agent with a query.

    Args:
        client: Bedrock AgentCore client
        agent_arn: ARN of deployed agent
        query: User query
        session_id: Session ID for this invocation

    Returns:
        Dictionary with response, trace_id, elapsed_time, and error info
    """
    start_time = time.time()

    try:
        payload = json.dumps({"prompt": query})
        response = client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn, runtimeSessionId=session_id, payload=payload
        )

        # Handle StreamingBody response
        agent_response = None
        if "response" in response:
            response_body = response["response"]
            if hasattr(response_body, "read"):
                raw_data = response_body.read()
                if isinstance(raw_data, bytes):
                    agent_response = raw_data.decode("utf-8")

        elapsed_time = time.time() - start_time

        return {
            "success": True,
            "output": agent_response or "",
            "trace_id": response.get("traceId", ""),
            "session_id": session_id,
            "elapsed_time": elapsed_time,
            "error": None,
        }

    except ClientError as e:
        elapsed_time = time.time() - start_time
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))

        return {
            "success": False,
            "output": "",
            "trace_id": "",
            "session_id": session_id,
            "elapsed_time": elapsed_time,
            "error": f"{error_code}: {error_message}",
        }

    except Exception as e:
        elapsed_time = time.time() - start_time

        return {
            "success": False,
            "output": "",
            "trace_id": "",
            "session_id": session_id,
            "elapsed_time": elapsed_time,
            "error": str(e),
        }


def _select_query(distribution: dict[str, int]) -> tuple[str, str]:
    """
    Select a random query based on distribution weights.

    Args:
        distribution: Dict mapping query type to weight

    Returns:
        Tuple of (query_type, query_text)
    """
    query_types = list(distribution.keys())
    weights = list(distribution.values())

    query_type = random.choices(query_types, weights=weights)[0]
    query_text = random.choice(TEST_QUERIES[query_type])

    return query_type, query_text


def _run_load_test(
    client: boto3.client,
    agent_arn: str,
    duration_minutes: int,
    requests_per_minute: int,
    distribution: dict[str, int],
) -> dict[str, Any]:
    """
    Run load test for specified duration and rate.

    Args:
        client: Bedrock AgentCore client
        agent_arn: ARN of deployed agent
        duration_minutes: How long to run the test
        requests_per_minute: Target request rate
        distribution: Query type distribution weights

    Returns:
        Test statistics
    """
    end_time = datetime.now() + timedelta(minutes=duration_minutes)
    interval_seconds = 60.0 / requests_per_minute

    stats = {
        "total_requests": 0,
        "successful_requests": 0,
        "failed_requests": 0,
        "by_type": {qtype: {"count": 0, "errors": 0} for qtype in TEST_QUERIES.keys()},
        "total_elapsed_time": 0.0,
        "errors": [],
    }

    logger.info(
        f"Starting load test for {duration_minutes} minutes at {requests_per_minute} req/min"
    )
    logger.info(f"Request interval: {interval_seconds:.2f} seconds")
    logger.info(f"End time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("")

    request_count = 0

    while datetime.now() < end_time:
        request_count += 1
        session_id = _generate_session_id()

        # Select query based on distribution
        query_type, query = _select_query(distribution)

        logger.info(f"[{request_count}] Type: {query_type}")
        logger.info(f"[{request_count}] Query: {query}")

        # Invoke agent
        result = _invoke_agent(client, agent_arn, query, session_id)

        # Update statistics
        stats["total_requests"] += 1
        stats["by_type"][query_type]["count"] += 1
        stats["total_elapsed_time"] += result["elapsed_time"]

        if result["success"]:
            stats["successful_requests"] += 1
            logger.info(f"[{request_count}] ✓ Success ({result['elapsed_time']:.2f}s)")
            logger.debug(f"[{request_count}] Response: {result['output'][:100]}...")
        else:
            stats["failed_requests"] += 1
            stats["by_type"][query_type]["errors"] += 1
            stats["errors"].append(
                {
                    "query": query,
                    "error": result["error"],
                    "timestamp": datetime.now().isoformat(),
                }
            )
            logger.warning(
                f"[{request_count}] ✗ Failed ({result['elapsed_time']:.2f}s): {result['error']}"
            )

        if result["trace_id"]:
            logger.debug(f"[{request_count}] Trace ID: {result['trace_id']}")

        logger.info("")

        # Wait for next request (if not at end)
        if datetime.now() < end_time:
            time.sleep(interval_seconds)

    return stats


def _print_summary(stats: dict[str, Any], duration_minutes: int) -> None:
    """Print test summary statistics."""
    logger.info("")
    logger.info("=" * 80)
    logger.info("LOAD TEST SUMMARY")
    logger.info("=" * 80)
    logger.info("")

    logger.info(f"Duration: {duration_minutes} minutes")
    logger.info(f"Total Requests: {stats['total_requests']}")
    logger.info(
        f"Successful: {stats['successful_requests']} ({stats['successful_requests'] / stats['total_requests'] * 100:.1f}%)"
    )
    logger.info(
        f"Failed: {stats['failed_requests']} ({stats['failed_requests'] / stats['total_requests'] * 100:.1f}%)"
    )

    if stats["total_requests"] > 0:
        avg_latency = stats["total_elapsed_time"] / stats["total_requests"]
        logger.info(f"Average Latency: {avg_latency:.2f}s")

    logger.info("")
    logger.info("Requests by Type:")
    for qtype, data in stats["by_type"].items():
        if data["count"] > 0:
            error_pct = (data["errors"] / data["count"] * 100) if data["count"] > 0 else 0
            logger.info(
                f"  {qtype:20s}: {data['count']:3d} requests ({data['errors']:3d} errors, {error_pct:.1f}%)"
            )

    if stats["errors"]:
        logger.info("")
        logger.info("Error Summary:")
        error_types = {}
        for error in stats["errors"]:
            error_msg = error["error"]
            error_types[error_msg] = error_types.get(error_msg, 0) + 1

        for error_msg, count in sorted(error_types.items(), key=lambda x: -x[1]):
            logger.info(f"  {count:3d}x {error_msg}")

    logger.info("")
    logger.info("=" * 80)


def main() -> None:
    """Main entry point for load testing."""
    parser = argparse.ArgumentParser(
        description="Load testing for Amazon Bedrock AgentCore observability demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Query Types:
  weather_only       - Single tool: weather queries
  time_only          - Single tool: time queries
  calculator_only    - Single tool: calculator queries
  weather_and_time   - Multi-tool: weather + time (2 tools)
  multi_tool         - Multi-tool: weather + time + calculator (3 tools)
  error_inducing     - Queries that cause tool errors
  unanswerable       - Questions outside tool capabilities

Examples:
  # Run for 5 minutes at 2 requests/minute (balanced workload)
  python run_load_test.py --duration 5 --rate 2

  # Run for 30 minutes at 5 requests/minute
  python run_load_test.py --duration 30 --rate 5

  # Focus on multi-tool queries (80% multi-tool, 20% other)
  python run_load_test.py --duration 10 --rate 3 \\
      --multi-tool 80 --weather-and-time 10 --unanswerable 10

  # Include errors (20% error-inducing queries)
  python run_load_test.py --duration 15 --rate 4 \\
      --weather-only 30 --time-only 30 --calculator-only 20 \\
      --error-inducing 20

  # High rate test with unanswerable questions
  python run_load_test.py --duration 10 --rate 10 \\
      --weather-only 25 --time-only 25 --multi-tool 25 --unanswerable 25
""",
    )

    parser.add_argument(
        "--duration", type=int, default=5, help="Test duration in minutes (default: 5)"
    )

    parser.add_argument(
        "--rate", type=int, default=2, help="Request rate in requests/minute (default: 2)"
    )

    parser.add_argument(
        "--region",
        type=str,
        help="AWS region (reads from .deployment_metadata.json if not specified)",
    )

    parser.add_argument(
        "--agent-arn",
        type=str,
        help="Agent ARN (reads from .deployment_metadata.json if not specified)",
    )

    # Distribution weights for each query type
    parser.add_argument(
        "--weather-only", type=int, default=15, help="Weight for weather-only queries (default: 15)"
    )

    parser.add_argument(
        "--time-only", type=int, default=15, help="Weight for time-only queries (default: 15)"
    )

    parser.add_argument(
        "--calculator-only",
        type=int,
        default=10,
        help="Weight for calculator-only queries (default: 10)",
    )

    parser.add_argument(
        "--weather-and-time",
        type=int,
        default=25,
        help="Weight for weather+time queries (default: 25)",
    )

    parser.add_argument(
        "--multi-tool",
        type=int,
        default=20,
        help="Weight for multi-tool queries (3 tools) (default: 20)",
    )

    parser.add_argument(
        "--error-inducing",
        type=int,
        default=10,
        help="Weight for error-inducing queries (default: 10)",
    )

    parser.add_argument(
        "--unanswerable", type=int, default=5, help="Weight for unanswerable queries (default: 5)"
    )

    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load deployment metadata
    metadata = _load_deployment_metadata()

    # Get agent ARN
    agent_arn = args.agent_arn
    if not agent_arn and metadata:
        agent_arn = metadata.get("agent_arn")

    if not agent_arn:
        logger.error("Agent ARN is required.")
        logger.error("Provide via:")
        logger.error("  1. --agent-arn command-line argument")
        logger.error("  2. Deploy agent first: ../deploy_agent.sh")
        sys.exit(1)

    # Get region
    region = args.region
    if not region and metadata:
        region = metadata.get("region", "us-east-1")
    if not region:
        region = "us-east-1"

    # Build distribution
    distribution = {
        "weather_only": args.weather_only,
        "time_only": args.time_only,
        "calculator_only": args.calculator_only,
        "weather_and_time": args.weather_and_time,
        "multi_tool": args.multi_tool,
        "error_inducing": args.error_inducing,
        "unanswerable": args.unanswerable,
    }

    # Validate distribution
    total_weight = sum(distribution.values())
    if total_weight == 0:
        logger.error("Total distribution weight must be > 0")
        sys.exit(1)

    logger.info("=" * 80)
    logger.info("LOAD TEST CONFIGURATION")
    logger.info("=" * 80)
    logger.info(f"Agent ARN: {agent_arn}")
    logger.info(f"Region: {region}")
    logger.info(f"Duration: {args.duration} minutes")
    logger.info(f"Request Rate: {args.rate} requests/minute")
    logger.info(f"Total Requests: ~{args.duration * args.rate}")
    logger.info("")
    logger.info("Query Distribution:")
    for qtype, weight in distribution.items():
        if weight > 0:
            pct = (weight / total_weight) * 100
            logger.info(f"  {qtype:20s}: {weight:3d} ({pct:5.1f}%)")
    logger.info("=" * 80)
    logger.info("")

    # Create client
    client = _create_bedrock_client(region)

    # Run load test
    try:
        stats = _run_load_test(
            client=client,
            agent_arn=agent_arn,
            duration_minutes=args.duration,
            requests_per_minute=args.rate,
            distribution=distribution,
        )

        # Print summary
        _print_summary(stats, args.duration)

    except KeyboardInterrupt:
        logger.info("")
        logger.info("Load test interrupted by user")
        sys.exit(0)

    except Exception as e:
        logger.exception(f"Load test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
