#!/bin/bash
set -e

echo "=== Cleaning up AgentCore Gateway Observability ==="

# Get the script directory and project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

# Load configurations
if [ -f "$PROJECT_DIR/config/gateway_config.env" ]; then
    source "$PROJECT_DIR/config/gateway_config.env"
fi

if [ -f "$PROJECT_DIR/config/target_config.env" ]; then
    source "$PROJECT_DIR/config/target_config.env"
fi

if [ -f "$PROJECT_DIR/config/pgstat_target_config.env" ]; then
    source "$PROJECT_DIR/config/pgstat_target_config.env"
fi

# Set default region if not set
AWS_REGION=${AWS_REGION:-"us-west-2"}

# Function to clean up log groups for a resource
cleanup_log_groups() {
    local resource_id=$1
    local resource_type=$2
    
    echo "Cleaning up log groups for $resource_type: $resource_id"
    
    # Delete resource-specific log group
    if [ "$resource_type" = "gateway" ]; then
        RESOURCE_LOG_GROUP="/aws/bedrock-agentcore/gateways/$resource_id"
    elif [ "$resource_type" = "target" ]; then
        RESOURCE_LOG_GROUP="/aws/bedrock-agentcore/targets/$resource_id"
    fi
    
    echo "Deleting log group: $RESOURCE_LOG_GROUP"
    aws logs delete-log-group --log-group-name "$RESOURCE_LOG_GROUP" --region $AWS_REGION 2>/dev/null || echo "Log group $RESOURCE_LOG_GROUP doesn't exist or couldn't be deleted"
    
    echo "Log groups cleanup completed for $resource_type: $resource_id"
}

# Clean up log groups for gateway
if [ ! -z "$GATEWAY_IDENTIFIER" ]; then
    cleanup_log_groups "$GATEWAY_IDENTIFIER" "gateway"
fi

# Clean up log groups for targets
if [ ! -z "$TARGET_ID" ]; then
    cleanup_log_groups "$TARGET_ID" "target"
fi

if [ ! -z "$PGSTAT_TARGET_ID" ]; then
    cleanup_log_groups "$PGSTAT_TARGET_ID" "target"
fi

echo "\nNOTE: The PutDeliverySource operation is only valid for AgentCore memory resources, not for gateways or targets."
echo "Therefore, no delivery sources or destinations were created or need to be cleaned up."
echo "\nAgentCore Gateway has basic built-in observability capabilities that don't require delivery sources."
echo "For detailed end-to-end tracing with Lambda targets, Lambda functions need ADOT instrumentation."

echo "=== AgentCore Gateway Observability Cleanup Complete ==="