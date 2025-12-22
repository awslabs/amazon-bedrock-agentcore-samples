#!/bin/bash
# Synchronize gateway targets after MCP deployment
set -e

# Set default region if not set
export AWS_REGION=${AWS_REGION:-us-east-1}
DEPLOYMENT_ID=$(node -p "require('./deployment-config.json').deploymentId")

echo "🔄 Synchronizing gateway targets for deployment: $DEPLOYMENT_ID"

# Get gateway ID dynamically based on deployment ID
GATEWAY_ID=$(aws bedrock-agentcore-control list-gateways \
  --query "items[?contains(name, 'agentstack-${DEPLOYMENT_ID}')].gatewayId | [0]" \
  --output text)

if [ -z "$GATEWAY_ID" ] || [ "$GATEWAY_ID" == "None" ]; then
  echo "❌ No gateway found for deployment: $DEPLOYMENT_ID"
  exit 1
fi

echo "Found gateway: $GATEWAY_ID"

# Get all target IDs
TARGET_IDS=$(aws bedrock-agentcore-control list-gateway-targets \
  --gateway-identifier "$GATEWAY_ID" \
  --query 'items[].targetId' \
  --output text)

echo "Found targets: $TARGET_IDS"

# Sync each target individually (API limit is 1 per call)
for TARGET_ID in $TARGET_IDS; do
  echo "Syncing target: $TARGET_ID"
  aws bedrock-agentcore-control synchronize-gateway-targets \
    --gateway-identifier "$GATEWAY_ID" \
    --target-id-list "[\"$TARGET_ID\"]" \
    --no-cli-pager
done

echo "Synchronization started. Waiting for completion..."

# Wait for all targets to be READY
for i in {1..30}; do
  sleep 10
  
  # Check if all are READY
  NOT_READY=$(aws bedrock-agentcore-control list-gateway-targets \
    --gateway-identifier "$GATEWAY_ID" \
    --query 'items[?status!=`READY`].name' \
    --output text)
  
  if [ -z "$NOT_READY" ]; then
    echo "✅ All targets synchronized!"
    exit 0
  fi
  
  echo "Waiting... (not ready: $NOT_READY)"
done

echo "⚠️ Timeout waiting for synchronization"
exit 1
