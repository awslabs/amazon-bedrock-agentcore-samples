#!/bin/bash
set -euo pipefail

# ============================================================================
# Receipts IDP Agent — Teardown
# Usage: ./destroy.sh [region]
#
# The stack is CDK-managed (created by `agentcore deploy`), and this CLI version
# has no `agentcore destroy`. Tear down via CloudFormation delete-stack — the most
# reliable path (verified: `cdk destroy` can silently no-op depending on the CDK
# CLI version, whereas delete-stack always acts on the named stack). With
# destroyOnDelete (the sample default) the DynamoDB tables and S3 bucket go too,
# leaving nothing billable behind.
# ============================================================================

REGION="${1:-us-west-2}"
STACK="${RECEIPTS_STACK:-AgentCore-ReceiptsAgent-dev}"
export AWS_REGION="$REGION"
export AWS_DEFAULT_REGION="$REGION"

echo "🧹 Destroying $STACK in $REGION..."

if ! aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" >/dev/null 2>&1; then
  echo "✅ Stack $STACK not present — nothing to destroy."
  exit 0
fi

aws cloudformation delete-stack --stack-name "$STACK" --region "$REGION"
echo "⏳ Waiting for delete to complete..."
aws cloudformation wait stack-delete-complete --stack-name "$STACK" --region "$REGION"
echo "✅ Teardown complete — $STACK removed."
