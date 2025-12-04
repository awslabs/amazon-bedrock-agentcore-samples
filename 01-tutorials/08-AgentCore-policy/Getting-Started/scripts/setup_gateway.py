"""
Setup script to create Gateway with Lambda target and save configuration
Simplified version for demo notebook
"""

import json
import logging
import sys
from pathlib import Path
from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient

def setup_gateway():
    """Setup AgentCore Gateway with Lambda target"""

    # Configuration
    region = "us-east-1"

    print("🚀 Setting up AgentCore Gateway...")
    print(f"Region: {region}\n")

    # Try to load Lambda ARN from config file
    lambda_config_file = Path(__file__).parent / 'lambda_config.json'
    lambda_arn = None

    if lambda_config_file.exists():
        try:
            with open(lambda_config_file, 'r', encoding='utf-8') as f:
                lambda_config = json.load(f)
                lambda_arn = lambda_config.get('lambda_arn')
                print("✅ Found Lambda configuration:")
                print(f"   Function: {lambda_config.get('function_name', 'RefundTool')}")
                print(f"   ARN: {lambda_arn}\n")
        except Exception as exc:
            print(f"⚠️  Could not read lambda_config.json: {exc}\n")

    # If Lambda ARN not found, ask user
    if not lambda_arn:
        print("⚠️  Lambda configuration not found")
        print("   Please run deploy_lambda.py first, or enter Lambda ARN manually\n")
        lambda_arn = input("Enter Lambda ARN: ").strip()

        if not lambda_arn:
            print("❌ Lambda ARN is required!")
            sys.exit(1)

    # Get IAM role ARN
    print("📋 Required Information:")
    print("   IAM Role ARN (with trust policy for preprod.genesis-service.aws.internal)")
    print()

    role_arn = input("Enter IAM Role ARN: ").strip() or None

    # Initialize client
    print("\n🔧 Initializing AgentCore client...")

    # Use default production endpoint (no endpoint_url specified)
    client = GatewayClient(
        region_name=region
    )
    client.logger.setLevel(logging.INFO)

    # Step 1: Create OAuth authorizer
    print("\n📝 Step 1: Creating OAuth authorization server...")
    cognito_response = client.create_oauth_authorizer_with_cognito("TestGateway")
    print("✅ Authorization server created")

    # Step 2: Create Gateway
    print("\n📝 Step 2: Creating AgentCore Gateway...")
    gateway = client.create_mcp_gateway(
        name='PolicyDemoGateway',
        role_arn=role_arn,
        authorizer_config=cognito_response["authorizer_config"],
        enable_semantic_search=True,
    )
    print(f"✅ Gateway created: {gateway['gatewayUrl']}")

    # Step 3: Add Lambda target
    print("\n📝 Step 3: Adding Lambda target...")

    # Define the refund tool schema
    refund_tool_schema = [
        {
            "name": "refund",
            "description": "Processes customer refunds by validating the refund amount, customer ID, and reason",
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

    lambda_target = client.create_mcp_gateway_target(
        gateway=gateway,
        name="RefundToolTarget",
        target_type="lambda",
        target_payload = {
            "lambdaArn": lambda_arn,
            "toolSchema": {
                "inlinePayload": refund_tool_schema
            }
        },
        credentials=None,
    )
    print("✅ Lambda target added")

    # Step 4: Save configuration
    print("\n📝 Step 4: Saving configuration...")
    config = {
        "gateway_url": gateway["gatewayUrl"],
        "gateway_id": gateway["gatewayId"],
        "gateway_arn": lambda_target["gatewayArn"],
        "region": region,
        "client_info": cognito_response["client_info"]
    }

    config_file = Path(__file__).parent / "gateway_config.json"
    with open(config_file, "w", encoding='utf-8') as f:
        json.dump(config, f, indent=2)

    print("\n" + "=" * 60)
    print("✅ GATEWAY SETUP COMPLETE!")
    print("=" * 60)
    print(f"Gateway URL: {gateway['gatewayUrl']}")
    print(f"Gateway ID: {gateway['gatewayId']}")
    print(f"Gateway ARN: {lambda_target['gatewayArn']}")
    print(f"\nConfiguration saved to: {config_file}")
    print("=" * 60)

    return config

if __name__ == "__main__":
    setup_gateway()
