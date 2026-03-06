#!/usr/bin/env bash
# scripts/teardown.sh — destroy all AgentCore demo resources
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CDK_DIR="$REPO_ROOT/cdk"
OUTPUTS_FILE="$REPO_ROOT/cdk-outputs.json"
YAML_FILE="$REPO_ROOT/.bedrock_agentcore.yaml"

echo "============================================================"
echo "  This will DESTROY all deployed AgentCore demo resources."
echo "============================================================"
echo ""
read -rp "Are you sure? (y/N): " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo "==> Destroying all CDK stacks"
(cd "$CDK_DIR" && npm run cdk -- destroy --all --force)

echo ""
echo "==> Cleaning up generated files"
rm -f "$OUTPUTS_FILE" && echo "    Removed cdk-outputs.json"
rm -f "$YAML_FILE"    && echo "    Removed .bedrock_agentcore.yaml"

echo ""
echo "Teardown complete."
