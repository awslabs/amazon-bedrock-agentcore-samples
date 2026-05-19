#!/usr/bin/env bash
set -euo pipefail

echo "Fetching OpenAI credentials from Secrets Manager..."

SECRET=$(aws secretsmanager get-secret-value \
    --secret-id "openai/codex" \
    --region "${AWS_REGION:-us-west-2}" \
    --query SecretString \
    --output text)

export CODEX_API_KEY=$(echo "$SECRET" | jq -r .api_key)

echo "Credentials loaded. Starting server..."
exec node /app/server.js
