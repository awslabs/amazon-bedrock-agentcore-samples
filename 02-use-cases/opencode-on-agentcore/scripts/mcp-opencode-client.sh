#!/usr/bin/env bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# MCP client wrapper for OpenCode Gateway — acquires Cognito JWT and proxies.
#
# Required env vars:
#   COGNITO_CLIENT_ID   — Cognito User Pool Client ID
#   COGNITO_USER        — Cognito username (email)
#   COGNITO_PASSWORD    — Cognito password
#   AWS_REGION           — AWS region
#   AWS_PROFILE          — AWS CLI profile (optional)
#   OPENCODE_GATEWAY_URL — Gateway MCP endpoint URL

set -euo pipefail

# Use system aws CLI (avoid venv shebang issues with spaces in paths)
AWS_CMD="aws"
if [ -x /opt/homebrew/bin/aws ]; then
  AWS_CMD=/opt/homebrew/bin/aws
elif [ -x /usr/local/bin/aws ]; then
  AWS_CMD=/usr/local/bin/aws
fi

AUTH_PARAMS=$(jq -nc --arg u "$COGNITO_USER" --arg p "$COGNITO_PASSWORD" '{USERNAME: $u, PASSWORD: $p}')

TOKEN=$("$AWS_CMD" cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id "${COGNITO_CLIENT_ID}" \
  --auth-parameters "$AUTH_PARAMS" \
  --region "${AWS_REGION}" \
  ${AWS_PROFILE:+--profile "${AWS_PROFILE}"} \
  --query 'AuthenticationResult.IdToken' --output text)

# Append a unique session-bust parameter to force a new microVM session
# on each MCP server restart (avoids stale microVM after deploys).
GATEWAY_URL="${OPENCODE_GATEWAY_URL}?_session=$(date +%s)"

exec npx -y mcp-remote@latest \
  "${GATEWAY_URL}" \
  --header "Authorization: Bearer ${TOKEN}"
