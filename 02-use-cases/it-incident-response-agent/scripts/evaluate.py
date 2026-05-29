#!/usr/bin/env python3
"""On-demand evaluation: register a custom evaluator (if missing) and run
both the custom and built-in evaluators against the most recent session
of the runtime.

Usage:
  scripts/evaluate.py                       # evaluates the latest session
  scripts/evaluate.py <session_id|trace_id> # evaluates a specific run

Reads stack outputs to discover the runtime + log group + service name.
"""

import argparse
import json
import os
import subprocess
import sys
import time

import boto3
from botocore.exceptions import ClientError

REGION = os.environ.get("AWS_REGION", "us-west-2")
STACK = os.environ.get("STACK_NAME", "ItIncidentResponseAgent")
JUDGE_MODEL_ID = os.environ.get(
    "JUDGE_MODEL_ID", "us.anthropic.claude-sonnet-4-6-20250929-v1:0"
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


def stack_outputs() -> dict:
    cfn = boto3.client("cloudformation", region_name=REGION)
    out = cfn.describe_stacks(StackName=STACK)["Stacks"][0]["Outputs"]
    return {o["OutputKey"]: o["OutputValue"] for o in out}


def ensure_custom_evaluator(control) -> str:
    for page in control.get_paginator("list_evaluators").paginate():
        for e in page.get("evaluators", []):
            if e.get("evaluatorName") == CUSTOM_EVALUATOR_NAME:
                return e["evaluatorId"]

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


def latest_trace_id(log_group: str, service_name: str, lookback_minutes: int = 30) -> str:
    """Find the most recent traceId in the runtime log group."""
    logs = boto3.client("logs", region_name=REGION)
    end = int(time.time() * 1000)
    start = end - lookback_minutes * 60 * 1000

    query = (
        "fields @timestamp, trace_id, span_id, attributes.session.id "
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
            f"No traces found in {log_group} in the last {lookback_minutes}m. "
            f"Run scripts/publish_ticket.sh first and wait ~30s."
        )
    fields = {kv["field"]: kv["value"] for kv in resp["results"][0]}
    return fields.get("trace_id") or fields["span_id"]


def run_evaluator(rt, evaluator_id: str, trace_id: str) -> list:
    resp = rt.evaluate(
        evaluatorId=evaluator_id,
        evaluationTarget={"traceIds": [trace_id]},
    )
    return resp.get("evaluationResults", [])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "trace_id",
        nargs="?",
        help="Trace ID to evaluate (defaults to latest in the log group)",
    )
    args = parser.parse_args()

    outputs = stack_outputs()
    log_group = outputs["RuntimeLogGroupName"]
    service_name = outputs["OtelServiceName"]

    trace_id = args.trace_id or latest_trace_id(log_group, service_name)
    print(f"==> evaluating trace {trace_id}")

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    rt = boto3.client("bedrock-agentcore", region_name=REGION)

    custom_id = ensure_custom_evaluator(control)
    builtins = ["GoalSuccessRate", "Correctness", "Helpfulness",
                "ToolSelectionAccuracy"]

    all_results = []
    for eid in [custom_id, *builtins]:
        print(f"  - {eid} ...")
        try:
            results = run_evaluator(rt, eid, trace_id)
            all_results.extend(results)
        except ClientError as exc:
            print(f"    FAILED: {exc.response['Error']['Code']} - {exc.response['Error'].get('Message','')}")

    print("\n==> results")
    print(json.dumps(all_results, indent=2, default=str))


if __name__ == "__main__":
    main()
