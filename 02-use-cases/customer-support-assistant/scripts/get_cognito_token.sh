#!/bin/bash

set -e

# Cognito Configuration
COGNITO_TOKEN_URL="https://us-east-1d1ae1ac0.auth.us-east-1.amazoncognito.com/oauth2/token"
CLIENT_ID="7kqi2l0n47mnfmhfapsf29ch4h"
CLIENT_SECRET="8hqplshopiiqjohfl37a6g7mgs1asjro5ab1j9ovjubpikjp58k"
SCOPE="default-m2m-resource-server-d1ae1ac0/read"

echo "Requesting access token from Cognito..."
echo "Token URL: $COGNITO_TOKEN_URL"
echo "Client ID: $CLIENT_ID"
echo "Scope: $SCOPE"
echo ""

# Get access token
response=$(curl -s -X POST "$COGNITO_TOKEN_URL" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -d "client_id=$CLIENT_ID" \
  -d "client_secret=$CLIENT_SECRET" \
  -d "scope=$SCOPE")

# Check if response contains access_token
if echo "$response" | grep -q "access_token"; then
    echo "Successfully obtained access token"
    echo ""
    echo "Full response:"
    echo "$response" | python3 -m json.tool
    echo ""

    # Extract and display just the token
    access_token=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")
    echo "Access Token:"
    echo "$access_token"
    echo ""

    # Export as environment variable
    export ACCESS_TOKEN="$access_token"
    echo "Token exported as ACCESS_TOKEN environment variable"

    # Save to file for later use
    echo "$access_token" > .cognito_access_token
    echo "Token saved to .cognito_access_token file"
else
    echo "Failed to obtain access token"
    echo "Response:"
    echo "$response"
    exit 1
fi
