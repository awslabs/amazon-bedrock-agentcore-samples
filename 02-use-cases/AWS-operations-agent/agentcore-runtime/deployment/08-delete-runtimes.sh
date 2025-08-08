#!/bin/bash

# Delete all AgentCore Runtimes
echo "🗑️  Deleting all AgentCore Runtimes..."

# Configuration - Get project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"  # Go up two levels to reach AgentCore root
RUNTIME_DIR="$(dirname "$SCRIPT_DIR")"  # agentcore-runtime directory
CONFIG_DIR="${PROJECT_DIR}/config"

# Load configuration from YAML (fallback if yq not available)
if command -v yq >/dev/null 2>&1; then
    REGION=$(yq eval '.aws.region' "${CONFIG_DIR}/static-config.yaml")
    ACCOUNT_ID=$(yq eval '.aws.account_id' "${CONFIG_DIR}/static-config.yaml")
else
    echo "⚠️  yq not found, using default values from existing config"
    # Fallback: extract from YAML using grep/sed
    REGION=$(grep "region:" "${CONFIG_DIR}/static-config.yaml" | head -1 | sed 's/.*region: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/')
    ACCOUNT_ID=$(grep "account_id:" "${CONFIG_DIR}/static-config.yaml" | head -1 | sed 's/.*account_id: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/')
fi

echo "📝 Configuration:"
echo "   Region: $REGION"
echo "   Account ID: $ACCOUNT_ID"
echo ""

# Get AWS credentials
echo "🔐 Getting AWS credentials..."
if [ -n "$AWS_PROFILE" ]; then
    echo "   Using AWS profile: $AWS_PROFILE"
    aws configure list --profile "$AWS_PROFILE"
else
    echo "   Using default AWS credentials"
    aws configure list
fi

# Check AWS credentials
echo "🔍 Verifying AWS credentials..."
if aws sts get-caller-identity --region "$REGION" >/dev/null 2>&1; then
    CALLER_IDENTITY=$(aws sts get-caller-identity --region "$REGION" 2>/dev/null)
    CURRENT_ACCOUNT=$(echo "$CALLER_IDENTITY" | grep -o '"Account": "[^"]*"' | cut -d'"' -f4)
    echo "✅ AWS credentials configured"
    echo "   Current Account: $CURRENT_ACCOUNT"
    echo "   Target Account: $ACCOUNT_ID"
    
    if [ "$CURRENT_ACCOUNT" != "$ACCOUNT_ID" ]; then
        echo "⚠️  Warning: Current account ($CURRENT_ACCOUNT) differs from config account ($ACCOUNT_ID)"
        echo "   Proceeding with current account credentials..."
    fi
else
    echo "❌ AWS credentials not configured or invalid"
    echo "   Please run: aws configure or aws sso login --profile <your-profile>"
    echo "   Current AWS config:"
    aws configure list
    exit 1
fi
echo ""

# Function to delete runtime
delete_runtime() {
    local runtime_arn="$1"
    local runtime_name="$2"
    
    if [ -z "$runtime_arn" ]; then
        echo "   ⚠️  No $runtime_name runtime ARN found - skipping"
        return 0
    fi
    
    # Extract runtime ID from ARN (format: arn:aws:bedrock-agentcore:region:account:runtime/runtime-id)
    local runtime_id=$(echo "$runtime_arn" | sed 's|.*runtime/||')
    
    echo "🗑️  Deleting $runtime_name runtime..."
    echo "   ARN: $runtime_arn"
    echo "   ID: $runtime_id"
    
    # Check if runtime exists first
    if ! aws bedrock-agentcore-control get-agent-runtime \
        --agent-runtime-id "$runtime_id" \
        --region "$REGION" >/dev/null 2>&1; then
        echo "   ℹ️  $runtime_name runtime not found or already deleted"
        return 0
    fi
    
    # Delete the runtime
    if aws bedrock-agentcore-control delete-agent-runtime \
        --agent-runtime-id "$runtime_id" \
        --region "$REGION" 2>/dev/null; then
        echo "   ✅ $runtime_name runtime deletion initiated"
        
        # Wait for deletion to complete
        echo "   ⏳ Waiting for $runtime_name runtime deletion to complete..."
        local max_attempts=30
        local attempt=1
        
        while [ $attempt -le $max_attempts ]; do
            if ! aws bedrock-agentcore-control get-agent-runtime \
                --agent-runtime-id "$runtime_id" \
                --region "$REGION" >/dev/null 2>&1; then
                echo "   ✅ $runtime_name runtime deleted successfully"
                return 0
            fi
            
            echo "   ⏳ Attempt $attempt/$max_attempts - $runtime_name runtime still exists..."
            sleep 10
            ((attempt++))
        done
        
        echo "   ⚠️  $runtime_name runtime deletion timeout - may still be in progress"
        return 1
    else
        echo "   ❌ Failed to delete $runtime_name runtime"
        echo "   💡 This might be normal if the runtime was already deleted"
        return 1
    fi
}

# Get runtime ARNs from dynamic configuration
echo "📖 Reading runtime ARNs from dynamic configuration..."
DYNAMIC_CONFIG="${CONFIG_DIR}/dynamic-config.yaml"

