#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""
CLI for managing the Amazon Bedrock AgentCore Runtime for role-based-hr-data-agent.

Usage:
  python scripts/agentcore_agent_runtime.py create --s3-bucket <bucket>
  python scripts/agentcore_agent_runtime.py delete --runtime-id <id>

The create command reads infrastructure config from SSM (populated by prereq.sh
and agentcore_gateway.py) so no manual ARN/URL entry is needed.
"""

import json
import sys
import time

import boto3
import click

from scripts.utils import get_ssm_parameter, put_ssm_parameter

RUNTIME_NAME = "hr_data_agent_runtime"
ENTRY_POINT = "main.py"
RUNTIME_LANG = "PYTHON_3_11"
S3_KEY = "hr-data-agent/runtime.zip"


@click.group()
def cli():
    """Manage the AgentCore Runtime for the HR Data Agent."""


@cli.command()
@click.option("--s3-bucket", default=None,
              help="S3 bucket holding runtime.zip (reads /app/hrdlp/deploy-bucket from SSM if omitted)")
@click.option("--name", default=RUNTIME_NAME, show_default=True,
              help="AgentCore Runtime name")
@click.option("--region", default="us-east-1", show_default=True)
def create(s3_bucket: str, name: str, region: str):
    """Create the AgentCore Runtime and store its ID + URL in SSM.

    Prerequisites (all populated by prereq.sh + agentcore_gateway.py):
      - /app/hrdlp/runtime-role-arn    — Runtime execution role
      - /app/hrdlp/gateway-url         — Gateway MCP endpoint
      - /app/hrdlp/cognito-user-pool-id — Cognito User Pool for JWT authorizer
      - /app/hrdlp/deploy-bucket        — S3 bucket (or pass --s3-bucket)

    Upload the runtime package first:
      bash scripts/prereq.sh                   # builds hr-data-agent/runtime.zip
      OR: aws s3 cp dist/runtime.zip s3://<bucket>/hr-data-agent/runtime.zip
    """
    # Resolve S3 bucket
    bucket = s3_bucket or get_ssm_parameter("/app/hrdlp/deploy-bucket")
    if not bucket:
        click.echo(
            "ERROR: --s3-bucket not provided and /app/hrdlp/deploy-bucket not in SSM.\n"
            "Run prereq.sh first or pass --s3-bucket <bucket>.",
            err=True,
        )
        sys.exit(1)

    # Read required SSM parameters
    role_arn = get_ssm_parameter("/app/hrdlp/runtime-role-arn")
    gateway_url = get_ssm_parameter("/app/hrdlp/gateway-url")
    user_pool_id = get_ssm_parameter("/app/hrdlp/cognito-user-pool-id")

    missing = [k for k, v in {
        "/app/hrdlp/runtime-role-arn": role_arn,
        "/app/hrdlp/gateway-url": gateway_url,
        "/app/hrdlp/cognito-user-pool-id": user_pool_id,
    }.items() if not v]
    if missing:
        click.echo(f"ERROR: Missing SSM parameters: {missing}\nRun prereq.sh and agentcore_gateway.py first.", err=True)
        sys.exit(1)

    # Collect persona client IDs for JWT authorizer allowedClients
    persona_client_ids = [
        cid for cid in [
            get_ssm_parameter(f"/app/hrdlp/personas/{p}/client-id")
            for p in ["hr-manager", "hr-specialist", "employee", "admin"]
        ] if cid
    ]
    if not persona_client_ids:
        click.echo("ERROR: No persona client IDs found in SSM. Run cognito_credentials_provider.py create first.", err=True)
        sys.exit(1)

    # Build JWT authorizer from Cognito User Pool
    discovery_url = (
        f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
        "/.well-known/openid-configuration"
    )

    client = boto3.client("bedrock-agentcore-control", region_name=region)
    click.echo(f"Creating AgentCore Runtime: {name}")
    click.echo(f"  S3 artifact : s3://{bucket}/{S3_KEY}")
    click.echo(f"  Role        : {role_arn}")
    click.echo(f"  Gateway URL : {gateway_url}")

    try:
        resp = client.create_agent_runtime(
            agentRuntimeName=name,
            description="Role-based HR data agent with field-level DLP via AgentCore Gateway",
            agentRuntimeArtifact={
                "codeConfiguration": {
                    "code": {"s3": {"bucket": bucket, "prefix": S3_KEY}},
                    "runtime": RUNTIME_LANG,
                    "entryPoint": [ENTRY_POINT],
                }
            },
            roleArn=role_arn,
            networkConfiguration={"networkMode": "PUBLIC"},
            environmentVariables={"GATEWAY_URL": gateway_url, "AWS_DEFAULT_REGION": region},
            authorizerConfiguration={
                "customJWTAuthorizer": {
                    "discoveryUrl": discovery_url,
                    "allowedClients": persona_client_ids,
                }
            },
            requestHeaderConfiguration={
                "requestHeaderAllowlist": ["Authorization"]
            },
        )

        runtime_id = resp["agentRuntimeId"]
        click.echo(f"Runtime created: {runtime_id}")

        # Wait for READY
        endpoint_url = _wait_for_runtime(client, runtime_id)

        # Build ARN-based invocation URL — required when runtime name contains underscores,
        # since DNS hostnames don't allow underscores.
        import urllib.parse
        account_id = boto3.client("sts").get_caller_identity()["Account"]
        runtime_arn = f"arn:aws:bedrock-agentcore:{region}:{account_id}:runtime/{runtime_id}"
        encoded_arn = urllib.parse.quote(runtime_arn, safe="")
        endpoint_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations"

        # Persist to SSM
        put_ssm_parameter("/app/hrdlp/runtime-id", runtime_id)
        put_ssm_parameter("/app/hrdlp/runtime-url", endpoint_url)

        click.echo(f"\nRuntime ID  : {runtime_id}")
        click.echo(f"Endpoint URL: {endpoint_url}")
        click.echo("SSM parameters updated.")

    except Exception as e:
        click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--runtime-id", default=None,
              help="Runtime ID (reads from SSM /app/hrdlp/runtime-id if omitted)")
@click.option("--region", default="us-east-1", show_default=True)
def delete(runtime_id: str, region: str):
    """Delete the AgentCore Runtime."""
    runtime_id = runtime_id or get_ssm_parameter("/app/hrdlp/runtime-id")
    if not runtime_id:
        click.echo("ERROR: runtime-id not provided and not found in SSM.", err=True)
        sys.exit(1)

    client = boto3.client("bedrock-agentcore-control", region_name=region)
    click.echo(f"Deleting runtime: {runtime_id}")
    try:
        client.delete_agent_runtime(agentRuntimeId=runtime_id)
        click.echo("Runtime deleted.")
    except Exception as e:
        click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)


def _wait_for_runtime(client, runtime_id: str, max_attempts: int = 30) -> str:
    """Poll until runtime is READY; return endpoint URL."""
    for _ in range(max_attempts):
        time.sleep(10)
        resp = client.get_agent_runtime(agentRuntimeId=runtime_id)
        status = resp.get("status")
        endpoint = resp.get("agentRuntimeEndpoint", "")
        click.echo(f"  Runtime status: {status}")
        if status == "READY":
            return endpoint
        if status in ("FAILED", "DELETING"):
            raise RuntimeError(f"Runtime reached terminal status: {status}")
    raise TimeoutError("Timed out waiting for Runtime to become READY")


if __name__ == "__main__":
    cli()
