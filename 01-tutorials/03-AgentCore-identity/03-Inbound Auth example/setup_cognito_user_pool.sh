#!/bin/bash

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
echo ""

# Create User Pool
aws cognito-idp create-user-pool \
  --pool-name "DemoUserPool" \
  --policies '{"PasswordPolicy":{"MinimumLength":8}}' \
  --region "$REGION" \
  > pool.json

# Store Pool ID
export POOL_ID=$(jq -r '.UserPool.Id' pool.json)

# Create App Client
aws cognito-idp create-user-pool-client \
  --user-pool-id $POOL_ID \
  --client-name "DemoClient" \
  --no-generate-secret \
  --explicit-auth-flows "ALLOW_USER_PASSWORD_AUTH" "ALLOW_REFRESH_TOKEN_AUTH" \
  --region "$REGION" \
  > client.json

# Store Client ID
export CLIENT_ID=$(jq -r '.UserPoolClient.ClientId' client.json)

# Create User
aws cognito-idp admin-create-user \
  --user-pool-id $POOL_ID \
  --username "testuser" \
  --temporary-password "Temp123!" \
  --region "$REGION" \
  --message-action SUPPRESS | jq

# Set Permanent Password
aws cognito-idp admin-set-user-password \
  --user-pool-id $POOL_ID \
  --username "testuser" \
  --password "MyPassword123!" \
  --region "$REGION" \
  --permanent | jq

# Authenticate User
aws cognito-idp initiate-auth \
  --client-id "$CLIENT_ID" \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME='testuser',PASSWORD='MyPassword123!' \
  --region "$REGION" \
  > auth.json

# Display auth response
jq . auth.json

# Store Access Token
ACCESS_TOKEN=$(jq -r '.AuthenticationResult.AccessToken' auth.json)

# Export variables for use in Jupyter notebook
COGNITO_DISCOVERY_URL="https://cognito-idp.$REGION.amazonaws.com/$POOL_ID/.well-known/openid-configuration"
COGNITO_CLIENT_ID="$CLIENT_ID"
COGNITO_ACCESS_TOKEN="$ACCESS_TOKEN"


echo ""
echo "========================================="
echo "Cognito Setup Complete!"
echo "========================================="
echo "Cognito Discovery URL: $COGNITO_DISCOVERY_URL"
echo "App Client ID: $COGNITO_CLIENT_ID"
echo "Access Token: ${COGNITO_ACCESS_TOKEN}"
echo "========================================="
echo ""


# Clean up credential files for security
echo "Cleaning up credential files..."
rm -f pool.json client.json auth.json
echo "Credential files removed for security."
echo "========================================="
