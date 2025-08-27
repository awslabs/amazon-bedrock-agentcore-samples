#!/usr/bin/python
from typing import List
import os
import sys
import boto3
import click

from utils import (
    get_aws_region,
    get_ssm_parameter,
    put_ssm_parameter,
    delete_ssm_parameter,
    load_api_spec,
    get_cognito_client_secret,
)


REGION = get_aws_region()

gateway_client = boto3.client(
    "bedrock-agentcore-control",
    region_name=REGION,
)


def create_gateway(gateway_name: str, api_spec: List) -> dict:
    """Create an AgentCore gateway with the specified configuration."""
    try:
        # Use Cognito for Inbound OAuth to our Gateway
        lambda_target_config = {
            "mcp": {
                "lambda": {
                    "lambdaArn": get_ssm_parameter(
                        "/app/customersupport/agentcore/lambda_arn"
                    ),
                    "toolSchema": {"inlinePayload": api_spec},
                }
            }
        }

        auth_config = {
            "customJWTAuthorizer": {
                "allowedClients": [
                    get_ssm_parameter(
                        "/app/customersupport/agentcore/machine_client_id"
                    )
                ],
                "discoveryUrl": get_ssm_parameter(
                    "/app/customersupport/agentcore/cognito_discovery_url"
                ),
            }
        }

        execution_role_arn = get_ssm_parameter(
            "/app/customersupport/agentcore/gateway_iam_role"
        )

        click.echo(f"Creating gateway in region {REGION} with name: {gateway_name}")
        click.echo(f"Execution role ARN: {execution_role_arn}")

        create_response = gateway_client.create_gateway(
            name=gateway_name,
            roleArn=execution_role_arn,
            protocolType="MCP",
            authorizerType="CUSTOM_JWT",
            authorizerConfiguration=auth_config,
            description="Customer Support AgentCore Gateway",
        )

        click.echo(f"✅ Gateway created: {create_response['gatewayId']}")

        # Create gateway target
        credential_config = [{"credentialProviderType": "GATEWAY_IAM_ROLE"}]
        gateway_id = create_response["gatewayId"]

        create_target_response = gateway_client.create_gateway_target(
            gatewayIdentifier=gateway_id,
            name="LambdaUsingSDK",
            description="Lambda Target using SDK",
            targetConfiguration=lambda_target_config,
            credentialProviderConfigurations=credential_config,
        )

        click.echo(f"✅ Gateway target created: {create_target_response['targetId']}")

        gateway = {
            "id": gateway_id,
            "name": gateway_name,
            "gateway_url": create_response["gatewayUrl"],
            "gateway_arn": create_response["gatewayArn"],
        }

        # Save gateway details to SSM parameters
        put_ssm_parameter("/app/customersupport/agentcore/gateway_id", gateway_id)
        put_ssm_parameter("/app/customersupport/agentcore/gateway_name", gateway_name)
        put_ssm_parameter(
            "/app/customersupport/agentcore/gateway_arn", create_response["gatewayArn"]
        )
        put_ssm_parameter(
            "/app/customersupport/agentcore/gateway_url", create_response["gatewayUrl"]
        )
        put_ssm_parameter(
            "/app/customersupport/agentcore/cognito_secret",
            get_cognito_client_secret(),
            with_encryption=True,
        )

        click.echo("✅ Gateway configuration saved to SSM parameters")

        return gateway

    except Exception as e:
        click.echo(f"❌ Error creating gateway: {str(e)}", err=True)
        sys.exit(1)


