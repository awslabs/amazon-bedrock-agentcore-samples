#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Post-deploy: create Cedar policies in the PolicyEngine via boto3.

The CfnPolicy CloudFormation resource handler has stabilization issues,
so policies are managed via the API instead.

Action names use the {target}___{tool} format per AgentCore Cedar schema.

Usage:
    python scripts/create-policies.py --region us-east-1

Reads PolicyEngineId from the OpenCodePolicy CloudFormation stack outputs and
GatewayArn from the OpenCodeGateway CloudFormation stack outputs.
"""

import argparse
import time

import boto3


def _get_stack_outputs(cfn_client, stack_name: str) -> dict[str, str]:
    """Return {OutputKey: OutputValue} for a CloudFormation stack."""
    resp = cfn_client.describe_stacks(StackName=stack_name)
    outputs = resp["Stacks"][0].get("Outputs", [])
    return {o["OutputKey"]: o["OutputValue"] for o in outputs}


def _policy_exists_active(client, engine_id: str, name: str) -> bool:
    """Check if a policy with the given name already exists and is ACTIVE."""
    paginator = client.get_paginator("list_policies")
    for page in paginator.paginate(policyEngineId=engine_id):
        for policy in page.get("policies", []):
            if policy.get("name") == name and policy.get("status") == "ACTIVE":
                return True
    return False


def _cleanup_failed(client, engine_id: str) -> None:
    """Delete any policies in FAILED state."""
    paginator = client.get_paginator("list_policies")
    for page in paginator.paginate(policyEngineId=engine_id):
        for policy in page.get("policies", []):
            if "FAILED" in policy.get("status", ""):
                print(f"  Deleting failed policy: {policy['name']} ({policy['policyId']})")
                client.delete_policy(policyEngineId=engine_id, policyId=policy["policyId"])
                time.sleep(1)


def _create_policy(client, engine_id: str, name: str, statement: str, description: str) -> None:
    """Create a Cedar policy and wait for it to become ACTIVE."""
    if _policy_exists_active(client, engine_id, name):
        print(f"  Policy '{name}' already ACTIVE — skipping.")
        return

    resp = client.create_policy(
        policyEngineId=engine_id,
        name=name,
        description=description,
        validationMode="IGNORE_ALL_FINDINGS",
        definition={"cedar": {"statement": statement}},
    )
    policy_id = resp["policyId"]
    print(f"  Created policy '{name}' (id={policy_id}), waiting for ACTIVE...")

    for _ in range(30):
        time.sleep(2)
        p = client.get_policy(policyEngineId=engine_id, policyId=policy_id)
        status = p["status"]
        if status == "ACTIVE":
            print(f"  Policy '{name}' is ACTIVE.")
            return
        if "FAILED" in status:
            reasons = p.get("statusReasons", ["unknown"])
            raise RuntimeError(f"Policy '{name}' FAILED: {reasons}")
    raise TimeoutError(f"Policy '{name}' did not become ACTIVE within 60s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create Cedar policies post-deploy")
    parser.add_argument("--region", required=True)
    args = parser.parse_args()

    cfn = boto3.client("cloudformation", region_name=args.region)
    agentcore = boto3.client("bedrock-agentcore-control", region_name=args.region)

    outputs = _get_stack_outputs(cfn, "OpenCodePolicy")
    engine_id = outputs["PolicyEngineId"]
    gateway_outputs = _get_stack_outputs(cfn, "OpenCodeGateway")
    gateway_arn = gateway_outputs["GatewayArn"]

    print(f"PolicyEngine: {engine_id}")
    print(f"Gateway ARN:  {gateway_arn}")

    # Clean up any failed policies from previous attempts
    print("\nCleaning up failed policies...")
    _cleanup_failed(agentcore, engine_id)
    time.sleep(3)

    # Action names use {target}___{tool} format
    # Target name is "opencode" (from create-gateway-mcp-targets.py)
    print("\nCreating Cedar policies...")

    _create_policy(
        agentcore,
        engine_id,
        name="opencode_readonly_deny_coding",
        statement=(
            "forbid(\n"
            "  principal,\n"
            '  action == AgentCore::Action::"opencode___run_coding_task",\n'
            f'  resource == AgentCore::Gateway::"{gateway_arn}"\n'
            ") when {\n"
            '  principal.hasTag("role") && principal.getTag("role") == "readonly"\n'
            "};"
        ),
        description="Deny run_coding_task for readonly role",
    )

    _create_policy(
        agentcore,
        engine_id,
        name="opencode_readonly_deny_cancel",
        statement=(
            "forbid(\n"
            "  principal,\n"
            '  action == AgentCore::Action::"opencode___cancel_task",\n'
            f'  resource == AgentCore::Gateway::"{gateway_arn}"\n'
            ") when {\n"
            '  principal.hasTag("role") && principal.getTag("role") == "readonly"\n'
            "};"
        ),
        description="Deny cancel_task for readonly role",
    )

    print("\nAll policies created successfully.")


if __name__ == "__main__":
    main()
