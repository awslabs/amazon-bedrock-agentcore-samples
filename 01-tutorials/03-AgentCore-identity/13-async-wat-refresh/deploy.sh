#!/bin/bash
# Deploy the WAT refresh test agent.
# Run AFTER: source setup_cognito.sh && bash setup_credential_provider.sh

set -e

export AWS_PROFILE=${AWS_PROFILE:-account-a}
REGION=${REGION:-us-east-1}

if [ -z "$POOL_ID" ] || [ -z "$INBOUND_CLIENT_ID" ]; then
  echo "ERROR: Run 'source setup_cognito.sh' first"
  exit 1
fi

DISCOVERY_URL="https://cognito-idp.${REGION}.amazonaws.com/${POOL_ID}/.well-known/openid-configuration"

echo "=== Configuring agent ==="
agentcore configure \
  -e main.py \
  -n thread_async_utils \
  -r $REGION \
  -rf requirements.txt \
  -dt direct_code_deploy \
  -rt PYTHON_3_12 \
  -do \
  -dm \
  -ni \
  --idle-timeout 3600 \
  --max-lifetime 28800 \
  -ac "{\"customJWTAuthorizer\":{\"discoveryUrl\":\"${DISCOVERY_URL}\",\"allowedClients\":[\"${INBOUND_CLIENT_ID}\"]}}"

echo ""
echo "=== Deploying ==="
agentcore deploy

echo ""
echo "Set AGENT_ARN from the output above, then run test scripts."
