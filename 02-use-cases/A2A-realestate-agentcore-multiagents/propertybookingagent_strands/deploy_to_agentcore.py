"""
Deploy Property Booking Agent to Bedrock AgentCore Runtime

This script deploys the Property Booking Agent using the bedrock-agentcore-starter-toolkit.
"""

import os
import sys
from bedrock_agentcore_starter_toolkit import Runtime
import boto3
from boto3.session import Session

# Get boto session
boto_session = Session()
region = boto_session.region_name

print("=" * 60)
print("Deploying Property Booking Agent to AgentCore Runtime")
print("=" * 60)
print()

# Configuration
agent_name = "property_booking_agent"  # Must use underscores, not hyphens
entrypoint = "agent_agentcore.py"
requirements_file = "requirements.txt"

# Get optional configuration from environment
cognito_client_id = os.getenv("COGNITO_CLIENT_ID")
cognito_discovery_url = os.getenv("COGNITO_DISCOVERY_URL")

if not cognito_client_id or not cognito_discovery_url:
    print("⚠️  Note: Cognito authentication not configured (optional)")
    print("Set COGNITO_CLIENT_ID and COGNITO_DISCOVERY_URL to enable authentication")
    print()

print(f"Configuration:")
print(f"  Agent Name: {agent_name}")
print(f"  Region: {region}")
print(f"  Entrypoint: {entrypoint}")
print(f"  Requirements: {requirements_file}")
print(f"  Auto-create execution role: True")
print(f"  Auto-create ECR: True")
print()

# Create Runtime instance
agentcore_runtime = Runtime()

# Configure the deployment
print("Step 1: Configuring deployment...")
config_params = {
    "entrypoint": entrypoint,
    "auto_create_execution_role": True,  # Let toolkit auto-create role with all permissions
    "auto_create_ecr": True,
    "requirements_file": requirements_file,
    "region": region,
    "agent_name": agent_name,
    "protocol": "A2A"
}

# Add authorizer configuration if Cognito is configured
if cognito_client_id and cognito_discovery_url:
    config_params["authorizer_configuration"] = {
        "customJWTAuthorizer": {
            "allowedClients": [cognito_client_id],
            "discoveryUrl": cognito_discovery_url,
        }
    }

response = agentcore_runtime.configure(**config_params)
print("✓ Configuration completed")
print()

# Launch the agent
print("Step 2: Launching to AgentCore Runtime...")
print("This may take several minutes...")
print()

launch_result = agentcore_runtime.launch()
print()
print("=" * 60)
print("✓ Deployment Complete!")
print("=" * 60)
print()
print(f"Agent ARN: {launch_result.agent_arn}")
print(f"Agent ID: {launch_result.agent_id}")
print()

# Check status
print("Checking deployment status...")
status_response = agentcore_runtime.status()
status = status_response.endpoint["status"]
print(f"Status: {status}")
print()

if status == "AVAILABLE":
    print("✓ Agent is ready!")
    print()
    print("Next steps:")
    print("  1. Test the agent using the agent ARN")
    print("  2. View logs with agentcore logs command")
    print("  3. Monitor with agentcore status command")
else:
    print(f"Agent status: {status}")
    print("Wait for status to become AVAILABLE before testing")

print()
print(f"Agent ARN: {launch_result.agent_arn}")
