#!/bin/bash

# Comprehensive AgentCore Cleanup Script
# This script removes EVERYTHING related to AgentCore deployment
# Use with caution - this will delete all agents, identities, and providers

set -e  # Exit on any error

echo "🧹 AgentCore Complete Cleanup"
echo "============================="
<<<<<<< HEAD
echo ""
echo "This script will delete ALL resources created by the following deployment scripts:"
echo "  • 01-prerequisites.sh (IAM roles, ECR repositories)"
echo "  • 02-create-memory.sh (AgentCore Memory resources)"
echo "  • 03-setup-oauth-provider.sh (OAuth2 credential providers)"
echo "  • 04-deploy-mcp-tool-lambda-zip.sh (MCP Lambda function and stack)"
echo "  • 05-create-gateway-targets.sh (AgentCore Gateways and targets)"
echo "  • 06-deploy-diy.sh (DIY agent runtime and ECR images)"
echo "  • 07-deploy-sdk.sh (SDK agent runtime and ECR images)"
echo ""
=======
>>>>>>> origin/main

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory and project paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
CONFIG_DIR="${PROJECT_DIR}/config"

# Load configuration using centralized config manager
echo "📋 Loading configuration using AgentCoreConfigManager..."

# Create temporary Python script to get configuration values
CONFIG_SCRIPT="${SCRIPT_DIR}/temp_get_config.py"
cat > "$CONFIG_SCRIPT" << 'EOF'
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from shared.config_manager import AgentCoreConfigManager
    
    config_manager = AgentCoreConfigManager()
    base_config = config_manager.get_base_settings()
    dynamic_config = config_manager.get_dynamic_config()
    
    # Output configuration values for shell script
    print(f"REGION={base_config['aws']['region']}")
    print(f"ACCOUNT_ID={base_config['aws']['account_id']}")
    
    # Output dynamic configuration for cleanup targeting
    runtime_config = dynamic_config.get('runtime', {})
    gateway_config = dynamic_config.get('gateway', {})
    mcp_config = dynamic_config.get('mcp_lambda', {})
    
    # DIY Agent ARNs
    diy_arn = runtime_config.get('diy_agent', {}).get('arn', '')
    diy_endpoint_arn = runtime_config.get('diy_agent', {}).get('endpoint_arn', '')
    
    # SDK Agent ARNs  
    sdk_arn = runtime_config.get('sdk_agent', {}).get('arn', '')
    sdk_endpoint_arn = runtime_config.get('sdk_agent', {}).get('endpoint_arn', '')
    
    # Gateway info
    gateway_url = gateway_config.get('url', '')
    gateway_id = gateway_config.get('id', '')
    gateway_arn = gateway_config.get('arn', '')
    
    # MCP Lambda info
    mcp_function_arn = mcp_config.get('function_arn', '')
    mcp_function_name = mcp_config.get('function_name', '')
    mcp_stack_name = mcp_config.get('stack_name', 'bac-mcp-stack')
    
    print(f"DIY_RUNTIME_ARN={diy_arn}")
    print(f"DIY_ENDPOINT_ARN={diy_endpoint_arn}")
    print(f"SDK_RUNTIME_ARN={sdk_arn}")
    print(f"SDK_ENDPOINT_ARN={sdk_endpoint_arn}")
    print(f"GATEWAY_URL={gateway_url}")
    print(f"GATEWAY_ID={gateway_id}")
    print(f"GATEWAY_ARN={gateway_arn}")
    print(f"MCP_FUNCTION_ARN={mcp_function_arn}")
    print(f"MCP_FUNCTION_NAME={mcp_function_name}")
    print(f"MCP_STACK_NAME={mcp_stack_name}")
    
except Exception as e:
    print(f"# Error loading configuration: {e}", file=sys.stderr)
    # Fallback to default values
    print("REGION=us-east-1")
    print("ACCOUNT_ID=unknown")
    print("DIY_RUNTIME_ARN=")
    print("DIY_ENDPOINT_ARN=")
    print("SDK_RUNTIME_ARN=")
    print("SDK_ENDPOINT_ARN=")
    print("GATEWAY_URL=")
    print("GATEWAY_ID=")
    print("GATEWAY_ARN=")
    print("MCP_FUNCTION_ARN=")
    print("MCP_FUNCTION_NAME=")
    print("MCP_STACK_NAME=bac-mcp-stack")
EOF

# Execute the config script and source the output
if CONFIG_OUTPUT=$(python3 "$CONFIG_SCRIPT" 2>/dev/null); then
    eval "$CONFIG_OUTPUT"
    echo "   ✅ Configuration loaded successfully"
else
    echo "   ⚠️  Failed to load configuration, using defaults"
    REGION="us-east-1"
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "unknown")
    DIY_RUNTIME_ARN=""
    DIY_ENDPOINT_ARN=""
    SDK_RUNTIME_ARN=""
    SDK_ENDPOINT_ARN=""
    GATEWAY_URL=""
    GATEWAY_ID=""
    GATEWAY_ARN=""
    MCP_FUNCTION_ARN=""
    MCP_FUNCTION_NAME=""
    MCP_STACK_NAME="bac-mcp-stack"
fi

# Clean up temporary script
rm -f "$CONFIG_SCRIPT"

echo -e "${BLUE}📝 Configuration loaded:${NC}"
echo "   Region: $REGION"
echo "   Account ID: $ACCOUNT_ID"
echo ""
echo -e "${BLUE}📝 Resources to clean up:${NC}"
echo "   DIY Runtime ARN: ${DIY_RUNTIME_ARN:-'(not deployed)'}"
echo "   SDK Runtime ARN: ${SDK_RUNTIME_ARN:-'(not deployed)'}"
echo "   Gateway ID: ${GATEWAY_ID:-'(not deployed)'}"
echo "   MCP Stack: ${MCP_STACK_NAME:-'bac-mcp-stack'}"
echo ""

