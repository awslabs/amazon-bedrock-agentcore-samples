#!/usr/bin/env python3
"""
Orchestrate a Harness with AWS Step Functions

A Harness has a lifecycle — create, wait until READY, invoke, delete — that maps
naturally onto a state machine. This sample builds a Step Functions **STANDARD**
workflow that drives that lifecycle end to end:

    CreateHarness ─▶ WaitForReady ─▶ GetStatus ─▶ (READY?) ─▶ InvokeHarness ─▶ DeleteHarness ─▶ Done
                          ▲                │
                          └──── not ready ─┘

Why a Lambda task worker (instead of a native SFN service integration)?
  * `InvokeHarness` returns a streaming response; a Step Functions SDK
    integration can't consume a stream. The Lambda drains the stream and
    returns the final text.
  * One small Lambda dispatches on an `action` field (create / status /
    invoke / delete), so the whole lifecycle is one deployable unit.

The script provisions everything it needs, runs one execution, prints the
result, and tears it all down:

    1. IAM roles  — Harness execution role (shared helper), Lambda role, SFN role
    2. Lambda     — the action-dispatched task worker (zipped & deployed inline)
    3. State machine — the ASL definition above
    4. Execution  — start it, poll until it finishes, print the agent's answer
    5. Cleanup    — delete the state machine, Lambda, roles (the workflow deletes
                    the harness itself)

Usage:
    # Run the full orchestration demo
    python stepfunctions_orchestration.py

    # Ask the orchestrated agent something specific
    python stepfunctions_orchestration.py \\
        -m "List three serverless patterns for event-driven apps."

    # Keep the state machine + Lambda after the demo (inspect in the console)
    python stepfunctions_orchestration.py --skip-cleanup

    # See all options
    python stepfunctions_orchestration.py --help
"""

import argparse
import io
import json
import os
import sys
import time
import uuid
import zipfile

from pathlib import Path

import boto3
import botocore.exceptions

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.iam import create_harness_role

REGION = os.getenv("AWS_DEFAULT_REGION")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_MODEL = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
DEFAULT_PROMPT = "In two sentences, what is AWS Step Functions and when should I use it?"

LAMBDA_RUNTIME = "python3.12"
LAMBDA_HANDLER = "index.handler"
LAMBDA_TIMEOUT = 300  # InvokeHarness can run the agent loop for a while

EXECUTION_POLL_INTERVAL = 5
EXECUTION_POLL_TIMEOUT = 600


# ---------------------------------------------------------------------------
# Lambda task worker — deployed inline. Dispatches on `action`.
# ---------------------------------------------------------------------------
LAMBDA_SOURCE = '''
import uuid
import boto3

control = boto3.client("bedrock-agentcore-control")
data = boto3.client("bedrock-agentcore")


def _create(event):
    cfg = event["input"]
    kwargs = {
        "harnessName": cfg["harnessName"],
        "executionRoleArn": cfg["executionRoleArn"],
    }
    if cfg.get("skills"):
        kwargs["skills"] = cfg["skills"]
    resp = control.create_harness(**kwargs)
    h = resp["harness"]
    return {"harnessId": h["harnessId"], "harnessArn": h["arn"], "status": h["status"]}


def _status(event):
    resp = control.get_harness(harnessId=event["harnessId"])
    h = resp["harness"]
    return {"harnessId": h["harnessId"], "harnessArn": h["arn"], "status": h["status"]}


def _invoke(event):
    session_id = str(uuid.uuid4()).upper()
    resp = data.invoke_harness(
        harnessArn=event["harnessArn"],
        runtimeSessionId=session_id,
        messages=[{"role": "user", "content": [{"text": event["message"]}]}],
        model={"bedrockModelConfig": {"modelId": event["model"]}},
    )
    text = ""
    for ev in resp["stream"]:
        if "contentBlockDelta" in ev:
            delta = ev["contentBlockDelta"].get("delta", {})
            if "text" in delta:
                text += delta["text"]
    return {"sessionId": session_id, "text": text}


def _delete(event):
    control.delete_harness(harnessId=event["harnessId"])
    return {"deleted": event["harnessId"]}


HANDLERS = {"create": _create, "status": _status, "invoke": _invoke, "delete": _delete}


def handler(event, context):
    action = event["action"]
    return HANDLERS[action](event)
'''


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(
    description="Drive the full Harness lifecycle from a Step Functions state machine.",
    formatter_class=argparse.RawDescriptionHelpFormatter,
)
parser.add_argument("--message", "-m", default=DEFAULT_PROMPT, help="Prompt the orchestrated agent answers")
parser.add_argument("--model", default=DEFAULT_MODEL, metavar="MODEL_ID", help=f"Bedrock model ID (default: {DEFAULT_MODEL})")
parser.add_argument("--role-arn", default=None, metavar="ARN", help="Existing Harness execution role ARN")
parser.add_argument("--skip-cleanup", action="store_true", help="Keep the state machine + Lambda after the demo")


