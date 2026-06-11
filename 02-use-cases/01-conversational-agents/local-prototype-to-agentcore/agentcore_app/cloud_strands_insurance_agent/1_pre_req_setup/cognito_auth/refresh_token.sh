#!/bin/bash
# cognito/refresh_token.sh

# Check if config file exists
if [ ! -f "cognito_config.json" ]; then
    echo "Error: cognito_config.json not found. Run setup_cognito.sh first."
    exit 1
fi

# Read config from JSON file
CLIENT_ID=$(jq -r '.client_id' cognito_config.json)
USERNAME=$(jq -r '.username' cognito_config.json)
PASSWORD=$(jq -r '.password' cognito_config.json)
REGION=$(jq -r '.region' cognito_config.json)

# Get new token
NEW_TOKEN=$(aws cognito-idp initiate-auth \
  --client-id "$CLIENT_ID" \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME="$USERNAME",PASSWORD="$PASSWORD" \
  --region "$REGION" | jq -r '.AuthenticationResult.AccessToken')

# Update config file with new token
jq --arg token "$NEW_TOKEN" '.bearer_token = $token' cognito_config.json > temp.json && mv temp.json cognito_config.json

echo "New Bearer Token: $NEW_TOKEN"
echo "Config updated in cognito_config.json"