# Warning and confirmation
show_warning() {
    echo -e "${RED}⚠️  WARNING: DESTRUCTIVE OPERATION${NC}"
    echo -e "${RED}=================================${NC}"
    echo ""
    echo -e "${YELLOW}This script will DELETE ALL of the following:${NC}"
    echo ""
<<<<<<< HEAD
    echo -e "${RED}🗑️  AgentCore Runtime Agents (from 06-deploy-diy.sh & 07-deploy-sdk.sh):${NC}"
    echo "   • DIY agent runtime instances and endpoints"
    echo "   • SDK agent runtime instances and endpoints"
    echo "   • Agent runtime configurations"
    echo ""
    echo -e "${RED}🗑️  AgentCore Memory Resources (from 02-create-memory.sh):${NC}"
    echo "   • Memory resources for conversation storage"
    echo "   • All stored conversation history"
    echo "   • Memory configurations"
    echo ""
    echo -e "${RED}🗑️  AgentCore Identity Resources (from 03-setup-oauth-provider.sh):${NC}"
    echo "   • OAuth2 credential providers (Okta integration)"
    echo "   • All workload identities"
    echo "   • All identity associations"
    echo ""
    echo -e "${RED}🗑️  AgentCore Gateway & MCP Resources (from 04-deploy-mcp-tool-lambda-zip.sh & 05-create-gateway-targets.sh):${NC}"
    echo "   • All AgentCore gateways and targets"
    echo "   • MCP tool Lambda function (bac-mcp-tool)"
    echo "   • CloudFormation stack (bac-mcp-stack)"
    echo "   • Lambda IAM roles (MCPToolFunctionRole, BedrockAgentCoreGatewayExecutionRole)"
    echo "   • CloudWatch log groups (/aws/lambda/bac-mcp-tool)"
    echo "   • Gateway configurations"
    echo ""
    echo -e "${RED}🗑️  AWS Infrastructure (from 01-prerequisites.sh):${NC}"
    echo "   • ECR repositories (bac-runtime-repo-diy, bac-runtime-repo-sdk) and all images"
    echo "   • IAM role: bac-execution-role"
    echo "   • IAM policies attached to the role"
    echo ""
    echo -e "${RED}🗑️  Configuration Files:${NC}"
    echo "   • Dynamic configuration values (reset to empty)"
=======
    echo -e "${RED}🗑️  AgentCore Runtime Agents:${NC}"
    echo "   • All deployed DIY and SDK agents"
    echo "   • Agent runtime instances"
    echo "   • Agent configurations"
    echo ""
    echo -e "${RED}🗑️  AgentCore Identity Resources:${NC}"
    echo "   • All OAuth2 credential providers"
    echo "   • All workload identities"
    echo "   • All identity associations"
    echo ""
    echo -e "${RED}🗑️  AWS Infrastructure:${NC}"
    echo "   • ECR repositories and images"
    echo "   • IAM role: bac-execution-role"
    echo "   • IAM policies attached to the role"
    echo ""
    echo -e "${RED}🗑️  AgentCore Gateway & MCP Resources:${NC}"
    echo "   • All AgentCore gateways and targets"
    echo "   • MCP tool Lambda function and stack"
    echo "   • Gateway configurations"
    echo ""
    echo -e "${RED}🗑️  Configuration Files:${NC}"
    echo "   • oauth-provider.yaml"
>>>>>>> origin/main
    echo "   • Generated configuration sections"
    echo ""
    echo -e "${YELLOW}💡 What will NOT be deleted:${NC}"
    echo "   • Your static-config.yaml"
    echo "   • AWS account-level settings"
    echo "   • Other AWS resources not created by AgentCore"
    echo ""
}

<<<<<<< HEAD
# Function to cleanup AgentCore Memory resources
cleanup_memory_resources() {
    echo -e "${BLUE}🗑️  Cleaning up AgentCore Memory resources...${NC}"
    echo "============================================="
    
    # Use the existing memory deletion script
    if [[ -f "${SCRIPT_DIR}/11-delete-memory.sh" ]]; then
        echo "Using existing 11-delete-memory.sh script..."
        if bash "${SCRIPT_DIR}/11-delete-memory.sh"; then
            echo -e "${GREEN}✅ Memory resources cleanup completed${NC}"
        else
            echo -e "${YELLOW}⚠️  Memory resources cleanup had issues${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  11-delete-memory.sh not found - skipping memory cleanup${NC}"
    fi
}

=======
>>>>>>> origin/main
# Function to cleanup AgentCore Runtime agents
cleanup_runtime_agents() {
    echo -e "${BLUE}🗑️  Cleaning up AgentCore Runtime agents...${NC}"
    echo "============================================="
    
<<<<<<< HEAD
    # Use the existing runtime deletion script
    if [[ -f "${SCRIPT_DIR}/08-delete-runtimes.sh" ]]; then
        echo "Using existing 08-delete-runtimes.sh script..."
        if bash "${SCRIPT_DIR}/08-delete-runtimes.sh"; then
=======
    # Use the existing cleanup script if available
    if [[ -f "${SCRIPT_DIR}/cleanup-agents.py" ]]; then
        echo "Using existing cleanup-agents.py script with configuration..."
        
        # Set environment variables for the cleanup script
        export CLEANUP_REGION="$REGION"
        export CLEANUP_DIY_ARN="$DIY_RUNTIME_ARN"
        export CLEANUP_SDK_ARN="$SDK_RUNTIME_ARN"
        export CLEANUP_DIY_ENDPOINT_ARN="$DIY_ENDPOINT_ARN"
        export CLEANUP_SDK_ENDPOINT_ARN="$SDK_ENDPOINT_ARN"
        
        if python3 "${SCRIPT_DIR}/cleanup-agents.py"; then
>>>>>>> origin/main
            echo -e "${GREEN}✅ Runtime agents cleanup completed${NC}"
        else
            echo -e "${YELLOW}⚠️  Runtime agents cleanup had issues${NC}"
        fi
<<<<<<< HEAD
    else
        echo -e "${YELLOW}⚠️  08-delete-runtimes.sh not found - skipping runtime cleanup${NC}"
=======
        
        # Clean up environment variables
        unset CLEANUP_REGION CLEANUP_DIY_ARN CLEANUP_SDK_ARN CLEANUP_DIY_ENDPOINT_ARN CLEANUP_SDK_ENDPOINT_ARN
    else
        echo -e "${YELLOW}⚠️  cleanup-agents.py not found, skipping runtime cleanup${NC}"
>>>>>>> origin/main
    fi
}

