#!/bin/bash
set -euo pipefail

# ============================================================================
# Event-Driven Claims Agent — One-Command Deploy
# Usage: ./deploy.sh [region]
# Example: ./deploy.sh us-west-2
#
# Deploys EVERYTHING via `agentcore deploy`:
# - Infrastructure (DynamoDB, S3, SNS, Cognito, EventBridge) via CDK infra-construct
# - 7 Lambda functions (6 tools + 1 trigger) via CDK infra-construct
# - AgentCore Runtime (dual-agent, Cognito auth, observability) via agentcore.json
# - AgentCore Gateway (MCP, 6 Lambda targets, Cognito CUSTOM_JWT auth) via agentcore.json
# - AgentCore Memory (SEMANTIC + SUMMARIZATION) via agentcore.json
# - AgentCore Policy Engine (Cedar: AllowAll + BlockExcessiveClaims) via agentcore.json
# - AgentCore Online Evaluation (built-in + custom LLM-as-judge) via agentcore.json
# ============================================================================

REGION="${1:-us-west-2}"
export AWS_REGION="$REGION"
export AWS_DEFAULT_REGION="$REGION"
export CDK_DEFAULT_REGION="$REGION"

# Use Finch or Docker for container builds
export CDK_DOCKER="${CDK_DOCKER:-docker}"

echo "🚀 Deploying Claims Agent to $REGION..."
echo ""

# Step 0: Ensure aws-targets.json has correct region
echo "📋 Step 0: Configuring deployment target..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
cat > agentcore/aws-targets.json <<EOF
[
  {
    "name": "dev",
    "account": "$ACCOUNT_ID",
    "region": "$REGION"
  }
]
EOF
echo "  Target: $ACCOUNT_ID / $REGION"
echo ""

# Step 1: Install CDK dependencies (if needed)
echo "📦 Step 1: Installing CDK dependencies..."
cd agentcore/cdk
if [ ! -d "node_modules" ]; then
  npm install --quiet
fi
cd ../..
echo ""

# Step 2: Install agent Python dependencies (if needed)
echo "🐍 Step 2: Installing agent dependencies..."
cd app/claimsagent
if [ ! -d ".venv" ]; then
  uv venv
fi
uv sync --quiet 2>/dev/null || uv pip install -r requirements.txt --quiet
cd ../..
echo ""

# Step 3: Validate agentcore.json
echo "✅ Step 3: Validating configuration..."
agentcore validate
echo ""

# Step 4: Bootstrap CDK (first-time only)
echo "🏗️  Step 4: Checking CDK bootstrap..."
cdk bootstrap aws://$ACCOUNT_ID/$REGION --quiet 2>/dev/null || true
echo ""

# Step 5: Deploy via AgentCore CLI
echo "🚀 Step 5: Deploying via agentcore deploy..."
agentcore deploy --target dev --yes
echo ""

# Step 6: Seed DynamoDB with sample data
echo "🌱 Step 6: Seeding DynamoDB..."
python3 scripts/seed_dynamodb.py --region "$REGION"
echo ""

echo "✅ Done! Claims Agent deployed to $REGION"
echo ""
echo "📋 Test with:"
echo "   python3 scripts/test_invoke.py --region $REGION"
echo ""
echo "🛡️  Test Cedar policy (should block \$100k+ claims):"
echo "   python3 scripts/test_invoke.py --region $REGION --prompt 'File a claim for POL-12345. Car totaled. \$150000 damage.'"
echo ""
echo "🧪 Local dev:"
echo "   agentcore dev --no-browser"