# ---------------------------------------------------------------------------
# State machine definition (ASL)
# ---------------------------------------------------------------------------
def build_definition(lambda_arn):
    """Amazon States Language definition that orchestrates the harness lifecycle.

    State I/O threads the harness identifiers forward via ResultPath so each
    task receives exactly the fields it needs.
    """
    return {
        "Comment": "Create, wait for, invoke, and delete a Harness",
        "StartAt": "CreateHarness",
        "States": {
            "CreateHarness": {
                "Type": "Task",
                "Resource": lambda_arn,
                "Parameters": {"action": "create", "input.$": "$"},
                "ResultPath": "$.created",
                "Next": "WaitForReady",
            },
            "WaitForReady": {
                "Type": "Wait",
                "Seconds": 5,
                "Next": "GetStatus",
            },
            "GetStatus": {
                "Type": "Task",
                "Resource": lambda_arn,
                "Parameters": {"action": "status", "harnessId.$": "$.created.harnessId"},
                "ResultPath": "$.created",
                "Next": "CheckStatus",
            },
            "CheckStatus": {
                "Type": "Choice",
                "Choices": [
                    {"Variable": "$.created.status", "StringEquals": "READY", "Next": "InvokeHarness"},
                    # Any terminal failure status -> clean up / fail fast. Matching
                    # only "FAILED" would loop forever on CREATE_FAILED, since the
                    # default branch goes back to WaitForReady.
                    {"Variable": "$.created.status", "StringEquals": "FAILED", "Next": "DeleteOnFailure"},
                    {"Variable": "$.created.status", "StringEquals": "CREATE_FAILED", "Next": "DeleteOnFailure"},
                    {"Variable": "$.created.status", "StringEquals": "UPDATE_FAILED", "Next": "DeleteOnFailure"},
                    {"Variable": "$.created.status", "StringEquals": "DELETE_FAILED", "Next": "Fail"},
                ],
                "Default": "WaitForReady",
            },
            "InvokeHarness": {
                "Type": "Task",
                "Resource": lambda_arn,
                "Parameters": {
                    "action": "invoke",
                    "harnessArn.$": "$.created.harnessArn",
                    "message.$": "$.message",
                    "model.$": "$.model",
                },
                "ResultPath": "$.invokeResult",
                "Next": "DeleteHarness",
            },
            "DeleteHarness": {
                "Type": "Task",
                "Resource": lambda_arn,
                "Parameters": {"action": "delete", "harnessId.$": "$.created.harnessId"},
                "ResultPath": "$.deleteResult",
                "Next": "Done",
            },
            "DeleteOnFailure": {
                "Type": "Task",
                "Resource": lambda_arn,
                "Parameters": {"action": "delete", "harnessId.$": "$.created.harnessId"},
                "ResultPath": "$.deleteResult",
                "Next": "Fail",
            },
            "Done": {"Type": "Succeed"},
            "Fail": {"Type": "Fail", "Error": "HarnessNotReady", "Cause": "Harness did not reach READY"},
        },
    }