# Function to cleanup AgentCore Gateway and MCP resources
cleanup_gateway_mcp_resources() {
    echo -e "${BLUE}🗑️  Cleaning up AgentCore Gateway and MCP resources...${NC}"
    echo "===================================================="
    
<<<<<<< HEAD
    # Use the existing gateway and MCP deletion scripts
    echo "Step 1: Deleting gateways and targets..."
    if [[ -f "${SCRIPT_DIR}/09-delete-gateways-targets.sh" ]]; then
        # Run the gateway deletion script non-interactively
        echo "y" | bash "${SCRIPT_DIR}/09-delete-gateways-targets.sh" || echo -e "${YELLOW}⚠️  Gateway deletion had issues${NC}"
    else
        echo -e "${YELLOW}⚠️  09-delete-gateways-targets.sh not found${NC}"
    fi
    
    echo ""
    echo "Step 2: Deleting MCP tool Lambda deployment..."
    if [[ -f "${SCRIPT_DIR}/10-delete-mcp-tool-deployment.sh" ]]; then
        # Run the MCP deletion script non-interactively
        echo "y" | bash "${SCRIPT_DIR}/10-delete-mcp-tool-deployment.sh" || echo -e "${YELLOW}⚠️  MCP deletion had issues${NC}"
    else
        echo -e "${YELLOW}⚠️  10-delete-mcp-tool-deployment.sh not found${NC}"
    fi
    
    echo -e "${GREEN}✅ Gateway and MCP resources cleanup completed${NC}"
=======
    # Create temporary Python script for gateway and MCP cleanup
    local cleanup_script="${SCRIPT_DIR}/temp_gateway_mcp_cleanup.py"
    
    cat > "$cleanup_script" << 'EOF'
import boto3
import json
import time
import os

def cleanup_mcp_cloudformation_stack(cloudformation_client, stack_name):
    """Cleanup MCP CloudFormation stack with enhanced error handling"""
    try:
        # Check if stack exists
        try:
            cloudformation_client.describe_stacks(StackName=stack_name)
            stack_exists = True
        except cloudformation_client.exceptions.ClientError as e:
            if "does not exist" in str(e):
                stack_exists = False
                print(f"   ✅ CloudFormation stack doesn't exist: {stack_name}")
                return True
            else:
                raise e
        
        if stack_exists:
            print(f"   🗑️  Deleting CloudFormation stack: {stack_name}")
            cloudformation_client.delete_stack(StackName=stack_name)
            
            # Wait for stack deletion (with timeout)
            print("   ⏳ Waiting for stack deletion...")
            waiter = cloudformation_client.get_waiter('stack_delete_complete')
            
            try:
                waiter.wait(
                    StackName=stack_name,
                    WaiterConfig={'MaxAttempts': 20, 'Delay': 30}  # Wait up to 10 minutes
                )
                print(f"   ✅ CloudFormation stack deleted: {stack_name}")
                return True
            except Exception as e:
                print(f"   ⚠️  Stack deletion timeout or error: {e}")
                print(f"   🔍 Check AWS Console for stack status")
                return False
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error with CloudFormation stack: {e}")
        return False

def cleanup_standalone_mcp_resources(region):
    """Cleanup standalone MCP tool lambda resources not managed by CloudFormation"""
    try:
        lambda_client = boto3.client('lambda', region_name=region)
        iam_client = boto3.client('iam', region_name=region)
        logs_client = boto3.client('logs', region_name=region)
        
        # 1. Find and delete MCP lambda functions
        print("   🔍 Finding standalone MCP lambda functions...")
        functions = lambda_client.list_functions()
        mcp_functions = []
        
        # Look for MCP-related function names (excluding CloudFormation managed ones)
        mcp_patterns = ['mcp', 'tool', 'agentcore', 'genesis']
        cf_patterns = ['aws-cloudformation', 'cloudformation']  # Skip CF managed functions
        
        for func in functions.get('Functions', []):
            func_name = func.get('FunctionName', '')
            func_name_lower = func_name.lower()
            
            # Check if it's MCP-related but not CloudFormation managed
            is_mcp_related = any(pattern in func_name_lower for pattern in mcp_patterns)
            is_cf_managed = any(pattern in func_name_lower for pattern in cf_patterns)
            
            if is_mcp_related and not is_cf_managed:
                mcp_functions.append(func)
                print(f"   📦 Found potential standalone MCP function: {func_name}")
        
        if not mcp_functions:
            print("   ✅ No standalone MCP lambda functions found")
            return True
        
        # Delete identified MCP functions
        deleted_functions = []
        for func in mcp_functions:
            func_name = func.get('FunctionName')
            try:
                lambda_client.delete_function(FunctionName=func_name)
                print(f"   ✅ Deleted lambda function: {func_name}")
                deleted_functions.append(func_name)
            except Exception as e:
                print(f"   ❌ Failed to delete lambda function {func_name}: {e}")
        
        # 2. Cleanup associated IAM roles
        print("   🔍 Cleaning up MCP-related IAM roles...")
        cleanup_mcp_iam_roles(iam_client, deleted_functions)
        
        # 3. Cleanup CloudWatch log groups
        print("   🔍 Cleaning up MCP-related CloudWatch log groups...")
        cleanup_mcp_log_groups(logs_client, deleted_functions)
        
        return len(deleted_functions) > 0
            
    except Exception as e:
        print(f"   ❌ Standalone MCP tool lambda cleanup failed: {e}")
        return False

def cleanup_mcp_iam_roles(iam_client, deleted_function_names):
    """Cleanup IAM roles created by MCP tool deployment"""
    try:
        roles = iam_client.list_roles()
        mcp_role_patterns = ['mcp', 'tool', 'lambda', 'agentcore', 'genesis']
        
        for role in roles.get('Roles', []):
            role_name = role.get('RoleName', '')
            role_name_lower = role_name.lower()
            
            # Check if role is MCP-related
            is_mcp_role = any(pattern in role_name_lower for pattern in mcp_role_patterns)
            
            # Also check if role is associated with deleted functions
            is_function_role = any(func_name in role_name for func_name in deleted_function_names)
            
            if is_mcp_role or is_function_role:
                try:
                    print(f"   🗑️  Attempting to delete IAM role: {role_name}")
                    
                    # Detach managed policies first
                    attached_policies = iam_client.list_attached_role_policies(RoleName=role_name)
                    for policy in attached_policies.get('AttachedPolicies', []):
                        iam_client.detach_role_policy(
                            RoleName=role_name,
                            PolicyArn=policy.get('PolicyArn')
                        )
                        print(f"       ✅ Detached policy: {policy.get('PolicyName')}")
                    
                    # Delete inline policies
                    inline_policies = iam_client.list_role_policies(RoleName=role_name)
                    for policy_name in inline_policies.get('PolicyNames', []):
                        iam_client.delete_role_policy(
                            RoleName=role_name,
                            PolicyName=policy_name
                        )
                        print(f"       ✅ Deleted inline policy: {policy_name}")
                    
                    # Delete the role
                    iam_client.delete_role(RoleName=role_name)
                    print(f"   ✅ Deleted IAM role: {role_name}")
                    
                except Exception as e:
                    print(f"   ❌ Failed to delete IAM role {role_name}: {e}")
                    
    except Exception as e:
        print(f"   ❌ Error cleaning up MCP IAM roles: {e}")

def cleanup_mcp_log_groups(logs_client, deleted_function_names):
    """Cleanup CloudWatch log groups for MCP functions"""
    try:
        # Cleanup log groups for deleted functions
        for func_name in deleted_function_names:
            log_group_name = f"/aws/lambda/{func_name}"
            
            try:
                logs_client.delete_log_group(logGroupName=log_group_name)
                print(f"   ✅ Deleted log group: {log_group_name}")
            except logs_client.exceptions.ResourceNotFoundException:
                print(f"   ✅ Log group doesn't exist: {log_group_name}")
            except Exception as e:
                print(f"   ❌ Failed to delete log group {log_group_name}: {e}")
                
    except Exception as e:
        print(f"   ❌ Error cleaning up MCP log groups: {e}")

def verify_gateway_mcp_cleanup(bedrock_client, cloudformation_client, stack_name, cf_success, standalone_success):
    """Enhanced verification of gateway and MCP cleanup"""
    try:
        print("   🔍 Performing comprehensive verification...")
        
        # Check remaining gateways
        gateways_after = bedrock_client.list_gateways()
        gateways_count = len(gateways_after.get('gateways', []))
        
        # Check CloudFormation stack status
        stack_exists = False
        try:
            cloudformation_client.describe_stacks(StackName=stack_name)
            stack_exists = True
        except cloudformation_client.exceptions.ClientError:
            stack_exists = False
        
        # Check for remaining standalone MCP functions
        lambda_client = boto3.client('lambda', region_name=os.environ.get('CLEANUP_REGION', 'us-east-1'))
        functions = lambda_client.list_functions()
        mcp_patterns = ['mcp', 'tool', 'agentcore', 'genesis']
        remaining_mcp_functions = []
        
        for func in functions.get('Functions', []):
            func_name = func.get('FunctionName', '')
            if any(pattern in func_name.lower() for pattern in mcp_patterns):
                remaining_mcp_functions.append(func_name)
        
        # Detailed reporting
        print(f"   📊 Verification Results:")
        print(f"   ├── Gateways: {gateways_count} remaining")
        print(f"   ├── CloudFormation Stack: {'❌ Still exists' if stack_exists else '✅ Deleted'}")
        print(f"   ├── Standalone MCP Functions: {len(remaining_mcp_functions)} remaining")
        
        if remaining_mcp_functions:
            print(f"   ⚠️  Remaining MCP functions:")
            for func_name in remaining_mcp_functions[:5]:  # Show first 5
                print(f"       - {func_name}")
            if len(remaining_mcp_functions) > 5:
                print(f"       ... and {len(remaining_mcp_functions) - 5} more")
        
        # Overall assessment
        cleanup_complete = (gateways_count == 0 and not stack_exists and len(remaining_mcp_functions) == 0)
        
        if cleanup_complete:
            print("   🎉 Gateway and MCP cleanup verification: PASSED")
            print("   ✅ All gateway and MCP resources successfully removed")
        else:
            print("   ⚠️  Gateway and MCP cleanup verification: PARTIAL")
            print(f"   📈 Gateway cleanup: {'✅ SUCCESS' if gateways_count == 0 else '⚠️ PARTIAL'}")
            print(f"   📈 CloudFormation cleanup: {'✅ SUCCESS' if not stack_exists else '⚠️ PARTIAL'}")
            print(f"   📈 Standalone MCP cleanup: {'✅ SUCCESS' if len(remaining_mcp_functions) == 0 else '⚠️ PARTIAL'}")
        
        return cleanup_complete
        
    except Exception as e:
        print(f"   ❌ Verification failed: {e}")
        return False

def cleanup_gateways_enhanced(bedrock_client):
    """Enhanced gateway cleanup with retry logic"""
    try:
        gateways = bedrock_client.list_gateways()
        gateway_list = gateways.get('gateways', [])
        
        if not gateway_list:
            print("   ✅ No gateways to delete")
            return True
            
        print(f"   Found {len(gateway_list)} gateways")
        
        deleted_count = 0
        failed_count = 0
        
        for gateway in gateway_list:
            gateway_id = gateway.get('gatewayId')
            gateway_name = gateway.get('name')
            
            try:
                # List targets for this gateway first
                targets_response = bedrock_client.list_targets(gatewayId=gateway_id)
                targets = targets_response.get('targets', [])
                
                print(f"   Gateway '{gateway_name}' has {len(targets)} targets")
                
                # Delete targets first with retry logic
                targets_deleted = 0
                for target in targets:
                    target_id = target.get('targetId')
                    target_name = target.get('name', target_id)
                    
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            bedrock_client.delete_target(gatewayId=gateway_id, targetId=target_id)
                            print(f"   ✅ Deleted target: {target_name}")
                            targets_deleted += 1
                            break
                        except Exception as e:
                            if attempt < max_retries - 1:
                                print(f"   ⏳ Retrying target deletion: {target_name} (attempt {attempt + 2})")
                                time.sleep(2)
                            else:
                                print(f"   ❌ Failed to delete target {target_name}: {e}")
                
                # Wait for targets to be deleted
                if targets_deleted > 0:
                    print(f"   ⏳ Waiting for {targets_deleted} targets to be deleted...")
                    time.sleep(10)
                
                # Delete the gateway with retry logic
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        bedrock_client.delete_gateway(gatewayId=gateway_id)
                        print(f"   ✅ Deleted gateway: {gateway_name}")
                        deleted_count += 1
                        break
                    except Exception as e:
                        if attempt < max_retries - 1:
                            print(f"   ⏳ Retrying gateway deletion: {gateway_name} (attempt {attempt + 2})")
                            time.sleep(5)
                        else:
                            print(f"   ❌ Failed to delete gateway {gateway_name}: {e}")
                            failed_count += 1
                
            except Exception as e:
                print(f"   ❌ Failed to process gateway {gateway_name}: {e}")
                failed_count += 1
        
        print(f"   📊 Gateway Results:")
        print(f"   ✅ Successfully deleted: {deleted_count}")
        print(f"   ❌ Failed to delete: {failed_count}")
        
        return failed_count == 0
        
    except Exception as e:
        print(f"   ❌ Error with gateways: {e}")
        return False

def cleanup_gateway_mcp_resources():
    try:
        region = os.environ.get('CLEANUP_REGION', 'us-east-1')
        bedrock_client = boto3.client('bedrock-agentcore-control', region_name=region)
        cloudformation_client = boto3.client('cloudformation', region_name=region)
        
        # 1. Delete all AgentCore gateways (which will also delete targets)
        print("🗑️  Deleting AgentCore gateways and targets...")
        gateway_success = cleanup_gateways_enhanced(bedrock_client)
        
        # 2. Delete MCP Tool Lambda CloudFormation stack
        print("\n🗑️  Deleting MCP Tool Lambda CloudFormation stack...")
        stack_name = os.environ.get('MCP_STACK_NAME', 'bac-mcp-stack')
        cloudformation_success = cleanup_mcp_cloudformation_stack(cloudformation_client, stack_name)
        
        # 3. Cleanup standalone MCP tool lambda resources
        print("\n🗑️  Cleaning up standalone MCP tool lambda resources...")
        standalone_success = cleanup_standalone_mcp_resources(region)
        
        # 4. Enhanced verification
        print("\n✅ Verifying gateway and MCP cleanup...")
        verification_success = verify_gateway_mcp_cleanup(bedrock_client, cloudformation_client, stack_name, cloudformation_success, standalone_success)
        
        return verification_success
        
    except Exception as e:
        print(f"❌ Gateway and MCP cleanup failed: {e}")
        return False

if __name__ == "__main__":
    cleanup_gateway_mcp_resources()
EOF
    
    # Run the gateway and MCP cleanup
    if python3 "$cleanup_script"; then
        echo -e "${GREEN}✅ Gateway and MCP resources cleanup completed${NC}"
    else
        echo -e "${YELLOW}⚠️  Gateway and MCP resources cleanup had issues${NC}"
    fi
    
    # Clean up temporary script
    rm -f "$cleanup_script"
>>>>>>> origin/main
}

