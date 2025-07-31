#!/bin/bash

export POOL_ID="${1}"

# Get AWS region from environment variable or boto session
if [ -z "$AWS_REGION" ]; then
  # Try to get region from AWS CLI configuration
  REGION=$(aws configure get region 2>/dev/null)
  if [ -z "$REGION" ]; then
    # Default to us-east-1 if no region is configured
    REGION="us-east-1"
    echo "Warning: No region configured. Using default: $REGION"
  fi
else
  REGION="$AWS_REGION"
fi

echo "Using AWS Region: $REGION"
echo "Using User Pool: $POOL_ID"
echo ""

# Create App Client
aws cognito-idp create-user-pool-client \
  --user-pool-id $POOL_ID \
  --client-name "CustomerSupportAuthClient" \
  --no-generate-secret \
  --explicit-auth-flows "ALLOW_USER_PASSWORD_AUTH" "ALLOW_REFRESH_TOKEN_AUTH" \
  --token-validity-units AccessToken=hours,IdToken=hours,RefreshToken=days \
  --access-token-validity 2 \
  --id-token-validity 2 \
  --refresh-token-validity 1 \
  --region "$REGION" \
  > client.json

# Store Client ID
export CLIENT_ID=$(jq -r '.UserPoolClient.ClientId' client.json)

# Create User
aws cognito-idp admin-create-user \
  --user-pool-id $POOL_ID \
  --username "testuser@example.com" \
  --temporary-password "Temp123!" \
  --region "$REGION" \
  --message-action SUPPRESS | jq

# Set Permanent Password
aws cognito-idp admin-set-user-password \
  --user-pool-id $POOL_ID \
  --username "testuser@example.com" \
  --password "MyPassword123@" \
  --region "$REGION" \
  --permanent | jq

# Authenticate User
aws cognito-idp initiate-auth \
  --client-id "$CLIENT_ID" \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME='testuser@example.com',PASSWORD='MyPassword123@' \
  --region "$REGION" \
  > auth.json

echo "Successfully extracted and saved access token to auth.json"