#!/bin/bash

# Script to set API keys in AWS Systems Manager Parameter Store
# Usage: ./scripts/set-api-keys.sh

REGION="us-east-1"

echo "🔑 Setting API keys in AWS Systems Manager Parameter Store..."
echo ""

# SERP API Key (Product Search)
read -p "Enter SERP API Key (or press Enter to skip): " SERP_KEY
if [ ! -z "$SERP_KEY" ]; then
  aws ssm put-parameter \
    --name "/concierge-agent/shopping/serp-api-key" \
    --value "$SERP_KEY" \
    --type "SecureString" \
    --overwrite \
    --region $REGION
  echo "✅ SERP API key set"
fi

echo ""
echo "🎉 API keys configuration complete!"
echo ""
echo "Note: After setting keys, you need to redeploy the MCP servers:"
echo "  cd infrastructure/mcp-servers && cdk deploy ShoppingStack"
