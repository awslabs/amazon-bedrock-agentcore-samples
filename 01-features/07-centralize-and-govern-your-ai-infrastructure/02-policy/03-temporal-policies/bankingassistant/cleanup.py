# /// script
# requires-python = ">=3.10"
# dependencies = ["boto3"]
# ///
"""
Tear down everything setup.py created for the banking assistant temporal
policies sample: all policies (base permits + temporal), the policy engine,
both Lambda targets, the gateway, the gateway IAM role, and the Lambda
functions.

Resource IDs are read from setup_config.json. The script is idempotent;
resources that are already gone are skipped.

Usage:
    uv run cleanup.py              # delete the sample's own resources
    uv run cleanup.py --cognito    # also delete the shared Cognito stack

Optional environment variables:
    REGION               - AWS region (default: us-east-1)
    COGNITO_STACK_NAME   - Cognito stack to delete with --cognito
                           (default: agentcore-gateway-lab)
"""

import argparse
import json
import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

REGION = os.environ.get("REGION", "us-east-1")
GATEWAY_ROLE_NAME = "banking-gateway-role"
GATEWAY_ROLE_POLICY = "GatewayExecutionPolicy"
LAMBDA_FUNCTIONS = ["banking-tools", "portfolio-tools"]
CONFIG_FILE = Path(__file__).parent / "setup_config.json"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------


def delete_all_policies(ctrl, engine_id: str) -> None:
    """Delete every policy on the engine (base permits and temporal alike)."""
    try:
        paginator_input = {"policyEngineId": engine_id, "maxResults": 50}
        names: list[tuple[str, str]] = []
        while True:
            resp = ctrl.list_policies(**paginator_input)
            for p in resp.get("policies", []):
                names.append((p["policyId"], p.get("name", p["policyId"])))
            token = resp.get("nextToken")
            if not token:
                break
            paginator_input["nextToken"] = token
    except ClientError as e:
        print(f"  Could not list policies: {e}")
        return

    if not names:
        print("  No policies to delete.")
        return

    for policy_id, name in names:
        try:
            ctrl.delete_policy(policyEngineId=engine_id, policyId=policy_id)
            print(f"  Deleted policy: {name}")
        except ClientError as e:
            print(f"  FAILED to delete {name}: {e}")


def delete_engine(ctrl, engine_id: str) -> None:
    try:
        ctrl.delete_policy_engine(policyEngineId=engine_id)
        print(f"  Deleted policy engine: {engine_id}")
    except ClientError as e:
        if e.response["Error"]["Code"] in ("ResourceNotFoundException", "NotFound"):
            print(f"  Policy engine already gone: {engine_id}")
        else:
            print(f"  FAILED to delete policy engine: {e}")


# ---------------------------------------------------------------------------
# Gateway and targets
# ---------------------------------------------------------------------------


def delete_targets(ctrl, gateway_id: str, cfg: dict) -> None:
    target_ids = [cfg[k] for k in cfg if k.startswith("target_id_") and cfg[k]]
    if not target_ids:
        # Fall back to listing if the config has no target IDs recorded.
        try:
            resp = ctrl.list_gateway_targets(
                gatewayIdentifier=gateway_id, maxResults=50
            )
            target_ids = [t["targetId"] for t in resp.get("items", [])]
        except ClientError as e:
            print(f"  Could not list targets: {e}")
            return

    for target_id in target_ids:
        try:
            ctrl.delete_gateway_target(gatewayIdentifier=gateway_id, targetId=target_id)
            print(f"  Deleted gateway target: {target_id}")
        except ClientError as e:
            if e.response["Error"]["Code"] in (
                "ResourceNotFoundException",
                "NotFound",
            ):
                print(f"  Target already gone: {target_id}")
            else:
                print(f"  FAILED to delete target {target_id}: {e}")


def delete_gateway(ctrl, gateway_id: str) -> None:
    try:
        ctrl.delete_gateway(gatewayIdentifier=gateway_id)
        print(f"  Deleted gateway: {gateway_id}")
    except ClientError as e:
        if e.response["Error"]["Code"] in ("ResourceNotFoundException", "NotFound"):
            print(f"  Gateway already gone: {gateway_id}")
        else:
            print(f"  FAILED to delete gateway: {e}")


# ---------------------------------------------------------------------------
# IAM and Lambda
# ---------------------------------------------------------------------------


def delete_gateway_role(iam) -> None:
    try:
        iam.delete_role_policy(
            RoleName=GATEWAY_ROLE_NAME, PolicyName=GATEWAY_ROLE_POLICY
        )
        print(f"  Deleted inline policy: {GATEWAY_ROLE_POLICY}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchEntity":
            print(f"  FAILED to delete inline policy: {e}")

    try:
        iam.delete_role(RoleName=GATEWAY_ROLE_NAME)
        print(f"  Deleted gateway role: {GATEWAY_ROLE_NAME}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            print(f"  Gateway role already gone: {GATEWAY_ROLE_NAME}")
        else:
            print(f"  FAILED to delete gateway role: {e}")


def delete_lambdas(lam) -> None:
    for name in LAMBDA_FUNCTIONS:
        try:
            lam.delete_function(FunctionName=name)
            print(f"  Deleted Lambda function: {name}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                print(f"  Lambda already gone: {name}")
            else:
                print(f"  FAILED to delete Lambda {name}: {e}")


def delete_cognito_stack(cfn, stack_name: str) -> None:
    try:
        cfn.delete_stack(StackName=stack_name)
        print(f"  Delete initiated for Cognito stack: {stack_name}")
    except ClientError as e:
        print(f"  FAILED to delete Cognito stack: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tear down the banking assistant sample"
    )
    parser.add_argument(
        "--cognito",
        action="store_true",
        help="Also delete the shared Cognito stack (only if no other lab needs it)",
    )
    args = parser.parse_args()

    cfg = load_config()
    if not cfg:
        print(
            "No setup_config.json found; nothing to clean up. "
            "Run setup.py first, or delete resources manually.",
            file=sys.stderr,
        )

    session = boto3.Session(region_name=REGION)
    ctrl = session.client("bedrock-agentcore-control", region_name=REGION)
    iam = session.client("iam")
    lam = session.client("lambda", region_name=REGION)

    print("=== Banking Assistant — Cleanup ===\n")

    engine_id = cfg.get("engine_id")
    gateway_id = cfg.get("gateway_id")

    print("Step 1: Policies")
    if engine_id:
        delete_all_policies(ctrl, engine_id)
    else:
        print("  No engine_id in config (skipped)")

    print("\nStep 2: Gateway targets")
    if gateway_id:
        delete_targets(ctrl, gateway_id, cfg)
    else:
        print("  No gateway_id in config (skipped)")

    print("\nStep 3: Policy engine")
    if engine_id:
        delete_engine(ctrl, engine_id)
    else:
        print("  No engine_id in config (skipped)")

    print("\nStep 4: Gateway")
    if gateway_id:
        delete_gateway(ctrl, gateway_id)
    else:
        print("  No gateway_id in config (skipped)")

    print("\nStep 5: Gateway IAM role")
    delete_gateway_role(iam)

    print("\nStep 6: Lambda functions")
    delete_lambdas(lam)

    if args.cognito:
        stack_name = os.environ.get("COGNITO_STACK_NAME", "agentcore-gateway-lab")
        print(f"\nStep 7: Cognito stack ({stack_name})")
        cfn = session.client("cloudformation", region_name=REGION)
        delete_cognito_stack(cfn, stack_name)

    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
        print(f"\nRemoved {CONFIG_FILE.name}")

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
