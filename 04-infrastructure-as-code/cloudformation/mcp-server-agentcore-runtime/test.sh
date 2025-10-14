#!/bin/bash
# Streamlined testing script for MCP Server

set -e

STACK_NAME="${1:-mcp-server-demo}"
REGION="${2:-us-west-2}"

echo "=========================================="
echo "MCP Server Testing Script"
echo "=========================================="
echo "Stack Name: $STACK_NAME"
echo "Region: $REGION"
echo ""

# Get stack outputs
echo "📋 Retrieving stack configuration..."
CLIENT_ID=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs[?OutputKey==`CognitoUserPoolClientId`].OutputValue' \
  --output text \
  --region "$REGION")

AGENT_ARN=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs[?OutputKey==`MCPServerRuntimeArn`].OutputValue' \
  --output text \
  --region "$REGION")

if [ -z "$CLIENT_ID" ] || [ -z "$AGENT_ARN" ]; then
  echo "❌ Error: Could not retrieve stack outputs"
  echo "   Make sure the stack '$STACK_NAME' exists in region '$REGION'"
  exit 1
fi

echo "✓ Configuration retrieved"
echo ""

# Get authentication token
echo "🔐 Getting authentication token..."
TOKEN_OUTPUT=$(python get_token.py "$CLIENT_ID" testuser MyPassword123! "$REGION" 2>&1)

# Extract token from output (it's the line after "Access Token:")
JWT_TOKEN=$(echo "$TOKEN_OUTPUT" | grep -A 1 "Access Token:" | tail -n 1 | tr -d '[:space:]')

if [ -z "$JWT_TOKEN" ]; then
  echo "❌ Error: Could not get authentication token"
  echo "$TOKEN_OUTPUT"
  exit 1
fi

echo "✓ Authentication successful"
echo ""

# Test MCP server
echo "🧪 Testing MCP server..."
echo ""
python test_mcp_server.py "$AGENT_ARN" "$JWT_TOKEN" "$REGION"

echo ""
echo "=========================================="
echo "✅ Testing Complete!"
echo "=========================================="
