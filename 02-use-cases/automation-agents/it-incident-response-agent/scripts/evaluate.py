#!/usr/bin/env python3
"""On-demand evaluation: run built-in and custom evaluators against a trace.

Usage:
  python scripts/evaluate.py                   # evaluates the latest trace
  python scripts/evaluate.py <trace_id>        # evaluates a specific trace

Prerequisites:
  - CloudWatch Transaction Search enabled in the region
  - Stack deployed with `agentcore deploy`
  - At least one ticket processed (to generate a trace)

The script runs three built-in evaluators (Correctness, Helpfulness,
ToolSelectionQuality) plus a custom IncidentResolutionQuality evaluator.
"""

import argparse
import json
import os
import sys
import time

import boto3
from botocore.exceptions import ClientError

REGION = os.environ.get("AWS_REGION", "us-west-2")
JUDGE_MODEL_ID = os.environ.get(
    "JUDGE_MODEL_ID", "us.anthropic.claude-sonnet-4-6"
)
CUSTOM_EVALUATOR_NAME = "IncidentResolutionQuality"

CUSTOM_INSTRUCTIONS = """\
You are a senior IT incident-response engineer reviewing one agent run.

Score how well the agent resolved the user's IT ticket end-to-end. Reward:
- correct identification of the affected user / asset / process
- relevant runbook lookups via the knowledge base
- a change request opened only when warranted
- a clear, actionable resolution comment back on the ticket

Penalize hallucinated user IDs, skipped diagnosis steps, vague resolutions,
or unnecessary change requests.

Return your numeric rating with a one-paragraph justification.
"""


def ensure_custom_evaluator(control) -> str:
    """Create or find the custom evaluator, return its ID."""
    try:
        for page in control.get_paginator("list_evaluators").paginate():
            for e in page.get("evaluators", []):
                if e.get("evaluatorName") == CUSTOM_EVALUATOR_NAME:
                    print(f"  Found existing evaluator: {CUSTOM_EVALUATOR_NAME}")
                    return e["evaluatorId"]
    except ClientError:
        pass

    print(f"  Creating custom evaluator: {CUSTOM_EVALUATOR_NAME}")
    resp = control.create_evaluator(
        evaluatorName=CUSTOM_EVALUATOR_NAME,
        description="Domain-specific quality score for IT incident resolution.",
        level="TRACE",
        evaluatorConfig={
            "llmAsAJudge": {
                "instructions": CUSTOM_INSTRUCTIONS,
                "ratingScale": {
                    "numerical": [
                        {"value": 1.0, "label": "poor",
                         "definition": "Wrong user/asset, no runbook usage, no resolution."},
                        {"value": 3.0, "label": "ok",
                         "definition": "Partially correct diagnosis, weak resolution."},
                        {"value": 5.0, "label": "excellent",
                         "definition": "Correct diagnosis, runbook-backed, clear actionable resolution."},
                    ]
                },
                "modelConfig": {
                    "bedrockEvaluatorModelConfig": {"modelId": JUDGE_MODEL_ID}
                },
            }
        },
    )
    return resp["evaluatorId"]


def latest_trace_id(log_group: str, lookback_minutes: int = 30) -> str:
    """Find the most recent traceId in the runtime log group."""
    logs = boto3.client("logs", region_name=REGION)
    end = int(time.time() * 1000)
    start = end - lookback_minutes * 60 * 1000

    query = (
        "fields @timestamp, trace_id "
        "| filter ispresent(trace_id) "
        "| sort @timestamp desc "
        "| limit 1"
    )
    q = logs.start_query(
        logGroupName=log_group,
        startTime=start,
        endTime=end,
        queryString=query,
    )["queryId"]

    while True:
        resp = logs.get_query_results(queryId=q)
        if resp["status"] in ("Complete", "Failed", "Cancelled"):
            break
        time.sleep(1)

    if not resp["results"]:
        sys.exit(
            f"No traces found in {log_group} in the last {lookback_minutes}m.\n"
            "Run ./scripts/publish_ticket.sh first and wait ~30s."
        )
    fields = {kv["field"]: kv["value"] for kv in resp["results"][0]}
    return fields["trace_id"]


def run_evaluator(rt, evaluator_id: str, trace_id: str) -> list:
    """Run an evaluator against a trace."""
    try:
        resp = rt.evaluate(
            evaluatorId=evaluator_id,
            evaluationTarget={"traceIds": [trace_id]},
        )
        return resp.get("evaluationResults", [])
    except ClientError as exc:
        print(f"    FAILED: {exc.response['Error']['Code']}")
        return []


def main():
    parser = argparse.ArgumentParser(description="Run on-demand evaluation")
    parser.add_argument(
        "trace_id",
        nargs="?",
        help="Trace ID to evaluate (defaults to latest)",
    )
    parser.add_argument(
        "--log-group",
        default="/aws/bedrock-agentcore/runtimes/ITIncidentAgent",
        help="CloudWatch log group for the runtime",
    )
    args = parser.parse_args()

    trace_id = args.trace_id or latest_trace_id(args.log_group)
    print(f"==> Evaluating trace: {trace_id}")
    print()

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    rt = boto3.client("bedrock-agentcore", region_name=REGION)

    custom_id = ensure_custom_evaluator(control)
    evaluators = {
        custom_id: CUSTOM_EVALUATOR_NAME,
        "Builtin.Correctness": "Correctness",
        "Builtin.Helpfulness": "Helpfulness",
        "Builtin.ToolSelectionQuality": "Tool Selection Quality",
    }

    all_results = []
    for eid, name in evaluators.items():
        print(f"  Running: {name} ...")
        results = run_evaluator(rt, eid, trace_id)
        for r in results:
            r["evaluator_name"] = name
        all_results.extend(results)

    print()
    print("==> Results")
    print(json.dumps(all_results, indent=2, default=str))


if __name__ == "__main__":
    main()
