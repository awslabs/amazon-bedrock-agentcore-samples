"""
Clean up all AWS resources created by deploy.py.

Reads config.json to identify and delete:
  1. Cedar policies and policy engine
  2. Gateway targets and Gateway
  3. Lambda functions and execution role
  4. Cognito app clients, resource server, domain, and User Pool

Usage:
    python cleanup.py [--region REGION]
"""

import argparse
import json
import logging
import time
from pathlib import Path

import boto3

CONFIG_FILE = Path(__file__).parent / "config.json"
LAMBDA_ROLE_NAME = "MultiTenantIsolationDemoLambdaRole"

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


def load_config():
    if not CONFIG_FILE.exists():
        raise FileNotFoundError("config.json not found. Nothing to clean up.")
    return json.loads(CONFIG_FILE.read_text())


def cleanup_policy_engine(control, config):
    """Delete Cedar policies and policy engine."""
    log.info("\n[Step 1] Cleaning up Policy Engine...")
    policy_info = config.get("policy_engine", {})
    engine_id = policy_info.get("engine_id")

    if not engine_id:
        log.info("  No engine_id in config, skipping.")
        return

    # Delete policies first
    for policy_id in policy_info.get("policy_ids", []):
        try:
            control.delete_policy(policyEngineId=engine_id, policyId=policy_id)
            log.info(f"  Deleted policy: {policy_id}")
            time.sleep(2)
        except Exception as e:
            log.info(f"  Policy cleanup ({policy_id}): {e}")

    # Wait for policies to be fully deleted
    time.sleep(5)

    try:
        control.delete_policy_engine(policyEngineId=engine_id)
        log.info(f"  Deleted policy engine: {engine_id}")
    except Exception as e:
        log.info(f"  Policy engine cleanup: {e}")


def cleanup_gateway(control, config):
    """Delete Gateway targets and Gateway."""
    log.info("\n[Step 2] Cleaning up Gateway...")
    gateway_info = config.get("gateway", {})
    gateway_id = gateway_info.get("gateway_id")

    if not gateway_id:
        log.info("  No gateway_id in config, skipping.")
        return

    # Delete targets
    try:
        targets = control.list_gateway_targets(gatewayIdentifier=gateway_id)
        for t in targets.get("items", []):
            control.delete_gateway_target(gatewayIdentifier=gateway_id, targetId=t["targetId"])
            log.info(f"  Deleted target: {t['name']}")
            time.sleep(2)
        time.sleep(5)
    except Exception as e:
        log.info(f"  Targets cleanup: {e}")

    # Delete gateway
    try:
        control.delete_gateway(gatewayIdentifier=gateway_id)
        log.info(f"  Deleted gateway: {gateway_id}")
    except Exception as e:
        log.info(f"  Gateway cleanup: {e}")


def cleanup_lambdas(session, region, config):
    """Delete Lambda functions and IAM role."""
    log.info("\n[Step 3] Cleaning up Lambda functions...")
    lam = session.client("lambda", region_name=region)
    iam = session.client("iam", region_name=region)

    for target_name, arn in config.get("lambda_arns", {}).items():
        fn_name = arn.split(":")[-1]
        try:
            lam.delete_function(FunctionName=fn_name)
            log.info(f"  Deleted Lambda: {fn_name}")
        except Exception as e:
            log.info(f"  Lambda cleanup ({fn_name}): {e}")

    try:
        iam.detach_role_policy(
            RoleName=LAMBDA_ROLE_NAME,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        )
        iam.delete_role(RoleName=LAMBDA_ROLE_NAME)
        log.info(f"  Deleted IAM role: {LAMBDA_ROLE_NAME}")
    except Exception as e:
        log.info(f"  IAM role cleanup: {e}")


def cleanup_cognito(session, region, config):
    """Delete Cognito User Pool and all related resources."""
    log.info("\n[Step 4] Cleaning up Cognito resources...")
    cognito = session.client("cognito-idp", region_name=region)
    cognito_config = config.get("cognito", {})
    pool_id = cognito_config.get("pool_id")

    if not pool_id:
        log.info("  No pool_id in config, skipping.")
        return

    domain = cognito_config.get("domain")
    if domain:
        try:
            cognito.delete_user_pool_domain(Domain=domain, UserPoolId=pool_id)
            log.info(f"  Deleted domain: {domain}")
            time.sleep(5)
        except Exception as e:
            log.info(f"  Domain cleanup: {e}")

    try:
        cognito.delete_user_pool(UserPoolId=pool_id)
        log.info(f"  Deleted User Pool: {pool_id}")
    except Exception as e:
        log.info(f"  User Pool cleanup: {e}")


def main():
    parser = argparse.ArgumentParser(description="Clean up multi-tenant isolation demo")
    parser.add_argument("--region", help="AWS region (override)", default=None)
    args = parser.parse_args()

    config = load_config()
    region = args.region or config.get("region")
    session = boto3.Session(region_name=region)
    control = session.client("bedrock-agentcore-control")

    log.info("Cleaning up multi-tenant isolation demo resources...")

    cleanup_gateway(control, config)
    cleanup_policy_engine(control, config)
    cleanup_lambdas(session, region, config)
    cleanup_cognito(session, region, config)

    CONFIG_FILE.unlink()
    log.info(f"\nDeleted {CONFIG_FILE}")
    log.info("\nCleanup complete.")


if __name__ == "__main__":
    main()
