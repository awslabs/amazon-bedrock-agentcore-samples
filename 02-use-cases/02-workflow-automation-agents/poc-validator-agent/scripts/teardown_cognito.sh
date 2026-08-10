#!/bin/bash
set -euo pipefail

# Deletes the Cognito pool created by setup_cognito.sh — and only that one.
# If .cognito-state.json is absent or says the pool was pre-existing, this
# refuses to act rather than guessing.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
STATE_FILE="$PROJECT_DIR/.cognito-state.json"

if [ ! -f "$STATE_FILE" ]; then
  echo "No .cognito-state.json — nothing was created by setup_cognito.sh."
  echo "Not touching any existing Cognito pool."
  exit 0
fi

REGION=$(python3 -c "import json;print(json.load(open('$STATE_FILE'))['region'])")
POOL_ID=$(python3 -c "import json;print(json.load(open('$STATE_FILE'))['user_pool_id'])")
DOMAIN=$(python3 -c "import json;print(json.load(open('$STATE_FILE'))['domain_prefix'])")

echo "About to delete Cognito User Pool $POOL_ID in $REGION."
read -r -p "Continue? [y/N] " reply
[[ "$reply" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }

aws cognito-idp delete-user-pool-domain --domain "$DOMAIN" \
  --user-pool-id "$POOL_ID" --region "$REGION" 2>/dev/null || true
aws cognito-idp delete-user-pool --user-pool-id "$POOL_ID" --region "$REGION"
rm -f "$STATE_FILE"

# Restore the placeholder config so nothing account-specific is left staged.
CONFIG="$PROJECT_DIR/agentcore/agentcore.json"
[ -f "$CONFIG.template" ] && mv "$CONFIG.template" "$CONFIG"

echo "Cognito removed and agentcore.json restored to placeholders."