def delete_gateway(gateway_id: str) -> bool:
    """Delete a gateway and all its targets."""
    try:
        click.echo(f"🗑️  Deleting all targets for gateway: {gateway_id}")

        # List and delete all targets
        list_response = gateway_client.list_gateway_targets(
            gatewayIdentifier=gateway_id, maxResults=100
        )

        for item in list_response["items"]:
            target_id = item["targetId"]
            click.echo(f"   Deleting target: {target_id}")
            gateway_client.delete_gateway_target(
                gatewayIdentifier=gateway_id, targetId=target_id
            )
            click.echo(f"   ✅ Target {target_id} deleted")

        # Delete the gateway
        click.echo(f"🗑️  Deleting gateway: {gateway_id}")
        gateway_client.delete_gateway(gatewayIdentifier=gateway_id)
        click.echo(f"✅ Gateway {gateway_id} deleted successfully")

        return True

    except Exception as e:
        click.echo(f"❌ Error deleting gateway: {str(e)}", err=True)
        return False


def get_gateway_id_from_config() -> str:
    """Get gateway ID from SSM parameter."""
    try:
        return get_ssm_parameter("/app/customersupport/agentcore/gateway_id")
    except Exception as e:
        click.echo(f"❌ Error reading gateway ID from SSM: {str(e)}", err=True)
        return None


@click.group()
@click.pass_context
def cli(ctx):
    """AgentCore Gateway Management CLI.

    Create and delete AgentCore gateways for the customer support application.
    """
    ctx.ensure_object(dict)


@cli.command()
@click.option("--name", required=True, help="Name for the gateway")
@click.option(
    "--api-spec-file",
    default="prerequisite/lambda/api_spec.json",
    help="Path to the API specification file (default: prerequisite/lambda/api_spec.json)",
)
def create(name, api_spec_file):
    """Create a new AgentCore gateway."""
    click.echo(f"🚀 Creating AgentCore gateway: {name}")
    click.echo(f"📍 Region: {REGION}")

    # Validate API spec file exists
    if not os.path.exists(api_spec_file):
        click.echo(f"❌ API specification file not found: {api_spec_file}", err=True)
        sys.exit(1)

    try:
        api_spec = load_api_spec(api_spec_file)
        gateway = create_gateway(gateway_name=name, api_spec=api_spec)
        click.echo(f"🎉 Gateway created successfully with ID: {gateway['id']}")

    except Exception as e:
        click.echo(f"❌ Failed to create gateway: {str(e)}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--gateway-id",
    help="Gateway ID to delete (if not provided, will read from gateway.config)",
)
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
def delete(gateway_id, confirm):
    """Delete an AgentCore gateway and all its targets."""

    # If no gateway ID provided, try to read from config
    if not gateway_id:
        gateway_id = get_gateway_id_from_config()
        if not gateway_id:
            click.echo(
                "❌ No gateway ID provided and couldn't read from SSM parameters",
                err=True,
            )
            sys.exit(1)
        click.echo(f"📖 Using gateway ID from SSM: {gateway_id}")

    # Confirmation prompt
    if not confirm:
        if not click.confirm(
            f"⚠️  Are you sure you want to delete gateway {gateway_id}? This action cannot be undone."
        ):
            click.echo("❌ Operation cancelled")
            sys.exit(0)

    click.echo(f"🗑️  Deleting gateway: {gateway_id}")

    if delete_gateway(gateway_id):
        click.echo("✅ Gateway deleted successfully")

        # Clean up SSM parameters
        delete_ssm_parameter("/app/customersupport/agentcore/gateway_id")
        delete_ssm_parameter("/app/customersupport/agentcore/gateway_name")
        delete_ssm_parameter("/app/customersupport/agentcore/gateway_arn")
        delete_ssm_parameter("/app/customersupport/agentcore/gateway_url")
        delete_ssm_parameter("/app/customersupport/agentcore/cognito_secret")
        click.echo("🧹 Removed gateway SSM parameters")

        # Clean up config file if it exists (backward compatibility)
        if os.path.exists("gateway.config"):
            os.remove("gateway.config")
            click.echo("🧹 Removed gateway.config file")

        click.echo("🎉 Gateway and configuration deleted successfully")
    else:
        click.echo("❌ Failed to delete gateway", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