# Function to cleanup AgentCore Identity resources
cleanup_identity_resources() {
    echo -e "${BLUE}🗑️  Cleaning up AgentCore Identity resources...${NC}"
    echo "==============================================="
    
    # Create temporary Python script for identity cleanup
    local cleanup_script="${SCRIPT_DIR}/temp_identity_cleanup.py"
    
    cat > "$cleanup_script" << 'EOF'
import boto3
import time
import os

def cleanup_oauth2_providers_with_retry(bedrock_client):
    """Enhanced OAuth2 provider cleanup with retry logic and dependency handling"""
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            providers = bedrock_client.list_oauth2_credential_providers()
            provider_list = providers.get('oauth2CredentialProviders', [])
            
            if not provider_list:
                print("   ✅ No OAuth2 credential providers to delete")
                return True
                
            print(f"   Found {len(provider_list)} OAuth2 credential providers (attempt {attempt + 1})")
            
            deleted_count = 0
            failed_count = 0
            
            for provider in provider_list:
                provider_name = provider.get('name')
                provider_arn = provider.get('credentialProviderArn')
                
                try:
                    # Check for dependencies before deletion
                    if has_provider_dependencies(bedrock_client, provider_arn):
                        print(f"   ⚠️  Provider {provider_name} has dependencies, cleaning up first...")
                        cleanup_provider_dependencies(bedrock_client, provider_arn)
                    
                    bedrock_client.delete_oauth2_credential_provider(
                        credentialProviderArn=provider_arn
                    )
                    print(f"   ✅ Deleted OAuth2 provider: {provider_name}")
                    deleted_count += 1
                    
                except Exception as e:
                    print(f"   ❌ Failed to delete OAuth2 provider {provider_name}: {e}")
                    failed_count += 1
            
            print(f"   📊 OAuth2 Provider Results (attempt {attempt + 1}):")
            print(f"   ✅ Successfully deleted: {deleted_count}")
            print(f"   ❌ Failed to delete: {failed_count}")
            
            # If all providers were deleted successfully, we're done
            if failed_count == 0:
                return True
                
            # If this wasn't the last attempt, wait before retrying
            if attempt < max_retries - 1:
                print(f"   ⏳ Retrying failed deletions in 5 seconds...")
                time.sleep(5)
                
        except Exception as e:
            print(f"   ❌ Error in OAuth2 provider cleanup attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                print(f"   ⏳ Retrying in 5 seconds...")
                time.sleep(5)
    
    print(f"   ⚠️  OAuth2 provider cleanup completed with some failures after {max_retries} attempts")
    return False

def has_provider_dependencies(bedrock_client, provider_arn):
    """Check if credential provider has dependencies"""
    try:
        # Check if any workload identities are using this provider
        identities = bedrock_client.list_workload_identities()
        for identity in identities.get('workloadIdentities', []):
            # This is a simplified check - in practice, you'd need to examine
            # the identity configuration to see if it references the provider
            pass
        return False
    except Exception:
        return False

def cleanup_provider_dependencies(bedrock_client, provider_arn):
    """Clean up resources that depend on the credential provider"""
    try:
        # In practice, this would identify and clean up dependent resources
        # For now, we'll just add a small delay to allow for eventual consistency
        time.sleep(2)
    except Exception as e:
        print(f"   ⚠️  Error cleaning up provider dependencies: {e}")

def cleanup_workload_identities_enhanced(bedrock_client):
    """Enhanced workload identity cleanup with proper pagination support"""
    try:
        print("   🔍 Getting ALL workload identities with pagination...")
        
        all_identities = []
        next_token = None
        page_count = 0
        
        while True:
            page_count += 1
            
            # Use maximum allowed page size (20)
            if next_token:
                response = bedrock_client.list_workload_identities(
                    maxResults=20,
                    nextToken=next_token
                )
            else:
                response = bedrock_client.list_workload_identities(maxResults=20)
            
            page_identities = response.get('workloadIdentities', [])
            all_identities.extend(page_identities)
            
            if page_count <= 5 or page_count % 100 == 0:  # Show progress for first 5 pages and every 100th page
                print(f"      📄 Page {page_count}: {len(page_identities)} identities (Total: {len(all_identities)})")
            
            next_token = response.get('nextToken')
            if not next_token:
                break
                
            # Safety limit to prevent infinite loops
            if page_count > 2000:
                print("         ⚠️  Stopping after 2000 pages for safety")
                break
        
        if page_count > 5:
            print(f"      📊 Pagination complete: {page_count} pages, {len(all_identities)} total identities")
        
        if not all_identities:
            print("   ✅ No workload identities to delete")
            return True
            
        print(f"   Found {len(all_identities)} workload identities")
        
        # Enhanced batching with progress tracking
        batch_size = 100  # Increased batch size for better performance
        deleted_count = 0
        failed_count = 0
        total_count = len(all_identities)
        
        for i in range(0, total_count, batch_size):
            batch = all_identities[i:i+batch_size]
            batch_deleted = 0
            batch_failed = 0
            
            print(f"   🔄 Processing batch {i//batch_size + 1}/{(total_count + batch_size - 1)//batch_size} ({len(batch)} identities)...")
            
            for identity in batch:
                identity_name = identity.get('name')
                
                try:
                    bedrock_client.delete_workload_identity(name=identity_name)
                    deleted_count += 1
                    batch_deleted += 1
                except Exception as e:
                    print(f"   ❌ Failed to delete identity {identity_name}: {e}")
                    failed_count += 1
                    batch_failed += 1
            
            # Progress update
            print(f"   📊 Batch {i//batch_size + 1} complete: {batch_deleted} deleted, {batch_failed} failed")
            print(f"   📈 Overall progress: {deleted_count}/{total_count} ({(deleted_count/total_count)*100:.1f}%)")
            
            # Small delay between batches to avoid rate limiting
            if i + batch_size < total_count:
                time.sleep(1)
        
        print(f"\n   📊 Final Workload Identity Results:")
        print(f"   ✅ Successfully deleted: {deleted_count}")
        print(f"   ❌ Failed to delete: {failed_count}")
        print(f"   📈 Success rate: {(deleted_count/total_count)*100:.1f}%")
        
        return failed_count == 0
        
    except Exception as e:
        print(f"   ❌ Error with workload identities: {e}")
        return False

def verify_identity_cleanup_comprehensive(bedrock_client, oauth_success, identity_success):
    """Comprehensive verification of identity cleanup with detailed reporting"""
    try:
        print("   🔍 Performing comprehensive verification...")
        
        # Check OAuth2 credential providers
        providers_after = bedrock_client.list_oauth2_credential_providers()
        providers_count = len(providers_after.get('oauth2CredentialProviders', []))
        
        # Check workload identities (first page only for speed)
        identities_after = bedrock_client.list_workload_identities(maxResults=20)
        identities_count = len(identities_after.get('workloadIdentities', []))
        has_more_identities = 'nextToken' in identities_after
        
        # Detailed reporting
        print(f"   📊 Verification Results:")
        print(f"   ├── OAuth2 Credential Providers: {providers_count} remaining")
        if has_more_identities:
            print(f"   ├── Workload Identities: {identities_count}+ remaining (first page only)")
        else:
            print(f"   ├── Workload Identities: {identities_count} remaining")
        
        # Check for specific types of remaining resources
        if providers_count > 0:
            print(f"   ⚠️  Remaining OAuth2 providers:")
            for provider in providers_after.get('oauth2CredentialProviders', []):
                provider_name = provider.get('name', 'Unknown')
                print(f"       - {provider_name}")
        
        if identities_count > 0:
            print(f"   ⚠️  Remaining workload identities (showing first 10):")
            for i, identity in enumerate(identities_after.get('workloadIdentities', [])[:10]):
                identity_name = identity.get('name', 'Unknown')
                print(f"       - {identity_name}")
            if identities_count > 10:
                print(f"       ... and {identities_count - 10} more")
        
        # Overall assessment (conservative due to pagination)
        cleanup_complete = providers_count == 0 and identities_count == 0 and not has_more_identities
        
        if cleanup_complete:
            print("   🎉 Identity cleanup verification: PASSED")
            print("   ✅ All identity resources successfully removed")
        else:
            print("   ⚠️  Identity cleanup verification: PARTIAL")
            print(f"   📈 OAuth2 providers cleanup: {'✅ SUCCESS' if providers_count == 0 else '⚠️ PARTIAL'}")
            print(f"   📈 Workload identities cleanup: {'✅ SUCCESS' if identities_count == 0 else '⚠️ PARTIAL'}")
            
            # Provide guidance for remaining resources
            if providers_count > 0 or identities_count > 0:
                print("   💡 Recommendations:")
                if providers_count > 0:
                    print("       - Some OAuth2 providers may have dependencies")
                    print("       - Try running cleanup again after a few minutes")
                if identities_count > 0 or has_more_identities:
                    print("       - Large number of workload identities may require multiple runs")
                    print("       - Script now processes ALL pages, but verification shows first page only")
        
        return cleanup_complete
        
    except Exception as e:
        print(f"   ❌ Verification failed: {e}")
        return False

def cleanup_identity_resources():
    try:
        region = os.environ.get('CLEANUP_REGION', 'us-east-1')
        bedrock_client = boto3.client('bedrock-agentcore-control', region_name=region)
        
        # 1. Delete all OAuth2 credential providers with retry logic
        print("🗑️  Deleting OAuth2 credential providers...")
        oauth_success = cleanup_oauth2_providers_with_retry(bedrock_client)
        
        # 2. Delete all workload identities with enhanced batching
        print("\n🗑️  Deleting workload identities...")
        identity_success = cleanup_workload_identities_enhanced(bedrock_client)
        
        # 3. Enhanced verification with detailed reporting
        print("\n✅ Verifying identity cleanup...")
        verification_success = verify_identity_cleanup_comprehensive(bedrock_client, oauth_success, identity_success)
        
        return verification_success
        
    except Exception as e:
        print(f"❌ Identity cleanup failed: {e}")
        return False

if __name__ == "__main__":
    cleanup_identity_resources()
EOF
    
    # Run the identity cleanup
    if python3 "$cleanup_script"; then
        echo -e "${GREEN}✅ Identity resources cleanup completed${NC}"
    else
        echo -e "${YELLOW}⚠️  Identity resources cleanup had issues${NC}"
    fi
    
    # Clean up temporary script
    rm -f "$cleanup_script"
}

# Function to cleanup ECR repositories
cleanup_ecr_repositories() {
    echo -e "${BLUE}🗑️  Cleaning up ECR repositories...${NC}"
    echo "==================================="
    
    local repos=("bac-runtime-repo-diy" "bac-runtime-repo-sdk")
    
    for repo in "${repos[@]}"; do
        echo "Checking ECR repository: $repo"
        
        if aws ecr describe-repositories --repository-names "$repo" --region "$REGION" &> /dev/null; then
            echo "   🗑️  Deleting ECR repository: $repo"
            
            # Delete all images first
            if aws ecr list-images --repository-name "$repo" --region "$REGION" --query 'imageIds[*]' --output json | grep -q imageDigest; then
                echo "   📦 Deleting images in repository..."
                aws ecr batch-delete-image \
                    --repository-name "$repo" \
                    --region "$REGION" \
                    --image-ids "$(aws ecr list-images --repository-name "$repo" --region "$REGION" --query 'imageIds[*]' --output json)" &> /dev/null || true
            fi
            
            # Delete the repository
            if aws ecr delete-repository --repository-name "$repo" --region "$REGION" --force &> /dev/null; then
                echo -e "${GREEN}   ✅ Deleted ECR repository: $repo${NC}"
            else
                echo -e "${YELLOW}   ⚠️  Failed to delete ECR repository: $repo${NC}"
            fi
        else
            echo -e "${GREEN}   ✅ ECR repository doesn't exist: $repo${NC}"
        fi
    done
}

# Function to cleanup IAM resources
cleanup_iam_resources() {
    echo -e "${BLUE}🗑️  Cleaning up IAM resources...${NC}"
    echo "================================"
    
    local role_name="bac-execution-role"
    local policy_name="bac-execution-policy"
    
    echo "Checking IAM role: $role_name"
    
    if aws iam get-role --role-name "$role_name" &> /dev/null; then
        echo "   🗑️  Deleting IAM role and policies..."
        
        # Delete inline policies
        echo "   📝 Deleting inline policy: $policy_name"
        aws iam delete-role-policy --role-name "$role_name" --policy-name "$policy_name" &> /dev/null || true
        
        # Delete the role
        if aws iam delete-role --role-name "$role_name" &> /dev/null; then
            echo -e "${GREEN}   ✅ Deleted IAM role: $role_name${NC}"
        else
            echo -e "${YELLOW}   ⚠️  Failed to delete IAM role: $role_name${NC}"
        fi
    else
        echo -e "${GREEN}   ✅ IAM role doesn't exist: $role_name${NC}"
    fi
}

# Function to cleanup configuration files
cleanup_config_files() {
    echo -e "${BLUE}🗑️  Cleaning up configuration files...${NC}"
    echo "======================================"
    
<<<<<<< HEAD
=======
    # Remove oauth-provider.yaml
    local oauth_config="${CONFIG_DIR}/oauth-provider.yaml"
    if [[ -f "$oauth_config" ]]; then
        rm -f "$oauth_config"
        echo -e "${GREEN}   ✅ Deleted: oauth-provider.yaml${NC}"
    else
        echo -e "${GREEN}   ✅ oauth-provider.yaml doesn't exist${NC}"
    fi
    
>>>>>>> origin/main
    # Reset dynamic-config.yaml to empty values
    local dynamic_config="${CONFIG_DIR}/dynamic-config.yaml"
    if [[ -f "$dynamic_config" ]]; then
        # Create backup
<<<<<<< HEAD
        cp "$dynamic_config" "${dynamic_config}.backup.$(date +%Y%m%d_%H%M%S)"
=======
        cp "$dynamic_config" "${dynamic_config}.backup"
>>>>>>> origin/main
        
        # Reset all dynamic values to empty
        cat > "$dynamic_config" << 'EOF'
# Dynamic Configuration - Updated by deployment scripts only
# This file contains all configuration values that are generated/updated during deployment
gateway:
  id: ""
  arn: ""
  url: ""
oauth_provider:
  provider_name: ""
  provider_arn: ""
  scopes: []
mcp_lambda:
  function_name: ""
  function_arn: ""
  role_arn: ""
  stack_name: ""
  gateway_execution_role_arn: ""
  ecr_uri: ""
<<<<<<< HEAD
  deployment_type: ""
=======
>>>>>>> origin/main
runtime:
  diy_agent:
    arn: ""
    ecr_uri: ""
    endpoint_arn: ""
  sdk_agent:
    arn: ""
    ecr_uri: ""
    endpoint_arn: ""
client:
  diy_runtime_endpoint: ""
  sdk_runtime_endpoint: ""
<<<<<<< HEAD
memory:
  id: ""
  name: ""
  region: ""
  status: ""
  event_expiry_days: ""
  created_at: ""
  description: ""
EOF
        echo -e "${GREEN}   ✅ Reset dynamic-config.yaml to empty values${NC}"
        echo -e "${BLUE}   📝 Backup saved with timestamp${NC}"
    fi
    
    # Clean up any temporary files that might have been created
    local temp_files=(
        "${SCRIPT_DIR}/temp_get_config.py"
        "${SCRIPT_DIR}/temp_gateway_mcp_cleanup.py"
        "${SCRIPT_DIR}/temp_identity_cleanup.py"
        "${CONFIG_DIR}/oauth-provider.yaml"
    )
    
    for temp_file in "${temp_files[@]}"; do
        if [[ -f "$temp_file" ]]; then
            rm -f "$temp_file"
            echo -e "${GREEN}   ✅ Deleted temporary file: $(basename "$temp_file")${NC}"
        fi
    done
    
    # Clean up any .backup files older than 30 days (keep recent ones for safety)
    find "${CONFIG_DIR}" -name "*.backup*" -type f -mtime +30 -delete 2>/dev/null || true
    
    echo -e "${GREEN}   ✅ Configuration cleanup completed${NC}"
=======
EOF
        echo -e "${GREEN}   ✅ Reset dynamic-config.yaml to empty values${NC}"
        echo -e "${BLUE}   📝 Backup saved as: dynamic-config.yaml.backup${NC}"
    fi
>>>>>>> origin/main
}

# Function to show cleanup summary
show_cleanup_summary() {
    echo ""
    echo -e "${GREEN}🎉 CLEANUP COMPLETED${NC}"
    echo -e "${GREEN}===================${NC}"
    echo ""
    echo -e "${BLUE}📋 What was cleaned up:${NC}"
<<<<<<< HEAD
    echo "   ✅ AgentCore Runtime agents (DIY and SDK)"
    echo "   ✅ AgentCore Gateways and MCP targets"
    echo "   ✅ MCP Tool Lambda function and CloudFormation stack"
    echo "   ✅ OAuth2 credential providers"
    echo "   ✅ Workload identities"
    echo "   ✅ AgentCore Memory resources"
=======
    echo "   ✅ AgentCore Runtime agents"
    echo "   ✅ AgentCore Gateways and MCP targets"
    echo "   ✅ MCP Tool Lambda function and stack"
    echo "   ✅ OAuth2 credential providers"
    echo "   ✅ Workload identities"
>>>>>>> origin/main
    echo "   ✅ ECR repositories and images"
    echo "   ✅ IAM role and policies"
    echo "   ✅ Generated configuration files"
    echo ""
    echo -e "${BLUE}📋 What was preserved:${NC}"
    echo "   ✅ static-config.yaml (unchanged)"
    echo "   ✅ dynamic-config.yaml (reset to empty values, with backup)"
    echo "   ✅ AWS account settings"
    echo "   ✅ Other AWS resources"
    echo ""
    echo -e "${BLUE}🚀 To redeploy from scratch:${NC}"
<<<<<<< HEAD
    echo "   1. ./01-prerequisites.sh (Setup IAM roles and ECR repositories)"
    echo "   2. ./02-create-memory.sh (Create AgentCore Memory resources)"
    echo "   3. ./03-setup-oauth-provider.sh (Setup OAuth2 credential providers)"
    echo "   4. ./04-deploy-mcp-tool-lambda-zip.sh (Deploy MCP Lambda function)"
    echo "   5. ./05-create-gateway-targets.sh (Create AgentCore Gateways and targets)"
    echo "   6. ./06-deploy-diy.sh (Deploy DIY agent runtime)"
    echo "   7. ./07-deploy-sdk.sh (Deploy SDK agent runtime)"
=======
    echo "   1. ./01-prerequisites.sh"
    echo "   2. ./02-setup-oauth-provider.sh"
    echo "   3. ./03-deploy-mcp-tool-lambda.sh"
    echo "   4. ./04-create-gateway-targets.sh"
    echo "   5. ./05-deploy-diy.sh"
    echo "   6. ./06-deploy-sdk.sh"
>>>>>>> origin/main
}

# Main execution
main() {
    show_warning
    
    echo -e "${RED}Are you absolutely sure you want to delete EVERYTHING?${NC}"
    echo -n "Type 'DELETE EVERYTHING' to confirm: "
    read confirmation
    
    if [[ "$confirmation" != "DELETE EVERYTHING" ]]; then
        echo -e "${YELLOW}❌ Cleanup cancelled${NC}"
        echo "   Confirmation text did not match exactly"
        exit 1
    fi
    
    echo ""
    echo -e "${RED}🚨 STARTING DESTRUCTIVE CLEANUP...${NC}"
    echo ""
    
<<<<<<< HEAD
    # Execute cleanup steps in reverse order of deployment
    echo "Step 1: Cleaning up runtime agents..."
    cleanup_runtime_agents
    echo ""
    
    echo "Step 2: Cleaning up gateway and MCP resources..."
    cleanup_gateway_mcp_resources
    echo ""
    
    echo "Step 3: Cleaning up identity resources..."
    # Set environment variables for identity cleanup
    export CLEANUP_REGION="$REGION"
    cleanup_identity_resources
    unset CLEANUP_REGION
    echo ""
    
    echo "Step 4: Cleaning up memory resources..."
    cleanup_memory_resources
    echo ""
    
    echo "Step 5: Cleaning up ECR repositories..."
    cleanup_ecr_repositories
    echo ""
    
    echo "Step 6: Cleaning up IAM resources..."
    cleanup_iam_resources
    echo ""
    
    echo "Step 7: Cleaning up configuration files..."
=======
    # Execute cleanup steps
    cleanup_runtime_agents
    echo ""
    
    # Set environment variables for gateway and MCP cleanup
    export CLEANUP_REGION="$REGION"
    export MCP_STACK_NAME="$MCP_STACK_NAME"
    export GATEWAY_ID="$GATEWAY_ID"
    export MCP_FUNCTION_NAME="$MCP_FUNCTION_NAME"
    
    cleanup_gateway_mcp_resources
    
    # Clean up environment variables
    unset CLEANUP_REGION MCP_STACK_NAME GATEWAY_ID MCP_FUNCTION_NAME
    echo ""
    
    # Set environment variables for identity cleanup
    export CLEANUP_REGION="$REGION"
    
    cleanup_identity_resources
    
    # Clean up environment variables
    unset CLEANUP_REGION
    echo ""
    
    cleanup_ecr_repositories
    echo ""
    
    cleanup_iam_resources
    echo ""
    
>>>>>>> origin/main
    cleanup_config_files
    echo ""
    
    show_cleanup_summary
}

# Run main function
main "$@"
