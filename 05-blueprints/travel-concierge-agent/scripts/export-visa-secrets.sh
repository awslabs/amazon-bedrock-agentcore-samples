#!/bin/bash
# Store Visa secrets in AWS Secrets Manager
# Usage: ./scripts/export-visa-secrets.sh

set -e

REGION="us-east-1"

echo "🔐 Storing Visa secrets in AWS Secrets Manager..."
echo ""

# Prompt for Visa API credentials
read -p "Enter Visa API Key: " VISA_API_KEY
read -p "Enter Visa Shared Secret: " VISA_SHARED_SECRET
read -p "Enter Visa Encryption API Key: " VISA_ENCRYPTION_API_KEY
read -p "Enter Visa Encryption Shared Secret: " VISA_ENCRYPTION_SHARED_SECRET
read -p "Enter Visa Key ID: " VISA_KEY_ID

# Function to create or update secret
store_secret() {
  local secret_name=$1
  local secret_value=$2
  
  if aws secretsmanager describe-secret --secret-id "$secret_name" --region $REGION &>/dev/null; then
    aws secretsmanager put-secret-value \
      --secret-id "$secret_name" \
      --secret-string "$secret_value" \
      --region $REGION &>/dev/null
    echo "✅ Updated: $secret_name"
  else
    aws secretsmanager create-secret \
      --name "$secret_name" \
      --secret-string "$secret_value" \
      --region $REGION &>/dev/null
    echo "✅ Created: $secret_name"
  fi
}

# Store API credentials
store_secret "visa/api-key" "$VISA_API_KEY"
store_secret "visa/shared-secret" "$VISA_SHARED_SECRET"
store_secret "visa/encryption-api-key" "$VISA_ENCRYPTION_API_KEY"
store_secret "visa/encryption-shared-secret" "$VISA_ENCRYPTION_SHARED_SECRET"
store_secret "visa/vic_key_id" "$VISA_KEY_ID"

# Store PEM certificates if they exist
if [ -f "./infrastructure/certs/server_mle_cert.pem" ]; then
  VISA_SERVER_MLE_CERT=$(cat ./infrastructure/certs/server_mle_cert.pem)
  store_secret "visa/server-mle-cert" "$VISA_SERVER_MLE_CERT"
else
  echo "⚠️  Warning: ./infrastructure/certs/server_mle_cert.pem not found, skipping"
fi

if [ -f "./infrastructure/certs/mle_private_cert.pem" ]; then
  VISA_MLE_PRIVATE_CERT=$(cat ./infrastructure/certs/mle_private_cert.pem)
  store_secret "visa/mle-private-cert" "$VISA_MLE_PRIVATE_CERT"
else
  echo "⚠️  Warning: ./infrastructure/certs/mle_private_cert.pem not found, skipping"
fi

echo ""
echo "🎉 Visa secrets stored in AWS Secrets Manager!"
echo ""
echo "Next steps:"
echo "1. Deploy cart manager: cd infrastructure/mcp-servers && cdk deploy CartStack"