if [ -f "$DYNAMIC_CONFIG" ]; then
    if command -v yq >/dev/null 2>&1; then
        DIY_RUNTIME_ARN=$(yq eval '.runtime.diy_agent.arn' "$DYNAMIC_CONFIG")
        SDK_RUNTIME_ARN=$(yq eval '.runtime.sdk_agent.arn' "$DYNAMIC_CONFIG")
    else
        # Fallback parsing
        DIY_RUNTIME_ARN=$(grep -A 10 "diy_agent:" "$DYNAMIC_CONFIG" | grep "arn:" | head -1 | sed 's/.*arn: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/')
        SDK_RUNTIME_ARN=$(grep -A 10 "sdk_agent:" "$DYNAMIC_CONFIG" | grep "arn:" | head -1 | sed 's/.*arn: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/')
    fi
    
    # Clean up empty values
    [ "$DIY_RUNTIME_ARN" = "null" ] && DIY_RUNTIME_ARN=""
    [ "$SDK_RUNTIME_ARN" = "null" ] && SDK_RUNTIME_ARN=""
    
    echo "   DIY Runtime ARN: ${DIY_RUNTIME_ARN:-'Not configured'}"
    echo "   SDK Runtime ARN: ${SDK_RUNTIME_ARN:-'Not configured'}"
else
    echo "   ⚠️  Dynamic configuration file not found: $DYNAMIC_CONFIG"
    DIY_RUNTIME_ARN=""
    SDK_RUNTIME_ARN=""
fi

echo ""

# List all existing runtimes for reference
echo "📋 Listing all existing runtimes in account..."
if aws bedrock-agentcore-control list-agent-runtimes --region "$REGION" >/dev/null 2>&1; then
    runtime_list=$(aws bedrock-agentcore-control list-agent-runtimes --region "$REGION" --query 'agentRuntimes[*].{Name:agentRuntimeName,ID:agentRuntimeId,Status:status}' --output table 2>/dev/null)
    if [ -n "$runtime_list" ] && echo "$runtime_list" | grep -q "agentcoreDIYTest\|bac_runtime"; then
        echo "$runtime_list"
    else
        echo "   ℹ️  No runtimes found in account"
    fi
else
    echo "   ⚠️  Unable to list runtimes (may be a permissions issue)"
fi

echo ""

# Delete runtimes
echo "🗑️  Starting runtime deletion process..."
echo ""

# Delete DIY runtime
if [ -n "$DIY_RUNTIME_ARN" ]; then
    delete_runtime "$DIY_RUNTIME_ARN" "DIY"
else
    echo "⚠️  No DIY runtime found to delete"
fi

echo ""

# Delete SDK runtime
if [ -n "$SDK_RUNTIME_ARN" ]; then
    delete_runtime "$SDK_RUNTIME_ARN" "SDK"
else
    echo "⚠️  No SDK runtime found to delete"
fi

echo ""

# Update dynamic configuration to clear runtime ARNs
echo "📝 Updating dynamic configuration to clear runtime ARNs..."
if command -v yq >/dev/null 2>&1; then
    yq eval '.runtime.diy_agent.arn = ""' -i "$DYNAMIC_CONFIG"
    yq eval '.runtime.diy_agent.endpoint_arn = ""' -i "$DYNAMIC_CONFIG"
    yq eval '.runtime.sdk_agent.arn = ""' -i "$DYNAMIC_CONFIG"
    yq eval '.runtime.sdk_agent.endpoint_arn = ""' -i "$DYNAMIC_CONFIG"
    echo "   ✅ Dynamic configuration updated - runtime ARNs cleared"
else
    echo "   ⚠️  yq not found - please manually clear runtime ARNs from:"
    echo "      $DYNAMIC_CONFIG"
fi

echo ""

# Optional: Clean up ECR repositories
echo "🧹 Optional: Clean up ECR repositories..."
echo "   This will delete Docker images but keep the repositories"

ECR_REPOS=("bac-runtime-repo-diy" "bac-runtime-repo-sdk")

for repo in "${ECR_REPOS[@]}"; do
    echo "   Checking ECR repository: $repo"
    
    # List images in repository
    if aws ecr describe-images --repository-name "$repo" --region "$REGION" >/dev/null 2>&1; then
        echo "   📦 Found ECR repository: $repo"
        
        # Get image digests
        image_digests=$(aws ecr list-images --repository-name "$repo" --region "$REGION" --query 'imageIds[*].imageDigest' --output text 2>/dev/null)
        
        if [ -n "$image_digests" ] && [ "$image_digests" != "None" ]; then
            echo "   🗑️  Deleting images from $repo..."
            for digest in $image_digests; do
                aws ecr batch-delete-image \
                    --repository-name "$repo" \
                    --image-ids imageDigest="$digest" \
                    --region "$REGION" >/dev/null 2>&1
            done
            echo "   ✅ Images deleted from $repo"
        else
            echo "   ℹ️  No images found in $repo"
        fi
    else
        echo "   ℹ️  ECR repository $repo not found or not accessible"
    fi
done

echo ""
echo "✅ Runtime cleanup completed!"
echo ""
echo "📋 Summary:"
echo "   • Deleted all AgentCore runtimes"
echo "   • Cleared runtime ARNs from dynamic configuration"
echo "   • Cleaned up ECR repository images"
echo ""
echo "💡 Next steps:"
echo "   • Run 97-delete-all-gateways-targets.sh to delete gateways and targets"
echo "   • Run 98-delete-mcp-tool-deployment.sh to delete MCP Lambda"
echo "   • Run 99-cleanup-everything.sh for complete cleanup"