# ---------------------------------------------------------------------------
# Provisioning helpers
# ---------------------------------------------------------------------------
def create_lambda_role(iam, account_id, role_name, harness_role_arn):
    """Role the Lambda assumes: logs + agentcore lifecycle/invoke + passrole + model invoke."""
    trust = {
        "Version": "2012-10-17",
        "Statement": [
            {"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}
        ],
    }
    arn = _ensure_role(iam, role_name, trust)
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "Logs",
                "Effect": "Allow",
                "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                "Resource": "*",
            },
            {
                "Sid": "HarnessLifecycle",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:CreateHarness",
                    "bedrock-agentcore:GetHarness",
                    "bedrock-agentcore:DeleteHarness",
                    "bedrock-agentcore:InvokeHarness",
                    # Creating/Getting/Deleting a Harness provisions an underlying
                    # AgentRuntime, so the matching runtime actions are required too.
                    "bedrock-agentcore:CreateAgentRuntime",
                    "bedrock-agentcore:GetAgentRuntime",
                    "bedrock-agentcore:DeleteAgentRuntime",
                    "bedrock-agentcore:UpdateAgentRuntime",
                ],
                "Resource": "*",
            },
            {"Sid": "PassExecutionRole", "Effect": "Allow", "Action": "iam:PassRole", "Resource": harness_role_arn},
        ],
    }
    iam.put_role_policy(RoleName=role_name, PolicyName="LambdaHarnessPolicy", PolicyDocument=json.dumps(policy))
    return arn


def create_sfn_role(iam, role_name, lambda_arn):
    """Role Step Functions assumes: permission to invoke the task Lambda."""
    trust = {
        "Version": "2012-10-17",
        "Statement": [
            {"Effect": "Allow", "Principal": {"Service": "states.amazonaws.com"}, "Action": "sts:AssumeRole"}
        ],
    }
    arn = _ensure_role(iam, role_name, trust)
    policy = {
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow", "Action": "lambda:InvokeFunction", "Resource": lambda_arn}],
    }
    iam.put_role_policy(RoleName=role_name, PolicyName="SfnInvokeLambdaPolicy", PolicyDocument=json.dumps(policy))
    return arn


def _ensure_role(iam, role_name, trust):
    """Create a role (idempotent); return its ARN."""
    try:
        return iam.get_role(RoleName=role_name)["Role"]["Arn"]
    except iam.exceptions.NoSuchEntityException:
        resp = iam.create_role(RoleName=role_name, AssumeRolePolicyDocument=json.dumps(trust))
        return resp["Role"]["Arn"]


