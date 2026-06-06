#!/bin/bash
set -euo pipefail

# ============================================================================
# Event-Driven Claims Agent — One-Command Deploy (CDK L2)
# Usage: ./deploy.sh [region]
# Example: ./deploy.sh eu-west-1
#
# Deploys EVERYTHING in a single CDK stack:
# - Infrastructure (DynamoDB, S3, SNS, Cognito, EventBridge)
# - 7 Lambda functions (tools + trigger)
# - AgentCore Runtime (dual-agent, Cognito auth, observability)
# - AgentCore Gateway (MCP, 6 Lambda targets, Cognito M2M)
# - AgentCore Memory (SEMANTIC + SUMMARIZATION)
# - AgentCore Policy Engine (Cedar: AllowAll + BlockExcessiveClaims)
# - AgentCore Online Evaluation (built-in + custom LLM-as-judge)
# ============================================================================

REGION="${1:-eu-west-1}"
export CDK_DEFAULT_REGION="$REGION"
export AWS_DEFAULT_REGION="$REGION"

echo "🚀 Deploying Claims Agent to $REGION..."
echo ""

# Step 0: Clean up leftover log groups (prevent CDK "already exists" errors)
echo "🧹 Step 0: Cleaning up old log groups..."
aws logs describe-log-groups --log-group-name-prefix /aws/lambda/ClaimsAgent --region "$REGION" --query 'logGroups[].logGroupName' --output text 2>/dev/null | tr '\t' '\n' | while read -r lg; do
  [ -n "$lg" ] && aws logs delete-log-group --log-group-name "$lg" --region "$REGION" 2>/dev/null && echo "  Deleted: $lg"
done || true
echo ""

# Step 1: CDK deploy (creates EVERYTHING in one stack)
echo "📦 Step 1: CDK deploy (all resources — infra + AgentCore)..."
cd infra
source .venv/bin/activate
cdk deploy --require-approval never
deactivate
cd ..
echo ""

# Step 2: Seed DynamoDB with sample data
echo "🌱 Step 2: Seeding DynamoDB..."
python3 scripts/seed_dynamodb.py --region "$REGION"
echo ""

echo "✅ Done! Claims Agent deployed to $REGION"
echo ""
echo "📋 Test with:"
echo "   agentcore invoke --prompt 'I need to file a claim. My policy is POL-12345. Fender bender, \$2000 damage.'"
echo ""
echo "🛡️  Test Cedar policy (should block \$100k+ claims):"
echo "   agentcore invoke --prompt 'File a claim for POL-11111. Car totaled. \$150000 damage.'"
