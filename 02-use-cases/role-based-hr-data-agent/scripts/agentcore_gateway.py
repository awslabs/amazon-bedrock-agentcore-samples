#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""
CLI for creating and deleting the Amazon Bedrock AgentCore Gateway for role-based-hr-data-agent.

Usage:
  python scripts/agentcore_gateway.py create --config prerequisite/prereqs_config.yaml
  python scripts/agentcore_gateway.py delete --gateway-id <id>
"""

import json
import sys
import time

import boto3
import click

from scripts.utils import get_ssm_parameter, put_ssm_parameter, read_config


@click.group()
def cli():
    """Manage the AgentCore Gateway for the HR Data Agent."""


@cli.command()
@click.option("--config", default="prerequisite/prereqs_config.yaml", show_default=True,
              help="Path to prereqs_config.yaml")
@click.option("--region", default=None, help="AWS region (overrides config)")
def create(config: str, region: str):
    """Create the AgentCore MCP Gateway with Lambda target and interceptors."""
    cfg = read_config(config)
    aws_cfg = cfg.get("aws", {})
    gw_cfg = cfg.get("gateway", {})
    region = region or aws_cfg.get("region", "us-east-1")

    lambda_arn = get_ssm_parameter(cfg["ssm_parameters"]["lambda_arn"])
    gateway_role_arn = get_ssm_parameter("/app/hrdlp/gateway-role-arn")
    request_interceptor_arn = get_ssm_parameter("/app/hrdlp/request-interceptor-arn")
    response_interceptor_arn = get_ssm_parameter("/app/hrdlp/response-interceptor-arn")
    user_pool_id = get_ssm_parameter(cfg["ssm_parameters"]["cognito_user_pool_id"])

    # Collect all persona client IDs for the JWT authorizer allowedAudience
    persona_client_ids = [
        cid for cid in [
            get_ssm_parameter(f"/app/hrdlp/personas/{p}/client-id")
            for p in ["hr-manager", "hr-specialist", "employee", "admin"]
        ] if cid
    ]

    if not all([lambda_arn, gateway_role_arn, user_pool_id]):
        click.echo("ERROR: Required SSM parameters missing. Run prereq.sh first.", err=True)
        sys.exit(1)

    if not persona_client_ids:
        click.echo("ERROR: No persona client IDs found in SSM. Run cognito_credentials_provider.py create first.", err=True)
        sys.exit(1)

    client = boto3.client("bedrock-agentcore-control", region_name=region)
    gateway_name = gw_cfg.get("name", "hr-data-agent-gateway")
    target_name = gw_cfg.get("target_name", "hr-lambda-target")

    # Read tool schemas from api_spec.json
    api_spec = read_config("prerequisite/lambda/api_spec.json")
    inline_payload = [
        {
            "name": op["operationId"],
            "description": op.get("summary", ""),
            "inputSchema": list(op["requestBody"]["content"].values())[0]["schema"],
        }
        for path_item in api_spec["paths"].values()
        for op in [list(path_item.values())[0]]
    ]

    # Build authorizer config — allowedClients = all persona client IDs
    discovery_url = (
        f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
        "/.well-known/openid-configuration"
    )
    authorizer_config = {
        "customJWTAuthorizer": {
            "discoveryUrl": discovery_url,
            "allowedClients": persona_client_ids,
        }
    }
    click.echo(f"  Authorizer: {len(persona_client_ids)} persona clients in allowedClients")

    # Build interceptor configurations — passRequestHeaders ensures Authorization header
    # flows through to interceptors so they can decode the JWT for tenant resolution
    interceptor_configs = []
    if request_interceptor_arn:
        interceptor_configs.append({
            "interceptor": {"lambda": {"arn": request_interceptor_arn}},
            "interceptionPoints": ["REQUEST"],
            "inputConfiguration": {"passRequestHeaders": True},
        })
    if response_interceptor_arn:
        interceptor_configs.append({
            "interceptor": {"lambda": {"arn": response_interceptor_arn}},
            "interceptionPoints": ["RESPONSE"],
            "inputConfiguration": {"passRequestHeaders": True},
        })
    click.echo(f"  Interceptors: {len(interceptor_configs)} configured (REQUEST + RESPONSE)")

    click.echo(f"Creating Gateway: {gateway_name} in {region}")

    try:
        create_kwargs = dict(
            name=gateway_name,
            protocolType="MCP",
            roleArn=gateway_role_arn,
            authorizerType="CUSTOM_JWT",
            authorizerConfiguration=authorizer_config,
        )
        if interceptor_configs:
            create_kwargs["interceptorConfigurations"] = interceptor_configs

        resp = client.create_gateway(**create_kwargs)
        gateway_id = resp["gatewayId"]
        gateway_url = resp.get("gatewayUrl", "")
        click.echo(f"Gateway created: {gateway_id}")

        # Wait for READY
        _wait_for_gateway(client, gateway_id)

        # Attach Lambda target — targetConfiguration uses mcp.lambda shape
        client.create_gateway_target(
            gatewayIdentifier=gateway_id,
            name=target_name,
            targetConfiguration={
                "mcp": {
                    "lambda": {
                        "lambdaArn": lambda_arn,
                        "toolSchema": {"inlinePayload": inline_payload},
                    }
                }
            },
            credentialProviderConfigurations=[
                {"credentialProviderType": "GATEWAY_IAM_ROLE"}
            ],
        )
        click.echo(f"Lambda target attached: {target_name}")

        # Construct full Gateway ARN (needed by Cedar policies)
        account_id = boto3.client("sts").get_caller_identity()["Account"]
        gateway_arn = f"arn:aws:bedrock-agentcore:{region}:{account_id}:gateway/{gateway_id}"

        # Persist to SSM
        put_ssm_parameter(cfg["ssm_parameters"]["gateway_id"], gateway_id)
        put_ssm_parameter(cfg["ssm_parameters"]["gateway_url"], gateway_url)
        put_ssm_parameter("/app/hrdlp/gateway-arn", gateway_arn)

        click.echo(f"\nGateway URL: {gateway_url}")
        click.echo(f"Gateway ARN: {gateway_arn}")
        click.echo("SSM parameters updated (/app/hrdlp/gateway-id, gateway-url, gateway-arn).")
        click.echo("\nNext: update Cedar policy with Gateway ARN:")
        click.echo(f"  sed -i 's|<YOUR_GATEWAY_ARN>|{gateway_arn}|g' prerequisite/cedar/hr_dlp_policies.cedar")

    except Exception as e:
        click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--gateway-id", required=True, help="Gateway ID to delete")
@click.option("--region", default="us-east-1", show_default=True)
def delete(gateway_id: str, region: str):
    """Delete the AgentCore Gateway and its targets."""
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    click.echo(f"Deleting gateway: {gateway_id}")
    try:
        # List and delete targets first
        targets = client.list_gateway_targets(gatewayIdentifier=gateway_id).get("items", [])
        for target in targets:
            client.delete_gateway_target(
                gatewayIdentifier=gateway_id, targetId=target["targetId"]
            )
            click.echo(f"Deleted target: {target['targetId']}")
        client.delete_gateway(gatewayIdentifier=gateway_id)
        click.echo("Gateway deleted.")
    except Exception as e:
        click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)


def _wait_for_gateway(client, gateway_id: str, max_attempts: int = 20) -> None:
    for _ in range(max_attempts):
        time.sleep(10)
        resp = client.get_gateway(gatewayIdentifier=gateway_id)
        status = resp.get("status")
        click.echo(f"  Gateway status: {status}")
        if status == "READY":
            return
        if status in ("FAILED", "DELETING"):
            raise RuntimeError(f"Gateway reached terminal status: {status}")
    raise TimeoutError("Timed out waiting for Gateway to become READY")


if __name__ == "__main__":
    cli()
