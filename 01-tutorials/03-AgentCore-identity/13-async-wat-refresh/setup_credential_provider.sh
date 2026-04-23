#!/bin/bash
# Create the OAuth2 credential provider in AgentCore Identity for outbound 2LO
# Run AFTER: source setup_cognito.sh

set -e

export AWS_PROFILE=${AWS_PROFILE:-account-a}
REGION=${REGION:-us-east-1}

if [ -z "$POOL_ID" ] || [ -z "$OUTBOUND_CLIENT_ID" ] || [ -z "$OUTBOUND_CLIENT_SECRET" ]; then
  echo "ERROR: Run 'source setup_cognito.sh' first"
  exit 1
fi

DOMAIN_PREFIX="agentcore-async-$(echo $POOL_ID | tr '[:upper:]' '[:lower:]' | sed 's/_/-/g')"
TOKEN_ENDPOINT="https://${DOMAIN_PREFIX}.auth.${REGION}.amazoncognito.com/oauth2/token"
AUTH_ENDPOINT="https://${DOMAIN_PREFIX}.auth.${REGION}.amazoncognito.com/oauth2/authorize"

echo "=== Creating OAuth2 Credential Provider for 2LO ==="
echo "Token Endpoint: $TOKEN_ENDPOINT"
aws bedrock-agentcore-control create-oauth2-credential-provider \
  --name "cognito-m2m-provider" \
  --credential-provider-vendor "CustomOauth2" \
  --oauth2-provider-config-input "{
    \"customOauth2ProviderConfig\": {
      \"oauthDiscovery\": {
        \"authorizationServerMetadata\": {
          \"issuer\": \"https://cognito-idp.${REGION}.amazonaws.com/${POOL_ID}\",
          \"authorizationEndpoint\": \"${AUTH_ENDPOINT}\",
          \"tokenEndpoint\": \"${TOKEN_ENDPOINT}\"
        }
      },
      \"clientId\": \"${OUTBOUND_CLIENT_ID}\",
      \"clientSecret\": \"${OUTBOUND_CLIENT_SECRET}\"
    }
  }" \
  --region $REGION \
  --output json

echo ""
echo "Credential provider 'cognito-m2m-provider' created."
echo "Now run: bash deploy.sh"
