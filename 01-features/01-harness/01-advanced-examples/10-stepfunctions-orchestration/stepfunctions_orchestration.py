#!/usr/bin/env python3
"""
Invoke a Harness from AWS Step Functions (native integration)

Step Functions has an **optimized service integration** for AgentCore Harness:
a Task state can call `InvokeHarness` directly — no Lambda, no glue code. In
Workflow Studio it shows up as the **AgentCore InvokeHarness** state.

    {
      "Type": "Task",
      "Resource": "arn:aws:states:::bedrockagentcore:invokeHarness",
      "Arguments": {
        "HarnessArn": "arn:aws:bedrock-agentcore:...:harness/my-harness",
        "RuntimeSessionId": "{% $uuid() %}",
        "Messages": [{ "Role": "user", "Content": [{ "Text": "..." }] }]
      },
      "End": true
    }

This sample builds a STANDARD state machine with that one native Task, runs it
against a harness, and reads back the agent's answer. The state machine puts the
agent into a workflow step you can wire retries, catches, choices, and Maps
around — the usual Step Functions toolbox.

Notes on the native integration (from the Step Functions docs):
  * Parameters are **PascalCase** (`HarnessArn`, `Messages`, `Model`), even
    though the underlying API is camelCase.
  * Only the **Request-Response** pattern is supported (no .sync / .waitForToken).
  * The response is **Converse-shaped**: `Output.Message.Content[].Text`,
    `StopReason`, `Usage`. Only the final assistant turn is returned.
  * The Task has a 15-minute max; keep the harness timeout under that.
  * The Step Functions resource URI uses `bedrockagentcore` (no hyphen); the
    harness ARN uses `bedrock-agentcore` (with hyphen).

The script creates a harness (boto3 control plane), builds + runs the state
machine, prints the answer, and tears everything down.

Usage:
    # Run the demo end to end
    python stepfunctions_orchestration.py

    # Ask the agent something specific
    python stepfunctions_orchestration.py \\
        -m "List three serverless patterns for event-driven apps."

    # Reuse an existing harness instead of creating one
    python stepfunctions_orchestration.py --harness-arn arn:aws:bedrock-agentcore:...:harness/my-harness

    # Keep the state machine (and harness) after the demo
    python stepfunctions_orchestration.py --skip-cleanup

    # See all options
    python stepfunctions_orchestration.py --help
"""

import argparse
import json
import os
import sys
import time
import uuid

from pathlib import Path

import boto3
import botocore.exceptions

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.iam import create_harness_role
from utils.client import get_agentcore_control_client

REGION = os.getenv("AWS_DEFAULT_REGION")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_MODEL = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
DEFAULT_PROMPT = "In two sentences, what is AWS Step Functions and when should I use it?"

HARNESS_POLL_INTERVAL = 5
HARNESS_POLL_TIMEOUT = 180
EXECUTION_POLL_INTERVAL = 5
EXECUTION_POLL_TIMEOUT = 600


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(
    description="Invoke an AgentCore Harness from a Step Functions state machine (native integration).",
    formatter_class=argparse.RawDescriptionHelpFormatter,
)
parser.add_argument("--message", "-m", default=DEFAULT_PROMPT, help="Prompt the agent answers")
parser.add_argument("--model", default=DEFAULT_MODEL, metavar="MODEL_ID", help=f"Bedrock model ID (default: {DEFAULT_MODEL})")
parser.add_argument("--harness-arn", default=None, metavar="ARN", help="Use an existing harness instead of creating one")
parser.add_argument("--role-arn", default=None, metavar="ARN", help="Existing Harness execution role ARN (when creating a harness)")
parser.add_argument("--skip-cleanup", action="store_true", help="Keep the state machine (and any created harness)")


