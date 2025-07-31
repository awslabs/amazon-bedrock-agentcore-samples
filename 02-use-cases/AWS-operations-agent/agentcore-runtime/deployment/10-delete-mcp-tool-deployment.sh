#!/bin/bash

# Delete MCP Tool Lambda deployment
echo "🗑️  Deleting MCP Tool Lambda deployment..."

# Configuration - Get project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"  # Go up two levels to reach AgentCore root
CONFIG_DIR="${PROJECT_DIR}/config"

# Load configuration from YAML (fallback if yq not available)
if command -v yq >/dev/null 2>&1; then
    REGION=$(yq eval '.aws.region' "${CONFIG_DIR}/static-config.yaml")
    ACCOUNT_ID=$(yq eval '.aws.account_id' "${CONFIG_DIR}/static-config.yaml")
    STACK_NAME=$(yq eval '.mcp_lambda.stack_name' "${CONFIG_DIR}/dynamic-config.yaml" 2>/dev/null)
else
    echo "⚠️  yq not found, using default values from existing config"
    # Fallback: extract from YAML using grep/sed
    REGION=$(grep "region:" "${CONFIG_DIR}/static-config.yaml" | head -1 | sed 's/.*region: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/')
    ACCOUNT_ID=$(grep "account_id:" "${CONFIG_DIR}/static-config.yaml" | head -1 | sed 's/.*account_id: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/')
    STACK_NAME=$(grep "stack_name:" "${CONFIG_DIR}/dynamic-config.yaml" | head -1 | sed 's/.*stack_name: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/' 2>/dev/null)
fi

# Default stack name if not found in config
if [[ -z "$STACK_NAME" || "$STACK_NAME" == "null" ]]; then
    STACK_NAME="bac-mcp-stack"
    echo "⚠️  Stack name not found in config, using default: $STACK_NAME"
fi

echo "📝 Configuration:"
echo "   Region: $REGION"
echo "   Account ID: $ACCOUNT_ID"
echo "   Stack Name: $STACK_NAME"
echo ""

# Get AWS credentials
echo "🔐 Getting AWS credentials..."
if [ -n "$AWS_PROFILE" ]; then
    echo "Using AWS profile: $AWS_PROFILE"
else
    echo "Using default AWS credentials"
fi

