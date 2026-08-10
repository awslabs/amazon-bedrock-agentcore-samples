#!/usr/bin/env bash
# Tear down everything this sample creates, in dependency order.
set -euo pipefail

TARGET="${1:-dev}"
REGION="${AWS_REGION:-$(python3 -c "import json,sys;print(json.load(open('agentcore/aws-targets.json'))[0]['region'])" 2>/dev/null || echo us-west-2)}"

echo "This removes the AgentCore Runtime, Memory, Gateway, PolicyEngine and"
echo "Evaluators for target '$TARGET' in $REGION, plus the ECR repository."
echo "Cognito is removed separately by scripts/teardown_cognito.sh."
read -r -p "Continue? [y/N] " reply
[[ "$reply" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }

# Deploying an emptied schema triggers CloudFormation stack deletion.
echo "→ Resetting the schema"
agentcore reset --yes 2>/dev/null || agentcore reset || true

echo "→ Deploying the emptied schema (deletes the stack)"
agentcore deploy --target "$TARGET" || true

echo "→ Sweeping any orphaned control-plane resources (dry run)"
python3 scripts/cleanup_agentcore.py --region "$REGION" || true

cat <<'NOTE'

If the sweep listed anything, delete it for real:
    python3 scripts/cleanup_agentcore.py --region <region> --apply

Then check separately, since neither the CLI nor the sweep removes them:
  - ECR repositories        aws ecr describe-repositories
  - CloudWatch log groups   aws logs describe-log-groups --log-group-name-prefix /aws/bedrock-agentcore
  - Cognito                 ./scripts/teardown_cognito.sh
NOTE
