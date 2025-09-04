#!/bin/bash
set -e

echo "=== Setting up AgentCore Gateway Observability ==="

# Get the script directory and project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

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
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Step 1: Note about CloudWatch Transaction Search
echo "Step 1: CloudWatch Transaction Search..."
echo "NOTE: CloudWatch Transaction Search needs to be enabled in the CloudWatch console."
echo "Please go to the CloudWatch console > Application Signals > Transaction search"
echo "and click 'Enable Transaction Search' if it's not already enabled."
echo "This is a one-time setup required for observability."
echo ""
echo "Proceeding with log group setup..."

# Step 2: Create log groups for resources
echo "Step 2: Creating log groups for resources..."

# Create log group for gateway
GATEWAY_LOG_GROUP="/aws/bedrock-agentcore/gateways/$GATEWAY_IDENTIFIER"
aws logs create-log-group --log-group-name "$GATEWAY_LOG_GROUP" --region $AWS_REGION || echo "Log group already exists or couldn't be created"

# Create log group for targets
if [ ! -z "$TARGET_ID" ]; then
    TARGET_LOG_GROUP="/aws/bedrock-agentcore/targets/$TARGET_ID"
    aws logs create-log-group --log-group-name "$TARGET_LOG_GROUP" --region $AWS_REGION || echo "Log group already exists or couldn't be created"
fi

if [ ! -z "$PGSTAT_TARGET_ID" ]; then
    PGSTAT_TARGET_LOG_GROUP="/aws/bedrock-agentcore/targets/$PGSTAT_TARGET_ID"
    aws logs create-log-group --log-group-name "$PGSTAT_TARGET_LOG_GROUP" --region $AWS_REGION || echo "Log group already exists or couldn't be created"
fi

# Step 3: Note about delivery sources and destinations
echo "Step 3: Note about delivery sources and destinations..."
echo "NOTE: The PutDeliverySource operation is only valid for AgentCore memory resources, not for gateways or targets."
echo "The error message 'This resource is not allowed for this LogType. Valid options are [memory]' indicates this limitation."
echo "\nHowever, AgentCore Gateway has built-in observability capabilities that don't require delivery sources."
echo "Gateway logs are automatically sent to CloudWatch and traces to X-Ray when Transaction Search is enabled."
echo "\nSkipping delivery source/destination configuration since it's not applicable for gateways and targets."

echo "\nNOTE: AgentCore Gateway has basic built-in observability capabilities."
echo "To view basic traces and logs, you need to enable CloudWatch Transaction Search in the CloudWatch console."
echo "Go to CloudWatch > Application Signals > Transaction search and click 'Enable Transaction Search'."
echo "\nFor detailed end-to-end tracing with Lambda targets, you would need to instrument your Lambda functions with ADOT SDK."

echo "=== AgentCore Gateway Observability Setup Complete ==="
echo "To view basic observability data, open the CloudWatch console and navigate to:"
echo "  - Application Signals > Transaction search"
echo "  - Log groups > /aws/bedrock-agentcore/gateways/$GATEWAY_IDENTIFIER"
echo "  - Log groups > /aws/bedrock-agentcore/targets/<target-id>"
echo "  - X-Ray > Traces"
echo ""
echo "Remember: For detailed end-to-end tracing, Lambda functions need ADOT instrumentation."