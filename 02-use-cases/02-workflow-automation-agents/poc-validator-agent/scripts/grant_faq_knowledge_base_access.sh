#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Grants the deployed runtime execution role read access to the
# PocValidatorFaqKB knowledge base, and writes the deployed knowledge base
# ID into agentcore.json's runtime envVars as FAQ_KNOWLEDGE_BASE_ID.
#
# Two gaps `agentcore deploy` leaves open for a knowledgeBases[] resource,
# confirmed by inspecting the deployed stack directly (not assumed from the
# Memory/Gateway pattern, which DOES auto-inject an env var and DOES
# auto-grant read access — Knowledge Base does neither as of CLI 0.26.0):
#   1. No `bedrock:Retrieve` grant on the runtime execution role.
#   2. No auto-injected env var pointing the runtime at the knowledge base ID
#      (Memory gets MEMORY_<NAME>_ID, Gateway gets AGENTCORE_GATEWAY_<NAME>_URL;
#      Knowledge Base gets nothing).
# See docs/decisions/0011.
#
# Idempotent — safe to re-run after every `agentcore deploy`.
#
# Usage: ./scripts/grant_faq_knowledge_base_access.sh [region]
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
REGION="${1:-${AWS_REGION:-us-east-1}}"
KB_NAME="PocValidatorFaqKB"

command -v jq >/dev/null 2>&1 || { echo "jq is required." >&2; exit 1; }

KB_ID=$(aws bedrock-agent list-knowledge-bases --region "$REGION" --output json \
  | jq -r --arg name "$KB_NAME" '.knowledgeBaseSummaries[] | select(.name | contains($name)) | .knowledgeBaseId' | head -1)

if [[ -z "$KB_ID" || "$KB_ID" == "None" ]]; then
  echo "Could not find knowledge base '${KB_NAME}' in ${REGION} — is it deployed?" >&2
  exit 1
fi

KB_ARN="arn:aws:bedrock:${REGION}:$(aws sts get-caller-identity --query Account --output text):knowledge-base/${KB_ID}"

ROLE_ARN=$(cd "$PROJECT_DIR" && agentcore status --json 2>/dev/null \
  | jq -r '.deployedState.targets.dev.resources.runtimes.pocvalidator.roleArn // empty')
if [[ -z "$ROLE_ARN" ]]; then
  echo "Could not find the runtime execution role — is the stack deployed?" >&2
  exit 1
fi
ROLE_NAME=$(basename "$ROLE_ARN")

echo "Knowledge base: $KB_ID ($KB_ARN)"
echo "Runtime execution role: $ROLE_NAME"

POLICY_DOC=$(cat <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PocValidatorFaqKnowledgeBaseRetrieve",
      "Effect": "Allow",
      "Action": "bedrock:Retrieve",
      "Resource": "${KB_ARN}"
    }
  ]
}
JSON
)

aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "PocValidatorFaqKnowledgeBaseAccess" \
  --policy-document "$POLICY_DOC"

echo "Granted bedrock:Retrieve on ${KB_ARN} to ${ROLE_NAME}."

CONFIG_FILE="$PROJECT_DIR/agentcore/agentcore.json"
CURRENT_VALUE=$(jq -r '.runtimes[0].envVars[] | select(.name == "FAQ_KNOWLEDGE_BASE_ID") | .value' "$CONFIG_FILE" 2>/dev/null || echo "")

if [[ "$CURRENT_VALUE" == "$KB_ID" ]]; then
  echo "agentcore.json already has the correct FAQ_KNOWLEDGE_BASE_ID ($KB_ID) — nothing to patch."
  echo "PATCHED=false"
else
  TMP_FILE=$(mktemp)
  jq --arg kbid "$KB_ID" '
    (.runtimes[0].envVars |= (
      if any(.[]; .name == "FAQ_KNOWLEDGE_BASE_ID")
      then map(if .name == "FAQ_KNOWLEDGE_BASE_ID" then .value = $kbid else . end)
      else . + [{"name": "FAQ_KNOWLEDGE_BASE_ID", "value": $kbid}]
      end
    ))
  ' "$CONFIG_FILE" > "$TMP_FILE"
  mv "$TMP_FILE" "$CONFIG_FILE"
  echo "Patched agentcore.json: FAQ_KNOWLEDGE_BASE_ID = $KB_ID"
  echo "A redeploy is needed for the running container to pick this up."
  echo "PATCHED=true"
fi
