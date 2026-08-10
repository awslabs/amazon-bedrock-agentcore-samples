#!/usr/bin/env bash
# Deploy the POC Validator to your AWS account via the AgentCore CLI.
set -euo pipefail

command -v agentcore >/dev/null 2>&1 || {
  echo "AgentCore CLI not found. Install it with: npm install -g @aws/agentcore" >&2
  exit 1
}

if [[ ! -f agentcore/aws-targets.json ]]; then
  echo "agentcore/aws-targets.json missing." >&2
  echo "Copy the template and fill in your account and region:" >&2
  echo "  cp agentcore/aws-targets.json.template agentcore/aws-targets.json" >&2
  exit 1
fi

echo "→ Validating configuration"
agentcore validate

echo "→ Deploying (creates Runtime, Memory, Gateway, PolicyEngine, Evaluators)"
agentcore deploy --target "${1:-dev}"

echo
echo "Deployed. Next:"
echo "  agentcore logs            # stream runtime logs"
echo "  agentcore traces list     # inspect a run"
echo "  ./destroy.sh              # tear everything down"