# Use configured AWS profile if specified in static config
AWS_PROFILE_CONFIG=$(grep "aws_profile:" "${CONFIG_DIR}/static-config.yaml" | head -1 | sed 's/.*aws_profile: *["'\'']*\([^"'\''#]*\)["'\'']*.*$/\1/' | xargs 2>/dev/null)
if [[ -n "$AWS_PROFILE_CONFIG" && "$AWS_PROFILE_CONFIG" != "\"\"" && "$AWS_PROFILE_CONFIG" != "''" ]]; then
    echo "Using configured AWS profile: $AWS_PROFILE_CONFIG"
    export AWS_PROFILE="$AWS_PROFILE_CONFIG"
fi

# Function to check if stack exists
check_stack_exists() {
    local stack_name="$1"
    aws cloudformation describe-stacks --stack-name "$stack_name" --region "$REGION" --output text --query 'Stacks[0].StackStatus' 2>/dev/null
}

# Function to get stack resources before deletion
get_stack_resources() {
    local stack_name="$1"
    echo "📋 Getting stack resources before deletion..."
    
    STACK_RESOURCES=$(aws cloudformation describe-stack-resources \
        --stack-name "$stack_name" \
        --region "$REGION" \
        --output json 2>/dev/null || echo "{}")
    
    if [[ "$STACK_RESOURCES" != "{}" ]]; then
        echo "   Resources in stack:"
        echo "$STACK_RESOURCES" | jq -r '.StackResources[]? | "      • \(.ResourceType): \(.LogicalResourceId) (\(.PhysicalResourceId // "N/A"))"' 2>/dev/null || echo "      • Could not parse resources"
    else
        echo "   ⚠️  Could not retrieve stack resources"
    fi
}

# Function to clean up dynamic configuration
cleanup_dynamic_config() {
    echo "🧹 Cleaning up dynamic configuration..."
    
    DYNAMIC_CONFIG="${CONFIG_DIR}/dynamic/infrastructure.yaml"
    
    if [[ -f "$DYNAMIC_CONFIG" ]]; then
        if command -v yq >/dev/null 2>&1; then
            yq eval ".mcp_lambda.function_arn = \"\"" -i "$DYNAMIC_CONFIG"
            yq eval ".mcp_lambda.function_name = \"\"" -i "$DYNAMIC_CONFIG"
            yq eval ".mcp_lambda.function_role_arn = \"\"" -i "$DYNAMIC_CONFIG"
            yq eval ".mcp_lambda.gateway_execution_role_arn = \"\"" -i "$DYNAMIC_CONFIG"
            yq eval ".mcp_lambda.stack_name = \"\"" -i "$DYNAMIC_CONFIG"
            yq eval ".mcp_lambda.ecr_uri = \":latest\"" -i "$DYNAMIC_CONFIG"
        else
            # Fallback: manual update using sed
            sed -i.bak "s|function_arn: \".*\"|function_arn: \"\"|" "$DYNAMIC_CONFIG"
            sed -i.bak "s|function_name: \".*\"|function_name: \"\"|" "$DYNAMIC_CONFIG"
            sed -i.bak "s|function_role_arn: \".*\"|function_role_arn: \"\"|" "$DYNAMIC_CONFIG"
            sed -i.bak "s|gateway_execution_role_arn: \".*\"|gateway_execution_role_arn: \"\"|" "$DYNAMIC_CONFIG"
            sed -i.bak "s|stack_name: \".*\"|stack_name: \"\"|" "$DYNAMIC_CONFIG"
            sed -i.bak "s|ecr_uri: \".*\"|ecr_uri: \":latest\"|" "$DYNAMIC_CONFIG"
            
            # Remove backup file
            rm -f "${DYNAMIC_CONFIG}.bak"
        fi
        
        echo "✅ Dynamic configuration cleared"
    else
        echo "⚠️  Dynamic configuration file not found: $DYNAMIC_CONFIG"
    fi
}

# Main execution
echo "⚠️  WARNING: This will delete the MCP Tool Lambda deployment!"
echo "   This includes:"
echo "   • Lambda function: dev-bedrock-agentcore-mcp-tool"
echo "   • IAM roles: MCPToolFunctionRole and BedrockAgentCoreGatewayExecutionRole"
echo "   • CloudWatch log group"
echo "   • CloudFormation stack: $STACK_NAME"
echo ""
echo "   This action cannot be undone."
echo ""
read -p "Are you sure you want to continue? (y/N): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "🚀 Starting MCP Tool deletion process..."
    echo ""
    
    # Check if stack exists
    STACK_STATUS=$(check_stack_exists "$STACK_NAME")
    
    if [[ -n "$STACK_STATUS" ]]; then
        echo "✅ Found CloudFormation stack: $STACK_NAME (Status: $STACK_STATUS)"
        echo ""
        
        # Get stack resources before deletion
        get_stack_resources "$STACK_NAME"
        echo ""
        
        # Delete the CloudFormation stack
        echo "🗑️  Deleting CloudFormation stack: $STACK_NAME..."
        aws cloudformation delete-stack --stack-name "$STACK_NAME" --region "$REGION"
        
        if [[ $? -eq 0 ]]; then
            echo "✅ Stack deletion initiated successfully"
            echo ""
            echo "⏳ Waiting for stack deletion to complete..."
            echo "   This may take several minutes..."
            
            # Wait for stack deletion to complete
            aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME" --region "$REGION"
            
            if [[ $? -eq 0 ]]; then
                echo "✅ Stack deletion completed successfully"
            else
                echo "⚠️  Stack deletion may have failed or timed out"
                echo "   Check AWS Console for current status"
            fi
        else
            echo "❌ Failed to initiate stack deletion"
            exit 1
        fi
    else
        echo "⚠️  CloudFormation stack not found: $STACK_NAME"
        echo "   Stack may have already been deleted"
    fi
    
    echo ""
    
    # Clean up dynamic configuration
    cleanup_dynamic_config
    
    echo ""
    echo "🎉 MCP Tool Lambda Deletion Complete!"
    echo "===================================="
    echo ""
    echo "✅ CloudFormation stack deleted: $STACK_NAME"
    echo "✅ Dynamic configuration cleared"
    echo ""
    echo "📋 What was deleted:"
    echo "   • Lambda function: dev-bedrock-agentcore-mcp-tool"
    echo "   • IAM role: MCPToolFunctionRole (for Lambda execution)"
    echo "   • IAM role: BedrockAgentCoreGatewayExecutionRole (for Gateway)"
    echo "   • CloudWatch log group: /aws/lambda/dev-bedrock-agentcore-mcp-tool"
    echo "   • ECR repository and images (if created)"
    echo "   • CloudFormation stack: $STACK_NAME"
    echo ""
    echo "💡 Note:"
    echo "   • AgentCore Gateways and Targets are NOT deleted"
    echo "   • OAuth provider configuration is still available"
    echo "   • Static configuration is unchanged"
    echo ""
    echo "🚀 To redeploy the MCP Tool Lambda:"
    echo "   Run ./03-deploy-mcp-tool-lambda.sh"
    echo ""
    echo "⚠️  If you have active gateways using this Lambda:"
    echo "   Run ./97-delete-all-gateways-targets.sh first"
    echo "   Then redeploy both Lambda and gateways"
    echo ""
else
    echo ""
    echo "❌ Deletion cancelled by user"
    echo ""
fi
