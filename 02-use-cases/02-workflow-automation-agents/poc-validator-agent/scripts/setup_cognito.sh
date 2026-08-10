#!/bin/bash
set -euo pipefail

# ============================================================================
# Cognito User Pool setup for the POC Validator Gateway.
#
# Creates a User Pool plus an M2M app client for the Gateway's CUSTOM_JWT
# authorizer, then substitutes the PLACEHOLDER_* values in agentcore.json.
# Run this BEFORE ./deploy.sh unless you already have a pool.
#
# Follows the same approach as
# 02-use-cases/02-workflow-automation-agents/event-driven-claims-agent/scripts/setup_cognito.sh
# — Cognito is managed by script rather than CDK so the Gateway's discovery URL
# is known before the stack that references it is created.
#
# Usage: ./scripts/setup_cognito.sh [region]
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
REGION="${1:-${AWS_REGION:-us-west-2}}"
STATE_FILE="$PROJECT_DIR/.cognito-state.json"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region "$REGION")
POOL_NAME="PocValidator-UserPool"
DOMAIN_PREFIX="poc-validator-${ACCOUNT_ID}"
RESOURCE_SERVER_ID="agentcore"
SCOPE_NAME="invoke"
CLIENT_NAME="PocValidator-M2M"

echo "Setting up Cognito for the POC Validator Gateway"
echo "  Region:  $REGION"
echo "  Account: $ACCOUNT_ID"
echo

EXISTING_POOL_ID=$(aws cognito-idp list-user-pools --max-results 60 --region "$REGION" \
  --query "UserPools[?Name=='${POOL_NAME}'].Id | [0]" --output text 2>/dev/null || echo "None")

if [ "$EXISTING_POOL_ID" != "None" ] && [ -n "$EXISTING_POOL_ID" ]; then
  echo "User Pool '$POOL_NAME' already exists ($EXISTING_POOL_ID) — reusing it."
  USER_POOL_ID="$EXISTING_POOL_ID"
else
  echo "Creating User Pool: $POOL_NAME"
  USER_POOL_ID=$(aws cognito-idp create-user-pool \
    --pool-name "$POOL_NAME" --region "$REGION" \
    --query 'UserPool.Id' --output text)

  aws cognito-idp create-user-pool-domain \
    --domain "$DOMAIN_PREFIX" --user-pool-id "$USER_POOL_ID" --region "$REGION" >/dev/null

  aws cognito-idp create-resource-server \
    --user-pool-id "$USER_POOL_ID" \
    --identifier "$RESOURCE_SERVER_ID" \
    --name "AgentCore Gateway" \
    --scopes "ScopeName=${SCOPE_NAME},ScopeDescription=Invoke the gateway" \
    --region "$REGION" >/dev/null
fi

EXISTING_CLIENT_ID=$(aws cognito-idp list-user-pool-clients \
  --user-pool-id "$USER_POOL_ID" --max-results 60 --region "$REGION" \
  --query "UserPoolClients[?ClientName=='${CLIENT_NAME}'].ClientId | [0]" \
  --output text 2>/dev/null || echo "None")

if [ "$EXISTING_CLIENT_ID" != "None" ] && [ -n "$EXISTING_CLIENT_ID" ]; then
  CLIENT_ID="$EXISTING_CLIENT_ID"
  echo "Reusing M2M app client ($CLIENT_ID)"
else
  echo "Creating M2M app client: $CLIENT_NAME"
  CLIENT_ID=$(aws cognito-idp create-user-pool-client \
    --user-pool-id "$USER_POOL_ID" --client-name "$CLIENT_NAME" \
    --generate-secret \
    --allowed-o-auth-flows client_credentials \
    --allowed-o-auth-scopes "${RESOURCE_SERVER_ID}/${SCOPE_NAME}" \
    --allowed-o-auth-flows-user-pool-client \
    --supported-identity-providers COGNITO \
    --region "$REGION" \
    --query 'UserPoolClient.ClientId' --output text)
fi

CLIENT_SECRET=$(aws cognito-idp describe-user-pool-client \
  --user-pool-id "$USER_POOL_ID" --client-id "$CLIENT_ID" --region "$REGION" \
  --query 'UserPoolClient.ClientSecret' --output text)

cat > "$STATE_FILE" <<JSON
{
  "created_by_script": true,
  "region": "$REGION",
  "user_pool_id": "$USER_POOL_ID",
  "client_id": "$CLIENT_ID",
  "domain_prefix": "$DOMAIN_PREFIX"
}
JSON

# Substitute placeholders in agentcore.json. Keep a pristine copy so the
# committed file never contains a real account's identifiers.
CONFIG="$PROJECT_DIR/agentcore/agentcore.json"
[ -f "$CONFIG.template" ] || cp "$CONFIG" "$CONFIG.template"
sed -e "s/PLACEHOLDER_REGION/$REGION/g" \
    -e "s/PLACEHOLDER_USER_POOL_ID/$USER_POOL_ID/g" \
    -e "s/PLACEHOLDER_CLIENT_ID/$CLIENT_ID/g" \
    "$CONFIG.template" > "$CONFIG"

echo
echo "Done."
echo "  User Pool: $USER_POOL_ID"
echo "  Client:    $CLIENT_ID"
echo "  Secret:    (retrieved; register it with: agentcore add credential)"
echo
echo "The client secret is NOT written to disk. Register it with AgentCore Identity:"
echo "  agentcore add credential --name cognito-gateway-m2m \\"
echo "    --client-id $CLIENT_ID --client-secret '<secret>'"
echo
echo "Still to set: PLACEHOLDER_AWS_DOCS_MCP_HOST in agentcore/agentcore.json —"
echo "the endpoint of your hosted AWS Documentation MCP server."
echo
echo "Next: ./deploy.sh dev"