# ---------------------------------------------------------------------------
# State machine definition (ASL) — one native AgentCore Task
# ---------------------------------------------------------------------------
def build_definition(harness_arn, model_id):
    """A STANDARD state machine with a single native InvokeHarness Task.

    The agent's message comes from the execution input ($states.input.message).
    Retry/Catch show the recommended error handling for the integration.
    """
    return {
        "Comment": "Invoke an AgentCore Harness via the native Step Functions integration",
        "QueryLanguage": "JSONata",
        "StartAt": "InvokeHarness",
        "States": {
            "InvokeHarness": {
                "Type": "Task",
                "Resource": "arn:aws:states:::bedrockagentcore:invokeHarness",
                "Arguments": {
                    "HarnessArn": harness_arn,
                    "RuntimeSessionId": "{% $uuid() %}",
                    "Messages": [
                        {"Role": "user", "Content": [{"Text": "{% $states.input.message %}"}]}
                    ],
                    "Model": {"BedrockModelConfig": {"ModelId": model_id}},
                    "TimeoutSeconds": 600,
                },
                "Retry": [
                    {
                        "ErrorEquals": ["BedrockAgentCore.ThrottlingException"],
                        "IntervalSeconds": 2,
                        "MaxAttempts": 3,
                        "BackoffRate": 2.0,
                    }
                ],
                "Catch": [
                    {"ErrorEquals": ["States.ALL"], "Next": "HandleError"}
                ],
                "End": True,
            },
            "HandleError": {
                "Type": "Fail",
                "Error": "InvokeHarnessFailed",
                "Cause": "The AgentCore InvokeHarness task failed",
            },
        },
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def poll_harness_status(control, harness_id, target_status="READY", timeout=HARNESS_POLL_TIMEOUT):
    """Poll until a Harness reaches the target status or times out."""
    deadline = time.monotonic() + timeout
    while True:
        resp = control.get_harness(harnessId=harness_id)
        status = resp["harness"]["status"]
        print(f"  Harness status: {status}")
        if status == target_status:
            return resp
        if status in ("FAILED", "CREATE_FAILED", "DELETE_FAILED"):
            raise RuntimeError(f"Harness entered {status}: {resp['harness'].get('failureReason')}")
        if time.monotonic() > deadline:
            raise TimeoutError(f"Harness not {target_status} after {timeout}s (current: {status})")
        time.sleep(HARNESS_POLL_INTERVAL)


def create_sfn_role(iam, role_name, harness_arn):
    """Role Step Functions assumes: permission to invoke the harness directly.

    With the native integration, Step Functions calls InvokeHarness itself — so
    the STATE MACHINE role (not a Lambda) needs bedrock-agentcore:InvokeHarness.
    """
    trust = {
        "Version": "2012-10-17",
        "Statement": [
            {"Effect": "Allow", "Principal": {"Service": "states.amazonaws.com"}, "Action": "sts:AssumeRole"}
        ],
    }
    try:
        arn = iam.get_role(RoleName=role_name)["Role"]["Arn"]
    except iam.exceptions.NoSuchEntityException:
        arn = iam.create_role(RoleName=role_name, AssumeRolePolicyDocument=json.dumps(trust))["Role"]["Arn"]
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "InvokeHarness",
                "Effect": "Allow",
                "Action": ["bedrock-agentcore:InvokeHarness", "bedrock-agentcore:InvokeAgentRuntime"],
                "Resource": harness_arn,
            }
        ],
    }
    iam.put_role_policy(RoleName=role_name, PolicyName="SfnInvokeHarnessPolicy", PolicyDocument=json.dumps(policy))
    return arn


def create_state_machine(sfn, name, definition, role_arn):
    """Create the STANDARD state machine, retrying while the role propagates."""
    deadline = time.monotonic() + 60
    while True:
        try:
            return sfn.create_state_machine(
                name=name, definition=json.dumps(definition), roleArn=role_arn, type="STANDARD"
            )
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "AccessDeniedException" and time.monotonic() < deadline:
                time.sleep(5)
                continue
            raise


def poll_execution(sfn, execution_arn, timeout=EXECUTION_POLL_TIMEOUT):
    """Poll a Step Functions execution until it leaves the RUNNING state."""
    deadline = time.monotonic() + timeout
    while True:
        resp = sfn.describe_execution(executionArn=execution_arn)
        status = resp["status"]
        print(f"  Execution status: {status}")
        if status != "RUNNING":
            return resp
        if time.monotonic() > deadline:
            raise TimeoutError(f"Execution still RUNNING after {timeout}s")
        time.sleep(EXECUTION_POLL_INTERVAL)


