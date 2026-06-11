#!/usr/bin/env bash
set -euo pipefail

# cleanup_cfn.sh — Teardown Amazon Bedrock AgentCore CloudFormation infrastructure
#
# Usage:
#   bash scripts/cleanup_cfn.sh us-east-1 dev
#
# This script:
#   1. Deletes the CloudFormation stack (Gateway, GatewayTarget, Runtime, Cedar policies)
#   2. Removes AgentCore-related SSM parameters
#   3. Does NOT delete prerequisites (Lambda, Cognito, IAM roles, S3 bucket)
#
# To delete prerequisites, run: bash scripts/cleanup.sh --region us-east-1 --env dev

REGION="${1:-us-east-1}"
ENV="${2:-dev}"

STACK_NAME="hr-data-agent-agentcore-${ENV}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Amazon Bedrock AgentCore CloudFormation Cleanup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Region      : ${REGION}"
echo "Environment : ${ENV}"
echo "Stack       : ${STACK_NAME}"
echo ""

# ============================================================================
# Step 1: Check if stack exists
# ============================================================================
echo "→ Checking if stack exists..."
STACK_STATUS=$(aws cloudformation describe-stacks \
  --region "${REGION}" \
  --stack-name "${STACK_NAME}" \
  --query "Stacks[0].StackStatus" \
  --output text 2>/dev/null || echo "NOT_FOUND")

if [[ "${STACK_STATUS}" == "NOT_FOUND" ]]; then
  echo "  ⚠️  Stack ${STACK_NAME} not found — nothing to delete."
  echo ""
else
  echo "  ✓ Stack found (status: ${STACK_STATUS})"
  echo ""

  # ==========================================================================
  # Step 2: Delete CloudFormation stack
  # ==========================================================================
  echo "→ Deleting CloudFormation stack: ${STACK_NAME}..."
  echo "  (This will take ~2-3 minutes)"
  echo ""

  aws cloudformation delete-stack \
    --region "${REGION}" \
    --stack-name "${STACK_NAME}"

  echo "  Waiting for stack deletion to complete..."
  aws cloudformation wait stack-delete-complete \
    --region "${REGION}" \
    --stack-name "${STACK_NAME}" 2>/dev/null || {
      echo ""
      echo "  ⚠️  Stack deletion did not complete cleanly. Check CloudFormation console for errors."
      echo "     Common causes: Runtime still processing requests, Gateway targets not deleted"
      echo ""
      exit 1
    }

  echo "  ✓ Stack deleted: ${STACK_NAME}"
  echo ""
fi

# ============================================================================
# Step 3: Remove AgentCore-related SSM parameters
# ============================================================================
echo "→ Removing AgentCore SSM parameters..."

SSM_PARAMS=(
  "/app/hrdlp/gateway-id"
  "/app/hrdlp/gateway-url"
  "/app/hrdlp/gateway-arn"
  "/app/hrdlp/cedar-policy-engine-arn"
  "/app/hrdlp/runtime-id"
  "/app/hrdlp/runtime-url"
)

for PARAM in "${SSM_PARAMS[@]}"; do
  if aws ssm get-parameter --region "${REGION}" --name "${PARAM}" &>/dev/null; then
    aws ssm delete-parameter --region "${REGION}" --name "${PARAM}"
    echo "  ✓ Deleted ${PARAM}"
  fi
done

echo ""

# ============================================================================
# Done
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ AgentCore infrastructure cleanup complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Remaining resources (NOT deleted by this script):"
echo "  - AWS Lambda functions (hr-data-provider-lambda, interceptors)"
echo "  - Amazon Cognito User Pool and clients"
echo "  - AWS Identity and Access Management (IAM) roles"
echo "  - Amazon S3 bucket (${REGION}-hr-data-agent-deploy-*)"
echo "  - AWS Systems Manager Parameter Store (/app/hrdlp/lambda-arn, /app/hrdlp/cognito-*, etc.)"
echo ""
echo "To delete all prerequisites, run:"
echo "  bash scripts/cleanup.sh --region ${REGION} --env ${ENV}"
echo ""
