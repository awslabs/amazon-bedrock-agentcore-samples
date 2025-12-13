#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse command line arguments
WEBSOCKET_FOLDER=""

usage() {
    echo "Usage: $0 <websocket-folder>"
    echo ""
    echo "Arguments:"
    echo "  websocket-folder    Folder containing the setup config (strands, echo, or sonic)"
    echo ""
    echo "Example:"
    echo "  ./cleanup.sh strands"
    echo ""
    exit 1
}

# Check if folder argument is provided
if [ $# -eq 0 ]; then
    echo -e "${RED}❌ Error: websocket folder argument is required${NC}"
    echo ""
    usage
fi

WEBSOCKET_FOLDER="$1"

# Validate folder exists
if [ ! -d "./$WEBSOCKET_FOLDER" ]; then
    echo -e "${RED}❌ Error: Folder not found: ./$WEBSOCKET_FOLDER${NC}"
    echo ""
    echo "Available folders:"
    for dir in strands echo sonic; do
        if [ -d "./$dir" ]; then
            echo "  - $dir"
        fi
    done
    echo ""
    exit 1
fi

echo "🧹 Cleaning up WebSocket resources..."
echo "📁 Using folder: $WEBSOCKET_FOLDER"
echo ""

# Check for configuration file in the specified folder
CONFIG_FILE="./$WEBSOCKET_FOLDER/setup_config.json"

if [ -f "$CONFIG_FILE" ]; then
    echo "📋 Loading configuration from $CONFIG_FILE..."
    
    # Load values from JSON file
    export AWS_REGION=$(jq -r '.aws_region' "$CONFIG_FILE")
    export ACCOUNT_ID=$(jq -r '.account_id' "$CONFIG_FILE")
    export IAM_ROLE_NAME=$(jq -r '.iam_role_name' "$CONFIG_FILE")
    export ECR_REPO_NAME=$(jq -r '.ecr_repo_name' "$CONFIG_FILE")
    export AGENT_ARN=$(jq -r '.agent_arn' "$CONFIG_FILE")
    
    echo "✅ Configuration loaded from file"
else
    echo "⚠️  No configuration file found at $CONFIG_FILE"
    echo "   Using environment variables or defaults..."
    
    # Set environment variables with defaults
    export AWS_REGION=${AWS_REGION:-us-east-1}
    export IAM_ROLE_NAME=${IAM_ROLE_NAME:-WebSocketSonicAgentRole}
    export ECR_REPO_NAME=${ECR_REPO_NAME:-agentcore_strands_images}
fi


# Display all variables that will be used for cleanup
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 Cleanup Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Required Variables:"
echo "   AWS_REGION:                    ${AWS_REGION}"
echo "   IAM_ROLE_NAME:                 ${IAM_ROLE_NAME}"
echo "   ECR_REPO_NAME:                 ${ECR_REPO_NAME}"
echo ""
echo "Optional Variables:"
echo "   AGENT_ARN:                     ${AGENT_ARN:-<not set>}"
echo "   POOL_ID:                       ${POOL_ID:-<not set>}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Delete agents
if [ -n "$AGENT_ARN" ]; then
    AGENT_ID=$(echo "$AGENT_ARN" | cut -d'/' -f2)
    echo "🤖 Deleting agent runtime: $AGENT_ID"
    
    # Try to get agent details first
    echo "   🔍 Checking if agent runtime exists..."
    if aws bedrock-agentcore-control get-agent-runtime \
        --agent-runtime-id "$AGENT_ID" \
        --region $AWS_REGION \
        --no-cli-pager 2>&1; then
        
        echo "   ✅ Agent runtime found, attempting deletion..."
        
        # Try to delete the agent runtime
        DELETE_OUTPUT=$(aws bedrock-agentcore-control delete-agent-runtime \
            --agent-runtime-id "$AGENT_ID" \
            --region $AWS_REGION \
            --no-cli-pager 2>&1)
        
        DELETE_EXIT_CODE=$?
        
        if [ $DELETE_EXIT_CODE -eq 0 ]; then
            echo "   ✅ Agent runtime deleted successfully"
        else
            echo "   ❌ Agent runtime deletion failed with exit code: $DELETE_EXIT_CODE"
            echo "   Error output: $DELETE_OUTPUT"
        fi
    else
        echo "   ℹ️  Agent runtime not found or already deleted"
    fi
    
    # Wait a moment for deletion to propagate
    echo "   ⏳ Waiting for deletion to propagate..."
    sleep 2
    
    # Verify deletion
    echo "   🔍 Verifying deletion..."
    if aws bedrock-agentcore-control get-agent-runtime \
        --agent-runtime-id "$AGENT_ID" \
        --region $AWS_REGION \
        --no-cli-pager >/dev/null 2>&1; then
        echo "   ⚠️  WARNING: Agent runtime still exists after deletion attempt"
    else
        echo "   ✅ Verified: Agent runtime no longer exists"
    fi
else
    echo "ℹ️  No AGENT_ARN provided, skipping agent deletion"
fi

# Delete IAM role
echo "🔐 Deleting IAM role: $IAM_ROLE_NAME..."
aws iam delete-role-policy \
    --role-name $IAM_ROLE_NAME \
    --policy-name ${IAM_ROLE_NAME}Policy \
    --no-cli-pager 2>/dev/null || echo "⚠️  Policy deletion failed or already deleted"

aws iam delete-role \
    --role-name $IAM_ROLE_NAME \
    --no-cli-pager 2>/dev/null || echo "⚠️  Role deletion failed or already deleted"

# Delete Cognito user pool (if POOL_ID is provided)
if [ -n "$POOL_ID" ]; then
    echo "🔑 Deleting Cognito user pool: $POOL_ID"
    aws cognito-idp delete-user-pool \
        --user-pool-id "$POOL_ID" \
        --region $AWS_REGION \
        --no-cli-pager 2>/dev/null && echo "   ✅ Cognito pool deleted" || echo "   ⚠️  Cognito deletion failed or already deleted"
fi

# Delete ECR repository
echo "🐳 Deleting ECR repository: $ECR_REPO_NAME"
# First, delete all images in the repository
aws ecr list-images \
    --repository-name $ECR_REPO_NAME \
    --region $AWS_REGION \
    --query 'imageIds[*]' \
    --output json \
    --no-cli-pager 2>/dev/null | \
    jq -r '.[] | "\(.imageDigest)"' 2>/dev/null | \
    while read digest; do
        if [ ! -z "$digest" ] && [ "$digest" != "null" ]; then
            aws ecr batch-delete-image \
                --repository-name $ECR_REPO_NAME \
                --image-ids imageDigest=$digest \
                --region $AWS_REGION \
                --no-cli-pager 2>/dev/null || true
        fi
    done

# Delete the repository
aws ecr delete-repository \
    --repository-name $ECR_REPO_NAME \
    --region $AWS_REGION \
    --force \
    --no-cli-pager 2>/dev/null && echo "✅ ECR repository deleted" || echo "⚠️  ECR repository deletion failed or already deleted"

# Delete configuration file
if [ -f "$CONFIG_FILE" ]; then
    echo "🗑️  Deleting configuration file: $CONFIG_FILE"
    rm -f "$CONFIG_FILE"
    echo "   ✅ Configuration file deleted"
fi

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "💡 Resources cleaned up:"
if [ -n "$POOL_ID" ]; then
    echo "   - Cognito User Pool: $POOL_ID"
fi
echo "   - IAM Role: $IAM_ROLE_NAME"
if [ -n "$AGENT_ARN" ]; then
    echo "   - Agent: $AGENT_ARN"
fi
echo "   - ECR Repository: $ECR_REPO_NAME"
echo "   - Configuration file: $CONFIG_FILE"
