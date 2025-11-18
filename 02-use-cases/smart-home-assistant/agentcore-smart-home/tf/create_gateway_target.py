#!/usr/bin/env python3
"""
Create/Delete Gateway Target using direct API call
"""
import boto3
import json
import subprocess
import urllib.parse
import sys


gateway_client = boto3.client('bedrock-agentcore-control')
RESOURCE_SERVER_ID = "smarthome-agentcore-runtime-id"
SCOPES = [
    {"ScopeName": "invoke",  # Just 'invoke', will be formatted as resource_server_id/invoke
    "ScopeDescription": "Scope for invoking the agentcore gateway"},
]

scope_names = [f"{RESOURCE_SERVER_ID}/{scope['ScopeName']}" for scope in SCOPES]
runtimeScopeString = " ".join(scope_names)

def get_terraform_outputs():
    """Get outputs from Terraform state"""
    try:
        result = subprocess.run(
            ['terraform', 'output', '-json'],
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error getting Terraform outputs: {e}")
        return None

def create_target():
    """Create gateway target"""
    outputs = get_terraform_outputs()
    if not outputs:
        print("Failed to get Terraform outputs")
        return
    
    gateway_id = outputs['gateway_id']['value']
    runtime_arn = outputs['agentcore_runtime_arn']['value']
    oauth2_provider_arn = outputs['oauth2_provider_arn']['value']
    
    encoded_runtime_arn = urllib.parse.quote(runtime_arn, safe='')
    agent_url = f"https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/{encoded_runtime_arn}/invocations"
    
    try:
        response = gateway_client.create_gateway_target(
            name='mcp-server-target',
            gatewayIdentifier=gateway_id,
            targetConfiguration={
                'mcp': {
                    'mcpServer': {
                        'endpoint': agent_url
                    }
                }
            },
            credentialProviderConfigurations=[
                {
                    'credentialProviderType': 'OAUTH',
                    'credentialProvider': {
                        'oauthCredentialProvider': {
                            'providerArn': oauth2_provider_arn,
                            'scopes': [
                                runtimeScopeString
                            ]
                        }
                    }
                },
            ]
        )
        print(f"✓ Gateway target created: {response['targetId']}")
    except Exception as e:
        print(f"✗ Error creating gateway target: {e}")

def delete_target():
    """Delete gateway target"""
    outputs = get_terraform_outputs()
    if not outputs:
        return
    
    gateway_id = outputs['gateway_id']['value']
    
    try:
        # List targets to find the one to delete
        targets = gateway_client.list_gateway_targets(gatewayIdentifier=gateway_id)
        for target in targets.get('gatewayTargets', []):
            if target['name'] == 'mcp-server-target':
                gateway_client.delete_gateway_target(
                    gatewayIdentifier=gateway_id,
                    targetIdentifier=target['targetId']
                )
                print(f"✓ Gateway target deleted: {target['targetId']}")
                return
        print("Gateway target not found")
    except Exception as e:
        print(f"✗ Error deleting gateway target: {e}")

if __name__ == "__main__":
    operation = sys.argv[1] if len(sys.argv) > 1 else "create"
    if operation == "delete":
        delete_target()
    else:
        create_target()
