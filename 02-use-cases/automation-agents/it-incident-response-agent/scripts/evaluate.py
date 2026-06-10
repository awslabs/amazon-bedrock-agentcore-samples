#!/usr/bin/env python3
"""Retrieve online evaluation results from the AgentCore Online Evaluation config.

Usage:
  python scripts/evaluate.py              # latest results (last 1 hour)
  python scripts/evaluate.py --hours 24   # last 24 hours of results
  python scripts/evaluate.py --raw        # print raw JSON (for piping)

Prerequisites:
  - CloudWatch Transaction Search enabled in the region
  - Stack deployed with online evaluation enabled (onlineEvalConfigs[] in agentcore.json)
  - At least one ticket processed (to generate evaluable traces)

Online evaluation runs continuously against all agent invocations, scoring:
  - Correctness — Did the agent provide accurate information?
  - Helpfulness — Was the response useful to the user?
  - ToolSelectionAccuracy — Did the agent choose the right tools?
  - GoalSuccessRate — Did the agent accomplish the user's goal?
"""

import argparse
import json
import os
import sys
import time

import boto3

REGION = os.environ.get("AWS_REGION", "us-west-2")
STACK_NAME = "AgentCore-ITIncidentAgent-dev"


def find_eval_log_group() -> str:
    """Find the online evaluation results log group."""
    logs = boto3.client("logs", region_name=REGION)
    resp = logs.describe_log_groups(
        logGroupNamePrefix="/aws/bedrock-agentcore/evaluations/results/ITIncidentAgent"
    )
    groups = [lg["logGroupName"] for lg in resp.get("logGroups", [])]
    if not groups:
        sys.exit(
            "No evaluation results log group found.\n"
            "Ensure onlineEvalConfigs[] is populated in agentcore.json and\n"
            "CloudWatch Transaction Search is enabled.\n"
            "See: docs/online-eval-workaround.md"
        )
    # Use the most recently created one
    return groups[-1]


def query_eval_results(log_group: str, hours: int = 1) -> list:
    """Query evaluation results from CloudWatch Logs."""
    logs = boto3.client("logs", region_name=REGION)
    end = int(time.time() * 1000)
    start = end - hours * 60 * 60 * 1000

    query = (
        "fields @timestamp, @message "
        "| sort @timestamp desc "
        "| limit 50"
    )

    q = logs.start_query(
        logGroupName=log_group,
        startTime=start,
        endTime=end,
        queryString=query,
    )["queryId"]

    # Poll for results
    while True:
        resp = logs.get_query_results(queryId=q)
        if resp["status"] in ("Complete", "Failed", "Cancelled"):
            break
        time.sleep(1)

    results = []
    for record in resp.get("results", []):
        fields = {kv["field"]: kv["value"] for kv in record}
        msg = fields.get("@message", "")
        if msg:
            try:
                results.append(json.loads(msg))
            except json.JSONDecodeError:
                results.append({"raw": msg, "timestamp": fields.get("@timestamp")})
    return results


def format_results(results: list) -> None:
    """Print evaluation results in a human-readable format."""
    if not results:
        print("  No evaluation results found in the specified time window.")
        print("  This can mean:")
        print("    - No tickets have been processed recently")
        print("    - Online evaluation is still processing (wait 2-3 min after invocation)")
        print("    - CloudWatch Transaction Search is not enabled")
        return

    print(f"  Found {len(results)} evaluation result(s):\n")

    for i, result in enumerate(results, 1):
        if isinstance(result, dict) and "raw" in result:
            print(f"  [{i}] {result.get('timestamp', 'unknown')}: {result['raw'][:200]}")
            continue

        trace_id = result.get("traceId", result.get("trace_id", "unknown"))
        evaluator = result.get("evaluatorName", result.get("evaluator_name", "unknown"))
        score = result.get("score", result.get("rating", "N/A"))
        rationale = result.get("rationale", result.get("justification", ""))

        print(f"  [{i}] Trace: {trace_id[:16]}...")
        print(f"      Evaluator: {evaluator}")
        print(f"      Score: {score}")
        if rationale:
            print(f"      Rationale: {rationale[:150]}...")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Retrieve online evaluation results for the IT Incident Response Agent"
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=1,
        help="How many hours back to query (default: 1)",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print raw JSON output (for piping to jq, etc.)",
    )
    args = parser.parse_args()

    print("═══════════════════════════════════════════════════════════════")
    print("  Online Evaluation Results — IT Incident Response Agent")
    print("═══════════════════════════════════════════════════════════════")
    print()

    # Find the evaluation results log group
    log_group = find_eval_log_group()
    print(f"  Log group: {log_group}")
    print(f"  Time window: last {args.hours} hour(s)")
    print()

    # Query results
    results = query_eval_results(log_group, args.hours)

    if args.raw:
        print(json.dumps(results, indent=2, default=str))
    else:
        format_results(results)

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  Evaluators (configured in agentcore.json → onlineEvalConfigs[]):")
    print("    • Builtin.Correctness")
    print("    • Builtin.Helpfulness")
    print("    • Builtin.ToolSelectionAccuracy")
    print("    • Builtin.GoalSuccessRate")
    print()
    print("  Dashboard: CloudWatch → GenAI Observability → ITIncidentAgent")
    print("═══════════════════════════════════════════════════════════════")


if __name__ == "__main__":
    main()