def extract_answer(output):
    """Pull the assistant text out of the Converse-shaped native-integration output."""
    msg = (output or {}).get("Output", {}).get("Message", {})
    return "".join(block.get("Text", "") for block in msg.get("Content", []))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(args=None):
    if args is None:
        args = parser.parse_args()

    iam = boto3.client("iam")
    sfn = boto3.client("stepfunctions", region_name=REGION)
    control = get_agentcore_control_client()

    suffix = uuid.uuid4().hex[:8]
    sfn_role_name = f"HarnessSfnRole-{suffix}"
    state_machine_name = f"HarnessInvoke-{suffix}"

    created_harness_id = None
    state_machine_arn = None
    sfn_role_name_created = None

    try:
        # ── Step 1: Ensure a harness exists ───────────────────────────
        print("=" * 60)
        print("Step 1: Harness")
        print("=" * 60)
        if args.harness_arn:
            harness_arn = args.harness_arn
            print(f"  Using existing harness: {harness_arn}")
        else:
            role_arn = args.role_arn or create_harness_role()
            if not args.role_arn:
                print("  Waiting for IAM propagation...")
                time.sleep(10)
            resp = control.create_harness(
                harnessName=f"SfnHarness_{suffix}",
                executionRoleArn=role_arn,
                systemPrompt=[{"text": "You are a concise, helpful assistant."}],
            )
            created_harness_id = resp["harness"]["harnessId"]
            harness_arn = resp["harness"]["arn"]
            print(f"  Created harness: {created_harness_id}")
            poll_harness_status(control, created_harness_id)

        # ── Step 2: Step Functions role (InvokeHarness) ───────────────
        print("\n" + "=" * 60)
        print("Step 2: Step Functions execution role")
        print("=" * 60)
        sfn_role_arn = create_sfn_role(iam, sfn_role_name, harness_arn)
        sfn_role_name_created = sfn_role_name
        print(f"  Role: {sfn_role_arn}")
        time.sleep(10)

        # ── Step 3: Create the state machine ──────────────────────────
        print("\n" + "=" * 60)
        print("Step 3: Create state machine (native InvokeHarness task)")
        print("=" * 60)
        definition = build_definition(harness_arn, args.model)
        sm = create_state_machine(sfn, state_machine_name, definition, sfn_role_arn)
        state_machine_arn = sm["stateMachineArn"]
        print(f"  State machine ARN: {state_machine_arn}")

        # ── Step 4: Start an execution ────────────────────────────────
        print("\n" + "=" * 60)
        print("Step 4: Start execution")
        print("=" * 60)
        print(f"  Message: {args.message}\n")
        exec_resp = sfn.start_execution(
            stateMachineArn=state_machine_arn,
            name=f"run-{uuid.uuid4().hex[:8]}",
            input=json.dumps({"message": args.message}),
        )
        result = poll_execution(sfn, exec_resp["executionArn"])

        # ── Step 5: Show the agent's answer ───────────────────────────
        print("\n" + "=" * 60)
        print("Step 5: Result")
        print("=" * 60)
        status = result["status"]
        print(f"  Execution status: {status}")
        if status == "SUCCEEDED":
            output = json.loads(result["output"])
            print(f"\n  Agent answer:\n  {extract_answer(output)}\n")
            usage = output.get("Usage", {})
            if usage:
                print(f"  Tokens: {usage}")
        else:
            print(f"  {result.get('error')}: {result.get('cause')}")

        print("=" * 60)
        print("Done!")
        print("=" * 60)

    finally:
        if not args.skip_cleanup:
            print("\nCleaning up...")
            _cleanup(iam, sfn, control, state_machine_arn, sfn_role_name_created, created_harness_id)
        else:
            print("\n--skip-cleanup set — leaving resources in place.")


def _cleanup(iam, sfn, control, state_machine_arn, sfn_role_name, harness_id):
    """Delete the state machine, SFN role, and any harness this script created."""
    if state_machine_arn:
        try:
            sfn.delete_state_machine(stateMachineArn=state_machine_arn)
            print(f"  Deleted state machine: {state_machine_arn}")
        except Exception as e:
            print(f"  Warning: failed to delete state machine: {e}")

    if sfn_role_name:
        try:
            iam.delete_role_policy(RoleName=sfn_role_name, PolicyName="SfnInvokeHarnessPolicy")
        except Exception:
            pass
        try:
            iam.delete_role(RoleName=sfn_role_name)
            print(f"  Deleted role: {sfn_role_name}")
        except Exception as e:
            print(f"  Warning: failed to delete role {sfn_role_name}: {e}")

    if harness_id:
        try:
            control.delete_harness(harnessId=harness_id)
            print(f"  Deleted harness: {harness_id}")
        except Exception as e:
            print(f"  Warning: failed to delete harness: {e}")


if __name__ == "__main__":
    main()
