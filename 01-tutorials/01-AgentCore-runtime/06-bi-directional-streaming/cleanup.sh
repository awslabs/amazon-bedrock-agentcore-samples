#!/bin/bash

# ============================================================================
# Session Lifecycle Best Practices — Cleanup Script
# ============================================================================
# AgentCore Runtime sessions consume memory (measured in GBHours) while active.
# Billing continues until the session is explicitly stopped or the runtime is
# deleted. This cleanup script follows the recommended teardown ordering:
#
#   1. Stop active runtime sessions  (stop-runtime-session — data plane)
#   2. Delete the agent runtime      (delete-agent-runtime — control plane)
#   3. Delete ECR repository          (remove container images)
#   4. Delete IAM role & policy       (remove authorization last)
#   5. Delete other resources          (Cognito, config files, etc.)
#
# The agent runtime MUST be deleted before the IAM role to prevent a window
# where the runtime exists without proper authorization controls.
#
# Each cleanup step uses `|| echo "warning"` so that a failure in one step
# does not prevent the remaining steps from executing.
# ============================================================================

# Disable set -e for cleanup — we want every step to attempt execution even
# if a previous step fails. This prevents orphaned resources and cost leaks.
set +e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track whether any cleanup step failed
CLEANUP_ERRORS=0

# Trap handler: ensure we report cleanup status even on SIGINT/SIGTERM
trap 'echo ""; echo -e "${YELLOW}⚠️  Cleanup interrupted — some resources may not have been deleted.${NC}"; echo "   Re-run this script to retry cleanup of remaining resources."; exit 1' INT TERM

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

# ============================================================================
# Step 1: Stop active runtime sessions (data plane)
# ============================================================================
# In production, use stop-runtime-session to end individual user sessions
# while keeping the runtime alive. For tutorial cleanup we proceed directly
# to deleting the runtime, but the pattern is documented here for reference.
#
# If you captured a runtimeSessionId during invocation, stop it first:
#   aws bedrock-agentcore stop-runtime-session \
#       --agent-runtime-arn "$AGENT_ARN" \
#       --runtime-session-id "<your-session-id>" \
#       --qualifier DEFAULT \
#       --region $AWS_REGION \
#       --no-cli-pager
#
# This releases the session's microVM resources immediately rather than
# waiting for the idle timeout to expire. delete-agent-runtime (Step 2)
# will also terminate any remaining sessions as part of full teardown.
# ============================================================================

# ============================================================================
# Step 2: Delete the agent runtime (control plane) — stops billing (GBHours)
# ============================================================================
# This tears down the entire runtime deployment including all active sessions,
# endpoints, and infrastructure. Must happen BEFORE IAM/ECR cleanup.
# ============================================================================
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
            echo "   ⚠️ Agent runtime deletion failed with exit code: $DELETE_EXIT_CODE"
            echo "   Error output: $DELETE_OUTPUT"
            CLEANUP_ERRORS=$((CLEANUP_ERRORS + 1))
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
        CLEANUP_ERRORS=$((CLEANUP_ERRORS + 1))
    else
        echo "   ✅ Verified: Agent runtime no longer exists"
    fi
else
    echo "ℹ️  No AGENT_ARN provided, skipping agent deletion"
fi

# ============================================================================
# Step 3: Delete ECR repository (remove container images)
# ============================================================================
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
    --no-cli-pager 2>/dev/null \
    && echo "✅ ECR repository deleted" \
    || { echo "⚠️  ECR repository deletion failed or already deleted"; CLEANUP_ERRORS=$((CLEANUP_ERRORS + 1)); }

# ============================================================================
# Step 4: Delete IAM role & policy (remove authorization last)
# ============================================================================
# IAM is deleted AFTER the agent runtime to prevent a window where the runtime
# exists without proper authorization controls.
# ============================================================================
echo "🔐 Deleting IAM role: $IAM_ROLE_NAME..."
aws iam delete-role-policy \
    --role-name $IAM_ROLE_NAME \
    --policy-name ${IAM_ROLE_NAME}Policy \
    --no-cli-pager 2>/dev/null \
    || echo "⚠️  Policy deletion failed or already deleted"

aws iam delete-role \
    --role-name $IAM_ROLE_NAME \
    --no-cli-pager 2>/dev/null \
    || echo "⚠️  Role deletion failed or already deleted"

# ============================================================================
# Step 5: Delete other resources (Cognito, config files)
# ============================================================================

# Delete Cognito user pool (if POOL_ID is provided)
if [ -n "$POOL_ID" ]; then
    echo "🔑 Deleting Cognito user pool: $POOL_ID"
    aws cognito-idp delete-user-pool \
        --user-pool-id "$POOL_ID" \
        --region $AWS_REGION \
        --no-cli-pager 2>/dev/null \
        && echo "   ✅ Cognito pool deleted" \
        || echo "   ⚠️  Cognito deletion failed or already deleted"
fi

# Delete configuration file
if [ -f "$CONFIG_FILE" ]; then
    echo "🗑️  Deleting configuration file: $CONFIG_FILE"
    rm -f "$CONFIG_FILE"
    echo "   ✅ Configuration file deleted"
fi

echo ""
if [ $CLEANUP_ERRORS -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Cleanup completed with $CLEANUP_ERRORS warning(s). Re-run to retry failed steps.${NC}"
else
    echo "✅ Cleanup complete!"
fi
echo ""
echo "💡 Resources cleaned up:"
if [ -n "$AGENT_ARN" ]; then
    echo "   - Agent: $AGENT_ARN"
fi
echo "   - ECR Repository: $ECR_REPO_NAME"
echo "   - IAM Role: $IAM_ROLE_NAME"
if [ -n "$POOL_ID" ]; then
    echo "   - Cognito User Pool: $POOL_ID"
fi
echo "   - Configuration file: $CONFIG_FILE"
