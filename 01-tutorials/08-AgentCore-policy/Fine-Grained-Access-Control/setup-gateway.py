"""
Setup script to create Gateway with Lambda target and save configuration.
Run this first: python setup_gateway.py

If a Gateway already exists (from gateway_config.json), it will be reused.
"""

import json
import logging
from pathlib import Path
import boto3
from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient


def load_existing_config() -> dict | None:
    """Load existing gateway_config.json if it exists and has valid gateway info."""
    config_path = Path("gateway_config.json")
    if not config_path.exists():
        return None

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # Check if config has required gateway fields (not placeholders)
        if config.get('gateway_id') and '<' not in config.get('gateway_id', '<'):
            return config
    except (json.JSONDecodeError, IOError):
        pass

    return None


def get_existing_gateway(
    region: str,
    gateway_id: str = None,
    gateway_name: str = None
) -> dict | None:
    """Check if gateway exists by ID or name and return its details."""
    boto_client = boto3.client('bedrock-agentcore-control', region_name=region)

    # Try by ID first
    if gateway_id:
        try:
            gateway = boto_client.get_gateway(gatewayIdentifier=gateway_id)
            if gateway and gateway.get('status') in ['READY', 'ACTIVE']:
                return gateway
        except Exception as exc:
            print(f"  Could not retrieve gateway by ID {gateway_id}: {exc}")

    # Try to find by name
    if gateway_name:
        try:
            response = boto_client.list_gateways()
            for gw in response.get('items', []):
                if gw.get('name') == gateway_name and gw.get('status') in ['READY', 'ACTIVE']:
                    # Get full gateway details
                    full_gw = boto_client.get_gateway(gatewayIdentifier=gw['gatewayId'])
                    return full_gw
        except Exception as exc:
            print(f"  Could not search for gateway by name: {exc}")

    return None


def setup_gateway():
    """Setup AgentCore Gateway with Lambda target and policy engine."""
    # Configuration
    region = "us-east-1"

    print("🚀 Setting up AgentCore Gateway...")
    print(f"Region: {region}\n")

    # Initialize client
    client = GatewayClient(region_name=region)
    client.logger.setLevel(logging.INFO)

    # Gateway name used for this tutorial
    gateway_name = 'TestGWforPolicyEngine'

    # Check for existing configuration or gateway
    existing_config = load_existing_config()
    gateway = None
    cognito_response = None

    if existing_config:
        print("📋 Found existing gateway_config.json")
        gateway_id = existing_config.get('gateway_id')

        # Try to retrieve the existing gateway
        print(f"  Checking if gateway '{gateway_id}' exists...")
        gateway = get_existing_gateway(region, gateway_id=gateway_id)

        if gateway:
            print(
                f"✓ Reusing existing gateway: {gateway.get('gatewayUrl', gateway_id)}\n"
            )
            # Reuse existing client_info if available
            if existing_config.get('client_info'):
                cognito_response = {"client_info": existing_config['client_info']}
        else:
            print(f"  Gateway '{gateway_id}' not found or not ready.\n")

    # If no gateway yet, check if one exists by name
    if not gateway:
        print(f"🔍 Checking for existing gateway named '{gateway_name}'...")
        gateway = get_existing_gateway(region, gateway_name=gateway_name)
        if gateway:
            print(f"✓ Found existing gateway: {gateway.get('gatewayUrl')}\n")

    # Get user inputs
    role_arn = input(
        "Enter role ARN to which you added the Trust relationship "
        "(or press Enter to create one): "
    ).strip() or None
    lambda_arn = input("Enter Lambda ARN: ").strip()

    if not lambda_arn:
        print("❌ Lambda ARN is required")
        return None

    # Create OAuth authorizer if we don't have existing client_info
    if not cognito_response:
        print("\nStep 1: Creating OAuth authorization server...")
        cognito_response = client.create_oauth_authorizer_with_cognito("TestGateway")
        print("✓ Authorization server created\n")

    # Create Gateway if we don't have an existing one
    if not gateway:
        print("Step 2: Creating Gateway...")
        gateway = client.create_mcp_gateway(
            name=gateway_name,
            role_arn=role_arn,
            authorizer_config=cognito_response.get("authorizer_config"),
            enable_semantic_search=True,
        )
        print(f"✓ Gateway created: {gateway['gatewayUrl']}\n")
    else:
        print("Step 2: Skipping gateway creation (reusing existing)\n")

    # Add Lambda target (or reuse existing)
    print("Step 3: Adding Lambda target...")

    target_name = "RefundToolTarget"

    # Define the refund tool schema
    refund_tool_schema = [
        {
            "name": "refund",
            "description": (
                "Processes customer refunds by validating the refund amount, "
                "customer ID, and reason. Returns a refund ID and confirmation "
                "details upon successful processing."
            ),
            "inputSchema": {
                "type": "object",
                "description": "Input parameters for processing a customer refund",
                "properties": {
                    "amount": {
                        "type": "integer",
                        "description": "The refund amount in USD (must be positive)",
                    },
                    "orderId": {
                        "type": "string",
                        "description": "Unique identifier for the customer requesting the refund",
                    },
                },
                "required": ["amount", "orderId"]
            }
        }
    ]

    try:
        lambda_target = client.create_mcp_gateway_target(
            gateway=gateway,
            name=target_name,
            target_type="lambda",
            target_payload={
                "lambdaArn": lambda_arn,
                "toolSchema": {
                    "inlinePayload": refund_tool_schema
                }
            },
            credentials=None,
        )
        print("✓ Lambda target added\n")
    except Exception as exc:
        if "ConflictException" in str(type(exc).__name__) or "already exists" in str(exc):
            print(f"✓ Lambda target '{target_name}' already exists, reusing\n")
            # Target already exists, just use the gateway ARN
            lambda_target = {"gatewayArn": gateway.get("gatewayArn")}
        else:
            raise

    # Save configuration
    config = {
        "gateway_url": gateway.get("gatewayUrl"),
        "gateway_id": gateway.get("gatewayId"),
        "gateway_arn": lambda_target.get("gatewayArn"),
        "region": region,
        "client_info": cognito_response.get("client_info")
    }

    with open("gateway_config.json", "w", encoding='utf-8') as f:
        json.dump(config, f, indent=2)

    print("=" * 60)
    print("✅ Gateway setup complete!")
    print(f"Gateway URL: {config['gateway_url']}")
    print(f"Gateway ID: {config['gateway_id']}")
    print(f"Gateway ARN: {config['gateway_arn']}")
    print("\nConfiguration saved to: gateway_config.json")
    print("=" * 60)

    return config


if __name__ == "__main__":
    setup_gateway()
