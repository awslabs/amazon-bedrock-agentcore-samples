#!/usr/bin/env python3

# ============================================================================
# IMPORTS
# ============================================================================

import boto3
import time
import sys
import os
import yaml

# ============================================================================
# CONFIGURATION
# ============================================================================

# Add project root to path for shared config manager
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from shared.config_manager import AgentCoreConfigManager

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def update_config_with_arns(config_manager, runtime_arn, endpoint_arn):
    """Update dynamic configuration with new ARNs"""
    print(f"\n📝 Updating dynamic configuration with new DIY runtime ARN...")
    try:
        # Update dynamic configuration
        updates = {
            "runtime": {
                "diy_agent": {
                    "arn": runtime_arn
                }
            }
        }
        
        if endpoint_arn:
            updates["runtime"]["diy_agent"]["endpoint_arn"] = endpoint_arn
        
        config_manager.update_dynamic_config(updates)
        print("   ✅ Dynamic config updated with new DIY runtime ARN")
        
    except Exception as config_error:
        print(f"   ⚠️  Error updating config: {config_error}")

# Initialize configuration manager
config_manager = AgentCoreConfigManager()

# Get configuration values
base_config = config_manager.get_base_settings()
merged_config = config_manager.get_merged_config()  # For runtime values that may be dynamic
oauth_config = config_manager.get_oauth_settings()

# Extract configuration values
REGION = base_config['aws']['region']
ROLE_ARN = base_config['runtime']['role_arn']
AGENT_RUNTIME_NAME = base_config['runtime']['diy_agent']['name']
ECR_URI = merged_config['runtime']['diy_agent']['ecr_uri']  # ECR URI is dynamic

# Okta configuration
OKTA_DOMAIN = oauth_config['domain']
OKTA_AUDIENCE = oauth_config['jwt']['audience']

print("🚀 Creating AgentCore Runtime for DIY agent...")
print(f"   📝 Name: {AGENT_RUNTIME_NAME}")
print(f"   📦 Container: {ECR_URI}")
print(f"   🔐 Role: {ROLE_ARN}")

control_client = boto3.client('bedrock-agentcore-control', region_name=REGION)

try:
    response = control_client.create_agent_runtime(
        agentRuntimeName=AGENT_RUNTIME_NAME,
        agentRuntimeArtifact={
            'containerConfiguration': {
                'containerUri': ECR_URI
            }
        },
        networkConfiguration={"networkMode": "PUBLIC"},
        roleArn=ROLE_ARN,
        authorizerConfiguration={
            'customJWTAuthorizer': {
                'discoveryUrl': oauth_config['jwt']['discovery_url'],
                'allowedAudience': [OKTA_AUDIENCE]
            }
        }
    )
    
    runtime_arn = response['agentRuntimeArn']
    runtime_id = runtime_arn.split('/')[-1]
    
    print(f"✅ DIY AgentCore Runtime created!")
    print(f"🏷️  ARN: {runtime_arn}")
    print(f"🆔 Runtime ID: {runtime_id}")
    
    print(f"\n⏳ Waiting for runtime to be READY...")
    max_wait = 600  # 10 minutes
    wait_time = 0
    
    while wait_time < max_wait:
        try:
            status_response = control_client.get_agent_runtime(agentRuntimeId=runtime_id)
            status = status_response.get('status')
            print(f"   📊 Status: {status} ({wait_time}s)")
            
            if status == 'READY':
                print(f"✅ DIY Runtime is READY!")
                
                # Create DEFAULT endpoint
                print(f"\n🔗 Creating DEFAULT endpoint...")
                try:
                    endpoint_response = control_client.create_agent_runtime_endpoint(
                        agentRuntimeId=runtime_id,
                        name="DEFAULT"
                    )
                    print(f"✅ DEFAULT endpoint created!")
                    print(f"🏷️  Endpoint ARN: {endpoint_response['agentRuntimeEndpointArn']}")
                    
                    # Update config with new ARNs
                    update_config_with_arns(config_manager, runtime_arn, endpoint_response['agentRuntimeEndpointArn'])
                    
                except Exception as ep_error:
                    if "already exists" in str(ep_error):
                        print(f"ℹ️  DEFAULT endpoint already exists, getting existing endpoint ARN...")
                        try:
                            # Get the existing endpoint ARN
                            endpoints_response = control_client.list_agent_runtime_endpoints(agentRuntimeId=runtime_id)
                            for endpoint in endpoints_response.get('agentRuntimeEndpoints', []):
                                if endpoint.get('name') == 'DEFAULT':
                                    endpoint_arn = endpoint.get('agentRuntimeEndpointArn')
                                    print(f"🏷️  Found existing endpoint ARN: {endpoint_arn}")
                                    update_config_with_arns(config_manager, runtime_arn, endpoint_arn)
                                    break
                            else:
                                # Fallback: construct the endpoint ARN
                                endpoint_arn = f"{runtime_arn}/runtime-endpoint/DEFAULT"
                                print(f"🔧 Constructed endpoint ARN: {endpoint_arn}")
                                update_config_with_arns(config_manager, runtime_arn, endpoint_arn)
                        except Exception as list_error:
                            print(f"⚠️  Could not get endpoint ARN: {list_error}")
                            # Fallback: construct the endpoint ARN
                            endpoint_arn = f"{runtime_arn}/runtime-endpoint/DEFAULT"
                            print(f"🔧 Using constructed endpoint ARN: {endpoint_arn}")
                            update_config_with_arns(config_manager, runtime_arn, endpoint_arn)
                    else:
                        print(f"❌ Error creating endpoint: {ep_error}")
                        # Still update with just runtime ARN
                        update_config_with_arns(config_manager, runtime_arn, "")
                
                break
            elif status in ['FAILED', 'DELETING']:
                print(f"❌ Runtime creation failed with status: {status}")
                break
            
            time.sleep(15)
            wait_time += 15
            
        except Exception as e:
            print(f"❌ Error checking status: {e}")
            break
    
    if wait_time >= max_wait:
        print(f"⚠️  Runtime creation taking longer than expected")
    
    print(f"\n🧪 Test with:")
    print(f"   ARN: {runtime_arn}")
    print(f"   ID: {runtime_id}")
    
except Exception as e:
    print(f"❌ Error creating DIY runtime: {e}")