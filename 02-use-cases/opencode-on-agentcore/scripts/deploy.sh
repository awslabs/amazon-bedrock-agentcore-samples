#!/usr/bin/env bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# deploy.sh — Full deployment: CDK stacks + Cedar policies.
#
# Usage:
#   AWS_PROFILE=my-profile AWS_REGION=us-east-1 ./scripts/deploy.sh
#
# Or set account/region in cdk.json context, or export CDK_DEFAULT_ACCOUNT
# and CDK_DEFAULT_REGION environment variables.
#
# After this script completes, create a Cognito test user and run
# ``scripts/smoke-test.py`` manually to verify the deployment end-to-end
# (see the README for the full post-deploy flow).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== OpenCode on AgentCore — Deployment ==="
echo "Project: $PROJECT_DIR"

# Source .env if present (for AWS_PROFILE, AWS_REGION, etc.)
if [[ -f "$PROJECT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_DIR/.env"
  set +a
fi

cd "$PROJECT_DIR"
source .venv/bin/activate

# Step 1: Deploy all CDK stacks
echo ""
echo "=== CDK Deploy (8 stacks) ==="
cdk deploy --all --require-approval never --concurrency 4 "$@"

# Step 2: Create Cedar policies
echo ""
echo "=== Post-deploy: Cedar policies ==="
python "$PROJECT_DIR/scripts/create-policies.py" \
  --region "${AWS_REGION:?AWS_REGION must be set}"

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Next steps:"
echo "  1. Create a Cognito user for yourself (see README, Deployment steps 6-7)."
echo "  2. Run the smoke test once the user exists:"
echo "       python scripts/smoke-test.py --region \"\$AWS_REGION\" --username <email>"
