#!/bin/bash

# Script to set API keys in AWS Systems Manager Parameter Store
# Usage: ./scripts/set-api-keys.sh

REGION="us-east-1"

echo "🔑 Setting API keys in AWS Systems Manager Parameter Store..."
echo ""

# OpenWeather API Key
read -p "Enter OpenWeather API Key (or press Enter to skip): " OPENWEATHER_KEY
if [ ! -z "$OPENWEATHER_KEY" ]; then
  aws ssm put-parameter \
    --name "/concierge-agent/travel/openweather-api-key" \
    --value "$OPENWEATHER_KEY" \
    --type "SecureString" \
    --overwrite \
    --region $REGION
  echo "✅ OpenWeather API key set"
fi

# SERP API Key (Internet Search)
read -p "Enter SERP API Key (or press Enter to skip): " SERP_KEY
if [ ! -z "$SERP_KEY" ]; then
  aws ssm put-parameter \
    --name "/concierge-agent/travel/serp-api-key" \
    --value "$SERP_KEY" \
    --type "SecureString" \
    --overwrite \
    --region $REGION
  echo "✅ SERP API key set"
fi

# Google Maps API Key
read -p "Enter Google Maps API Key (or press Enter to skip): " GOOGLE_KEY
if [ ! -z "$GOOGLE_KEY" ]; then
  aws ssm put-parameter \
    --name "/concierge-agent/travel/google-maps-key" \
    --value "$GOOGLE_KEY" \
    --type "SecureString" \
    --overwrite \
    --region $REGION
  echo "✅ Google Maps API key set"
fi

echo ""
echo "🎉 API keys configuration complete!"
echo ""
echo "Note: After setting keys, you need to redeploy the MCP servers:"
echo "  cd infrastructure/mcp-servers && cdk deploy TravelStack"
