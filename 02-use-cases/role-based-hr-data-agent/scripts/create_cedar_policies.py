#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""
Creates the Cedar Policy Engine, attaches it to the Amazon Bedrock AgentCore Gateway,
and creates the three HR DLP authorization policies.

This must run AFTER agentcore_gateway.py create (needs gateway-id, gateway-arn,
gateway-url, gateway-role-arn, cognito-user-pool-id, request/response interceptor ARNs
in SSM, and persona client IDs).

Usage:
  python scripts/create_cedar_policies.py --region us-east-1 --env dev
  python scripts/create_cedar_policies.py --mode ENFORCE   # switch to enforcement
"""

import json
import time

import boto3
import click

from scripts.utils import get_ssm_parameter, put_ssm_parameter

# Cedar policies reference the gateway ARN and tool action names in the format:
#   <target-name>___<tool-name>
POLICIES = [
    {
        "name": "allow_search_employee",
        "description": "Allow search_employee for users with hr-dlp-gateway/read scope",
        "statement": (
            'permit(principal is AgentCore::OAuthUser, '
            'action == AgentCore::Action::"hr-lambda-target___search_employee", '
            'resource == AgentCore::Gateway::"{gateway_arn}") '
            'when {{ principal.hasTag("scope") && principal.getTag("scope") like "*hr-dlp-gateway/read*" }};'
        ),
    },
    {
        "name": "allow_get_employee_profile",
        "description": "Allow get_employee_profile for users with hr-dlp-gateway/pii scope",
        "statement": (
            'permit(principal is AgentCore::OAuthUser, '
            'action == AgentCore::Action::"hr-lambda-target___get_employee_profile", '
            'resource == AgentCore::Gateway::"{gateway_arn}") '
            'when {{ principal.hasTag("scope") && principal.getTag("scope") like "*hr-dlp-gateway/pii*" }};'
        ),
    },
    {
        "name": "allow_get_employee_compensation",
        "description": "Allow get_employee_compensation for users with hr-dlp-gateway/comp scope",
        "statement": (
            'permit(principal is AgentCore::OAuthUser, '
            'action == AgentCore::Action::"hr-lambda-target___get_employee_compensation", '
            'resource == AgentCore::Gateway::"{gateway_arn}") '
            'when {{ principal.hasTag("scope") && principal.getTag("scope") like "*hr-dlp-gateway/comp*" }};'
        ),
    },
]


_CEDAR_INIT_WAIT = 15   # seconds to let Cedar schema finish indexing after gateway READY
_MAX_POLICY_ATTEMPTS = 3  # retries per real policy on transient internal errors
_POLICY_RETRY_WAIT = 30   # seconds between policy retries


def _poll_policy_status(client, engine_id, policy_id, polls=12, interval=5):
    """Poll until policy leaves CREATING. Returns (status, statusReasons) tuple."""
    for _ in range(polls):
        time.sleep(interval)
        resp = client.get_policy(policyEngineId=engine_id, policyId=policy_id)
        status = resp["status"]
        if status != "CREATING":
            return status, resp.get("statusReasons", [])
    return "CREATING", []


def _create_policy_with_retry(client, engine_id, gateway_arn, policy_def):
    """
    Create a single Cedar policy, retrying only on transient internal errors.
    Validation failures (Overly Permissive, schema errors) are non-retriable
    and abort immediately with the full reason from the service.
    """
    statement = policy_def["statement"].format(gateway_arn=gateway_arn)
    definition = {"cedar": {"statement": statement}}

    for attempt in range(1, _MAX_POLICY_ATTEMPTS + 1):
        try:
            resp = client.create_policy(
                policyEngineId=engine_id,
                name=policy_def["name"],
                description=policy_def["description"],
                definition=definition,
            )
            policy_id = resp["policyId"]
        except client.exceptions.ConflictException:
            # Policy with this name already exists — find and reuse it
            policies = client.list_policies(policyEngineId=engine_id).get("policies", [])
            existing = next((p for p in policies if p["name"] == policy_def["name"]), None)
            if not existing:
                click.echo(
                    f"ERROR: ConflictException but could not find existing policy '{policy_def['name']}'.",
                    err=True,
                )
                raise SystemExit(1)
            click.echo(f"  Policy '{policy_def['name']}' already exists, reusing: {existing['policyId']}")
            return existing["policyId"]

        click.echo(
            f"  Creating: {policy_def['name']} ({policy_id})"
            + (f" [attempt {attempt}/{_MAX_POLICY_ATTEMPTS}]" if attempt > 1 else "")
            + " — waiting for ACTIVE..."
        )

        status, reasons = _poll_policy_status(client, engine_id, policy_id)

        if status == "ACTIVE":
            click.echo(f"  ACTIVE: {policy_def['name']}")
            return policy_id

        if status == "CREATE_FAILED":
            # Determine if this is a validation failure (non-retriable) or a
            # transient internal error (retriable). Validation failures contain
            # descriptive reasons (e.g. "Overly Permissive"); internal errors
            # say "An internal error occurred during creation".
            is_internal = any(
                "internal error" in r.lower() for r in reasons
            ) or not reasons

            try:
                client.delete_policy(policyEngineId=engine_id, policyId=policy_id)
            except Exception:
                pass

            if not is_internal:
                # Validation failure — retrying won't help
                click.echo(
                    f"ERROR: Policy '{policy_def['name']}' failed validation:\n"
                    + "\n".join(f"  - {r}" for r in reasons),
                    err=True,
                )
                raise SystemExit(1)

            if attempt < _MAX_POLICY_ATTEMPTS:
                click.echo(
                    f"  CREATE_FAILED (internal error) for {policy_def['name']} — "
                    f"retrying in {_POLICY_RETRY_WAIT}s..."
                )
                time.sleep(_POLICY_RETRY_WAIT)
                continue

        # TIMED_OUT or exhausted retries on internal errors
        click.echo(
            f"ERROR: Policy '{policy_def['name']}' failed after "
            f"{attempt} attempt(s) (last status: {status}, reasons: {reasons}). "
            "This is a service-side issue — wait a few minutes and re-run.",
            err=True,
        )
        raise SystemExit(1)


@click.command()
@click.option("--region", default="us-east-1", show_default=True)
@click.option("--env", default="dev", show_default=True, help="Environment suffix for policy engine name")
@click.option("--mode", default="LOG_ONLY", type=click.Choice(["LOG_ONLY", "ENFORCE"]),
              show_default=True, help="Cedar policy enforcement mode")
def create(region: str, env: str, mode: str):
    """
    Create the Cedar Policy Engine, attach to Gateway, and create HR DLP policies.

    Prerequisites (populated by prereq.sh + agentcore_gateway.py):
      - /app/hrdlp/gateway-id   Gateway identifier
      - /app/hrdlp/gateway-arn  Gateway ARN (for Cedar policy resource)

    All other gateway configuration (authorizer, interceptors, role) is read
    directly from the live gateway via get_gateway — no extra SSM parameters needed.
    """
    gateway_id = get_ssm_parameter("/app/hrdlp/gateway-id")
    gateway_arn = get_ssm_parameter("/app/hrdlp/gateway-arn")

    if not gateway_id or not gateway_arn:
        click.echo("ERROR: Missing /app/hrdlp/gateway-id or /app/hrdlp/gateway-arn in SSM.\nRun prereq.sh and agentcore_gateway.py first.", err=True)
        raise SystemExit(1)

    client = boto3.client("bedrock-agentcore-control", region_name=region)

    # Read current gateway configuration — authorizer, interceptors, role are
    # taken directly from the live gateway instead of being reconstructed from SSM.
    click.echo(f"Reading current gateway configuration: {gateway_id}")
    gw = client.get_gateway(gatewayIdentifier=gateway_id)
    gw_name = gw["name"]
    gw_role_arn = gw["roleArn"]
    gw_protocol = gw["protocolType"]
    gw_authorizer_type = gw["authorizerType"]
    gw_authorizer_config = gw["authorizerConfiguration"]
    gw_interceptors = gw.get("interceptorConfigurations", [])
    click.echo(f"  name={gw_name}  interceptors={len(gw_interceptors)}")

    # -------------------------------------------------------------------------
    # Step 1: Create (or reuse) the policy engine — idempotent
    # -------------------------------------------------------------------------
    engine_name = f"hr_dlp_policies_{env}"
    click.echo(f"Creating policy engine: {engine_name}")
    try:
        resp = client.create_policy_engine(
            name=engine_name,
            description=f"Cedar authorization policies for HR DLP Gateway ({env})",
        )
        engine_id = resp["policyEngineId"]
        click.echo(f"  Engine ID: {engine_id} — waiting for ACTIVE...")

        for _ in range(12):
            time.sleep(5)
            status = client.get_policy_engine(policyEngineId=engine_id)["status"]
            if status == "ACTIVE":
                break
            if status == "FAILED":
                click.echo("ERROR: Policy engine reached FAILED status.", err=True)
                raise SystemExit(1)
        else:
            click.echo("ERROR: Timed out waiting for policy engine to become ACTIVE.", err=True)
            raise SystemExit(1)

    except client.exceptions.ConflictException:
        # Engine already exists — find it by name and reuse it
        engines = client.list_policy_engines().get("policyEngines", [])
        existing = next((e for e in engines if e["name"] == engine_name), None)
        if not existing:
            click.echo(f"ERROR: ConflictException but could not find existing engine '{engine_name}'.", err=True)
            raise SystemExit(1)
        engine_id = existing["policyEngineId"]
        click.echo(f"  Policy engine already exists, reusing: {engine_id}")

    click.echo(f"  Policy engine ACTIVE: {engine_id}")

    # -------------------------------------------------------------------------
    # Step 2: Attach the engine to the gateway — two-phase update.
    #
    # Phase A: Attach policy engine WITHOUT interceptors.
    # The reference sample (08-AgentCore-policy) never includes interceptors
    # in the update_gateway call that attaches the policy engine. Including them
    # causes Cedar schema initialization to fail with an internal error on every
    # subsequent create_policy call. Attach cleanly first so Cedar can initialize.
    #
    # Phase B: After Cedar is confirmed ready and policies are created, restore
    # the interceptors in a second update_gateway call.
    # -------------------------------------------------------------------------
    click.echo(f"\nAttaching policy engine to gateway (phase A — no interceptors): {gateway_id}")

    account_id = boto3.client("sts").get_caller_identity()["Account"]
    engine_arn = (
        f"arn:aws:bedrock-agentcore:{region}:{account_id}:policy-engine/{engine_id}"
    )

    # Phase A — policy engine only, no interceptors.
    # Strip interceptorConfigurations so Cedar's internal tools/list call (used
    # to index the schema) is not blocked by JWT auth from the interceptors.
    client.update_gateway(
        gatewayIdentifier=gateway_id,
        name=gw_name,
        roleArn=gw_role_arn,
        protocolType=gw_protocol,
        authorizerType=gw_authorizer_type,
        authorizerConfiguration=gw_authorizer_config,
        policyEngineConfiguration={"arn": engine_arn, "mode": mode},
    )
    click.echo("  Waiting for gateway to return to READY...")

    for _ in range(20):
        time.sleep(10)
        gw_status = client.get_gateway(gatewayIdentifier=gateway_id)["status"]
        click.echo(f"  Gateway status: {gw_status}")
        if gw_status == "READY":
            break
        if gw_status == "FAILED":
            click.echo("ERROR: Gateway reached FAILED status after update.", err=True)
            raise SystemExit(1)
    else:
        click.echo("ERROR: Timed out waiting for gateway to become READY.", err=True)
        raise SystemExit(1)

    # -------------------------------------------------------------------------
    # Step 3: Brief wait for Cedar schema to finish indexing.
    # The gateway returns READY before Cedar's internal schema is fully
    # initialized. A short fixed sleep is sufficient; transient failures
    # during policy creation are handled by _create_policy_with_retry.
    # -------------------------------------------------------------------------
    click.echo(f"\nWaiting {_CEDAR_INIT_WAIT}s for Cedar schema to initialize...")
    time.sleep(_CEDAR_INIT_WAIT)

    # -------------------------------------------------------------------------
    # Step 4: Create each Cedar policy.
    # Retries up to _MAX_POLICY_ATTEMPTS times on transient internal errors.
    # Validation failures (Overly Permissive, schema errors) abort immediately.
    # -------------------------------------------------------------------------
    click.echo(f"\nCreating {len(POLICIES)} Cedar policies (mode: {mode})...")

    created_policy_ids = []
    for policy_def in POLICIES:
        policy_id = _create_policy_with_retry(client, engine_id, gateway_arn, policy_def)
        created_policy_ids.append(policy_id)

    # -------------------------------------------------------------------------
    # Step 5: Restore interceptors — phase B of the two-phase gateway update.
    # Now that Cedar is initialized and policies are ACTIVE, re-add the
    # interceptors. Cedar schema is already indexed so this update won't
    # interfere with it.
    # -------------------------------------------------------------------------
    if gw_interceptors:
        click.echo(f"\nRestoring interceptors on gateway (phase B): {gateway_id}")
        client.update_gateway(
            gatewayIdentifier=gateway_id,
            name=gw_name,
            roleArn=gw_role_arn,
            protocolType=gw_protocol,
            authorizerType=gw_authorizer_type,
            authorizerConfiguration=gw_authorizer_config,
            policyEngineConfiguration={"arn": engine_arn, "mode": mode},
            interceptorConfigurations=gw_interceptors,
        )
        click.echo("  Waiting for gateway to return to READY...")
        for _ in range(20):
            time.sleep(10)
            gw_status = client.get_gateway(gatewayIdentifier=gateway_id)["status"]
            click.echo(f"  Gateway status: {gw_status}")
            if gw_status == "READY":
                break
            if gw_status == "FAILED":
                click.echo("ERROR: Gateway reached FAILED status restoring interceptors.", err=True)
                raise SystemExit(1)
        else:
            click.echo("ERROR: Timed out waiting for gateway to become READY.", err=True)
            raise SystemExit(1)
        click.echo("  Interceptors restored.")

    # -------------------------------------------------------------------------
    # Step 6: Persist policy engine ARN to SSM
    # -------------------------------------------------------------------------
    put_ssm_parameter("/app/hrdlp/cedar-policy-engine-arn", engine_arn)

    click.echo(f"\nCedar setup complete.")
    click.echo(f"  Policy engine : {engine_id} ({mode})")
    click.echo(f"  Policies      : {len(created_policy_ids)} ACTIVE")
    click.echo(f"  SSM           : /app/hrdlp/cedar-policy-engine-arn")
    if mode == "LOG_ONLY":
        click.echo("\n  Mode is LOG_ONLY — policies log but do not block requests.")
        click.echo("  To enforce, re-run with: --mode ENFORCE")


if __name__ == "__main__":
    create()
