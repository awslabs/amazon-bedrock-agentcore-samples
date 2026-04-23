#!/bin/bash
# Setup Cognito User Pool for inbound JWT auth
# and a Resource Server + App Client for outbound 2LO (M2M)
#
# Usage: source setup_cognito.sh
# This exports env vars needed by deploy.sh and test scripts.

set -e

export AWS_PROFILE=${AWS_PROFILE:-account-a}
REGION=${REGION:-us-east-1}
USERNAME=${USERNAME:-testuser}
PASSWORD=${PASSWORD:-TestPass123!}
POOL_NAME="AgentCoreAsyncDemo"
RESOURCE_SERVER_ID="https://agent-api.example.com"

echo "=== Creating Cognito User Pool ==="
export POOL_ID=$(aws cognito-idp create-user-pool \
  --pool-name "$POOL_NAME" \
  --policies '{"PasswordPolicy":{"MinimumLength":8}}' \
  --region $REGION | jq -r '.UserPool.Id')
echo "Pool ID: $POOL_ID"

echo "=== Creating Resource Server (for 2LO scopes) ==="
aws cognito-idp create-resource-server \
  --user-pool-id $POOL_ID \
  --identifier "$RESOURCE_SERVER_ID" \
  --name "Agent API" \
  --scopes '[{"ScopeName":"invoke","ScopeDescription":"Invoke agent API"}]' \
  --region $REGION > /dev/null

echo "=== Creating Inbound App Client (for JWT auth - user login) ==="
export INBOUND_CLIENT_ID=$(aws cognito-idp create-user-pool-client \
  --user-pool-id $POOL_ID \
  --client-name "InboundClient" \
  --no-generate-secret \
  --explicit-auth-flows "ALLOW_USER_PASSWORD_AUTH" "ALLOW_REFRESH_TOKEN_AUTH" \
  --access-token-validity 5 \
  --token-validity-units '{"AccessToken":"minutes"}' \
  --region $REGION | jq -r '.UserPoolClient.ClientId')
echo "Inbound Client ID: $INBOUND_CLIENT_ID (access token TTL: 5 minutes)"

echo "=== Creating Outbound App Client (for 2LO - M2M) ==="
OUTBOUND_RESPONSE=$(aws cognito-idp create-user-pool-client \
  --user-pool-id $POOL_ID \
  --client-name "OutboundM2MClient" \
  --generate-secret \
  --allowed-o-auth-flows "client_credentials" \
  --allowed-o-auth-scopes "${RESOURCE_SERVER_ID}/invoke" \
  --allowed-o-auth-flows-user-pool-client \
  --region $REGION)

export OUTBOUND_CLIENT_ID=$(echo $OUTBOUND_RESPONSE | jq -r '.UserPoolClient.ClientId')
export OUTBOUND_CLIENT_SECRET=$(echo $OUTBOUND_RESPONSE | jq -r '.UserPoolClient.ClientSecret')
echo "Outbound Client ID: $OUTBOUND_CLIENT_ID"
echo "Outbound Client Secret: $OUTBOUND_CLIENT_SECRET"

echo "=== Creating Cognito Domain (required for token endpoint) ==="
DOMAIN_PREFIX="agentcore-async-$(echo $POOL_ID | tr '[:upper:]' '[:lower:]' | sed 's/_/-/g')"
aws cognito-idp create-user-pool-domain \
  --user-pool-id $POOL_ID \
  --domain "$DOMAIN_PREFIX" \
  --region $REGION > /dev/null
echo "Domain: https://${DOMAIN_PREFIX}.auth.${REGION}.amazoncognito.com"

echo "=== Creating Test User ==="
aws cognito-idp admin-create-user \
  --user-pool-id $POOL_ID \
  --username $USERNAME \
  --region $REGION \
  --message-action SUPPRESS > /dev/null

aws cognito-idp admin-set-user-password \
  --user-pool-id $POOL_ID \
  --username $USERNAME \
  --password $PASSWORD \
  --region $REGION \
  --permanent > /dev/null

export USERNAME PASSWORD

echo ""
echo "========================================="
echo "SETUP COMPLETE"
echo "========================================="
echo "Pool ID:              $POOL_ID"
echo "Discovery URL:        https://cognito-idp.${REGION}.amazonaws.com/${POOL_ID}/.well-known/openid-configuration"
echo "Inbound Client ID:    $INBOUND_CLIENT_ID"
echo "Outbound Client ID:   $OUTBOUND_CLIENT_ID"
echo "Outbound Secret:      $OUTBOUND_CLIENT_SECRET"
echo ""
echo "Run 'source setup_credential_provider.sh' next."
echo "========================================="
