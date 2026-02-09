"""
Deploy Real Estate Coordinator Agent to Bedrock AgentCore Runtime
"""

import os
import sys
from bedrock_agentcore_starter_toolkit import Runtime
from boto3.session import Session

boto_session = Session()
region = boto_session.region_name

print("=" * 70)
print("Deploying Real Estate Coordinator to AgentCore Runtime")
print("=" * 70)
print()

agent_name = "realestate_coordinator"
entrypoint = "agent_agentcore.py"
requirements_file = "requirements.txt"

print(f"Configuration:")
print(f"  Agent Name: {agent_name}")
print(f"  Region: {region}")
print(f"  Protocol: A2A")
print()

agentcore_runtime = Runtime()

print("Step 1: Configuring deployment...")
config_params = {
    "entrypoint": entrypoint,
    "auto_create_execution_role": True,
    "auto_create_ecr": True,
    "requirements_file": requirements_file,
    "region": region,
    "agent_name": agent_name,
    "protocol": "A2A"
}

response = agentcore_runtime.configure(**config_params)
print("✓ Configuration completed")
print()

print("Step 2: Getting sub-agent URLs...")
# Get the sub-agent ARNs from their directories
property_search_arn = None
property_booking_arn = None

try:
    with open("../propertysearchagent_strands/.agent_arn", "r", encoding='utf-8') as f:
        property_search_arn = f.read().strip()
    print(f"✓ Property Search Agent ARN: {property_search_arn}")
except FileNotFoundError:
    print("⚠ Property Search Agent ARN not found - deploy it first")

try:
    with open("../propertybookingagent_strands/.agent_arn", "r", encoding='utf-8') as f:
        property_booking_arn = f.read().strip()
    print(f"✓ Property Booking Agent ARN: {property_booking_arn}")
except FileNotFoundError:
    print("⚠ Property Booking Agent ARN not found - deploy it first")

print()

# Construct the environment variables
env_vars = {}
if property_search_arn:
    from urllib.parse import quote
    escaped_arn = quote(property_search_arn, safe='')
    env_vars["PROPERTY_SEARCH_AGENT_URL"] = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{escaped_arn}/invocations/"
    print(f"✓ Property Search Agent URL configured")

if property_booking_arn:
    from urllib.parse import quote
    escaped_arn = quote(property_booking_arn, safe='')
    env_vars["PROPERTY_BOOKING_AGENT_URL"] = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{escaped_arn}/invocations/"
    print(f"✓ Property Booking Agent URL configured")

print()
print("Step 3: Launching to AgentCore Runtime...")
print("This may take several minutes...")
print()

try:
    launch_result = agentcore_runtime.launch(env_vars=env_vars)
    print()
    print("=" * 70)
    print("✓ Deployment Complete!")
    print("=" * 70)
    print()
    print(f"Agent ARN: {launch_result.agent_arn}")
    print(f"Agent ID: {launch_result.agent_id}")
    print()
    
    with open(".agent_arn", "w", encoding='utf-8') as f:
        f.write(launch_result.agent_arn)
    print("✓ Agent ARN saved to .agent_arn")
    print()
    
    status_response = agentcore_runtime.status()
    status = status_response.endpoint["status"]
    print(f"Status: {status}")
    print()
    
    if status in ["AVAILABLE", "READY"]:
        print("✓ Real Estate Coordinator is ready!")
        print()
        print("Test the coordinator:")
        print("  python test_coordinator.py")
        print()
    
except Exception as e:
    print()
    print("=" * 70)
    print("✗ Deployment Failed")
    print("=" * 70)
    print()
    print(f"Error: {e}")
    sys.exit(1)
