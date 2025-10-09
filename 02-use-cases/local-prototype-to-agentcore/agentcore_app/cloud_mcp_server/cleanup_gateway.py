#!/usr/bin/env python3
"""Cleanup Bedrock AgentCore Gateway

This script removes the gateway and associated resources created by the setup script.
Use this if you want to start fresh or remove the gateway.
"""

import boto3
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

region = os.getenv("AWS_REGION", "us-east-1")
endpoint_url = os.getenv("ENDPOINT_URL", "https://bedrock-agentcore-control.us-east-1.amazonaws.com")
gateway_name = os.getenv("GATEWAY_NAME", "InsuranceAPIGateway")

print(f"Cleaning up gateway '{gateway_name}' in region {region}")

# Create boto3 client
client = boto3.client('bedrock-agentcore-control', 
                     region_name=region,
                     endpoint_url=endpoint_url)

# Find the gateway
print(f"Looking for gateway '{gateway_name}'...")
response = client.list_gateways()
gateway = None
for gw in response.get('gateways', []):
    if gw['name'] == gateway_name:
        gateway = gw
        print(f"✓ Found gateway: {gateway['gatewayId']}")
        break

if not gateway:
    print(f"⚠️  Gateway '{gateway_name}' not found. Nothing to clean up.")
    exit(0)

# List and delete targets
print(f"Listing targets for gateway...")
try:
    targets_response = client.list_gateway_targets(gatewayArn=gateway['gatewayArn'])
    targets = targets_response.get('targets', [])
    
    if targets:
        print(f"Found {len(targets)} target(s) to delete")
        for target in targets:
            print(f"  Deleting target: {target['targetId']} ({target['name']})")
            try:
                client.delete_gateway_target(
                    gatewayArn=gateway['gatewayArn'],
                    targetId=target['targetId']
                )
                print(f"  ✓ Deleted target: {target['targetId']}")
            except Exception as e:
                print(f"  ⚠️  Error deleting target: {e}")
    else:
        print("No targets found")
except Exception as e:
    print(f"⚠️  Error listing targets: {e}")

# Delete the gateway
print(f"Deleting gateway: {gateway['gatewayId']}")
try:
    client.delete_gateway(gatewayArn=gateway['gatewayArn'])
    print(f"✓ Deleted gateway: {gateway['gatewayId']}")
except Exception as e:
    print(f"❌ Error deleting gateway: {e}")
    exit(1)

# Clean up Cognito resources (optional - commented out by default)
# Uncomment if you want to also delete the Cognito user pool
"""
print("\nCleaning up Cognito resources...")
cognito_client = boto3.client('cognito-idp', region_name=region)

# Find user pool by domain
domain_name = f"agentcore-{gateway_name.lower()}"
try:
    pools_response = cognito_client.list_user_pools(MaxResults=60)
    for pool in pools_response.get('UserPools', []):
        pool_id = pool['Id']
        # Check if this pool has our domain
        try:
            domain_response = cognito_client.describe_user_pool_domain(Domain=domain_name)
            if domain_response.get('DomainDescription', {}).get('UserPoolId') == pool_id:
                print(f"Found user pool: {pool_id}")
                # Delete domain first
                print(f"Deleting domain: {domain_name}")
                cognito_client.delete_user_pool_domain(Domain=domain_name, UserPoolId=pool_id)
                print(f"✓ Deleted domain")
                
                # Delete user pool
                print(f"Deleting user pool: {pool_id}")
                cognito_client.delete_user_pool(UserPoolId=pool_id)
                print(f"✓ Deleted user pool")
                break
        except:
            continue
except Exception as e:
    print(f"⚠️  Error cleaning up Cognito: {e}")
"""

print("\n✅ Cleanup complete!")
print("\nNote: Cognito resources (user pool, domain) were NOT deleted.")
print("To delete them manually, uncomment the Cognito cleanup section in this script.")
