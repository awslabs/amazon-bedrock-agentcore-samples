#!/bin/bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# Get Cognito JWT token for OpenCode Gateway auth.
#
# Required environment variables:
#   COGNITO_USER       — Cognito username (email)
#   COGNITO_PASSWORD   — Cognito password
#   COGNITO_CLIENT_ID  — Cognito User Pool App Client ID
#   AWS_REGION          — AWS region (default: us-east-1)
#   AWS_PROFILE         — (optional) AWS CLI profile

set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
CLIENT_ID="${COGNITO_CLIENT_ID:?Set COGNITO_CLIENT_ID}"
USER="${COGNITO_USER:?Set COGNITO_USER}"
PASS="${COGNITO_PASSWORD:?Set COGNITO_PASSWORD}"

aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id "$CLIENT_ID" \
  --auth-parameters USERNAME="$USER",PASSWORD="$PASS" \
  --region "$REGION" \
  --query 'AuthenticationResult.IdToken' --output text