def zip_lambda_source():
    """Package the inline Lambda source into an in-memory zip for create_function."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("index.py", LAMBDA_SOURCE)
    buf.seek(0)
    return buf.read()


def create_task_lambda(lam, fn_name, role_arn):
    """Deploy the task Lambda, retrying while IAM role propagation settles."""
    code = zip_lambda_source()
    deadline = time.monotonic() + 60
    while True:
        try:
            resp = lam.create_function(
                FunctionName=fn_name,
                Runtime=LAMBDA_RUNTIME,
                Role=role_arn,
                Handler=LAMBDA_HANDLER,
                Code={"ZipFile": code},
                Timeout=LAMBDA_TIMEOUT,
                MemorySize=256,
            )
            return resp["FunctionArn"]
        except lam.exceptions.InvalidParameterValueException:
            # Role not yet assumable by Lambda — wait and retry.
            if time.monotonic() > deadline:
                raise
            time.sleep(5)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(args=None):
    if args is None:
        args = parser.parse_args()

    iam = boto3.client("iam")
    lam = boto3.client("lambda", region_name=REGION)
    sfn = boto3.client("stepfunctions", region_name=REGION)
    account_id = boto3.client("sts").get_caller_identity()["Account"]

    suffix = uuid.uuid4().hex[:8]
    lambda_name = f"harness-task-{suffix}"
    lambda_role_name = f"HarnessSfnLambdaRole-{suffix}"
    sfn_role_name = f"HarnessSfnRole-{suffix}"
    state_machine_name = f"HarnessLifecycle-{suffix}"

    lambda_arn = None
    state_machine_arn = None
    created_roles = []

    try:
        # ── Step 0: IAM — Harness execution role ──────────────────────
        print("=" * 60)
        print("Step 0: IAM roles")
        print("=" * 60)
        if args.role_arn:
            harness_role_arn = args.role_arn
            print(f"  Harness execution role (provided): {harness_role_arn}")
        else:
            harness_role_arn = create_harness_role()

        lambda_role_arn = create_lambda_role(iam, account_id, lambda_role_name, harness_role_arn)
        created_roles.append((lambda_role_name, ["LambdaHarnessPolicy"]))
        print(f"  Lambda role: {lambda_role_arn}")

        print("  Waiting for IAM propagation...")
        time.sleep(10)

        # ── Step 1: Deploy the task Lambda ────────────────────────────
        print("\n" + "=" * 60)
        print("Step 1: Deploy task Lambda")
        print("=" * 60)
        lambda_arn = create_task_lambda(lam, lambda_name, lambda_role_arn)
        print(f"  Lambda ARN: {lambda_arn}")

        sfn_role_arn = create_sfn_role(iam, sfn_role_name, lambda_arn)
        created_roles.append((sfn_role_name, ["SfnInvokeLambdaPolicy"]))
        print(f"  Step Functions role: {sfn_role_arn}")
        time.sleep(10)

        # ── Step 2: Create the state machine ──────────────────────────
        print("\n" + "=" * 60)
        print("Step 2: Create state machine")
        print("=" * 60)
        definition = build_definition(lambda_arn)
        resp = _create_state_machine(sfn, state_machine_name, definition, sfn_role_arn)
        state_machine_arn = resp["stateMachineArn"]
        print(f"  State machine ARN: {state_machine_arn}")

        # ── Step 3: Start an execution ────────────────────────────────
        print("\n" + "=" * 60)
        print("Step 3: Start execution")
        print("=" * 60)
        execution_input = {
            "harnessName": f"SfnHarness_{suffix}",
            "executionRoleArn": harness_role_arn,
            "message": args.message,
            "model": args.model,
        }
        exec_resp = sfn.start_execution(
            stateMachineArn=state_machine_arn,
            name=f"run-{uuid.uuid4().hex[:8]}",
            input=json.dumps(execution_input),
        )
        execution_arn = exec_resp["executionArn"]
        print(f"  Execution ARN: {execution_arn}")
        print(f"  Message: {args.message}\n")

        result = poll_execution(sfn, execution_arn)

        # ── Step 4: Show the agent's answer ───────────────────────────
        print("\n" + "=" * 60)
        print("Step 4: Result")
        print("=" * 60)
        status = result["status"]
        print(f"  Execution status: {status}")
        if status == "SUCCEEDED":
            output = json.loads(result["output"])
            answer = output.get("invokeResult", {}).get("text", "")
            print(f"\n  Agent answer:\n  {answer}\n")
        else:
            print(f"  {result.get('error')}: {result.get('cause')}")

        print("=" * 60)
        print("Done!")
        print("=" * 60)

    finally:
        if not args.skip_cleanup:
            print("\nCleaning up...")
            _cleanup(iam, lam, sfn, state_machine_arn, lambda_name, created_roles)
        else:
            print("\n--skip-cleanup set — leaving state machine, Lambda, and roles in place.")


def _create_state_machine(sfn, name, definition, role_arn):
    """Create the STANDARD state machine, retrying while the SFN role propagates."""
    deadline = time.monotonic() + 60
    while True:
        try:
            return sfn.create_state_machine(
                name=name,
                definition=json.dumps(definition),
                roleArn=role_arn,
                type="STANDARD",
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


def _cleanup(iam, lam, sfn, state_machine_arn, lambda_name, created_roles):
    """Delete the state machine, Lambda, and IAM roles. Best-effort."""
    if state_machine_arn:
        try:
            sfn.delete_state_machine(stateMachineArn=state_machine_arn)
            print(f"  Deleted state machine: {state_machine_arn}")
        except Exception as e:
            print(f"  Warning: failed to delete state machine: {e}")

    try:
        lam.delete_function(FunctionName=lambda_name)
        print(f"  Deleted Lambda: {lambda_name}")
    except Exception as e:
        print(f"  Warning: failed to delete Lambda: {e}")

    for role_name, policies in created_roles:
        for policy_name in policies:
            try:
                iam.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
            except Exception:
                pass
        try:
            iam.delete_role(RoleName=role_name)
            print(f"  Deleted role: {role_name}")
        except Exception as e:
            print(f"  Warning: failed to delete role {role_name}: {e}")


if __name__ == "__main__":
    main()
