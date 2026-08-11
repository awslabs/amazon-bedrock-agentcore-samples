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

FAQ_BUCKET="poc-validator-faq-kb-$(aws sts get-caller-identity --query Account --output text)"
if aws s3api head-bucket --bucket "$FAQ_BUCKET" >/dev/null 2>&1; then
  echo "→ Syncing FAQ knowledge base source docs to s3://${FAQ_BUCKET}/faq/"
  aws s3 sync agentcore/faq/ "s3://${FAQ_BUCKET}/faq/" --delete
else
  echo "→ Creating FAQ knowledge base bucket s3://${FAQ_BUCKET}"
  aws s3api create-bucket --bucket "$FAQ_BUCKET" --region "$(aws configure get region || echo us-east-1)"
  aws s3api put-public-access-block --bucket "$FAQ_BUCKET" --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
  aws s3api put-bucket-encryption --bucket "$FAQ_BUCKET" --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
  aws s3 sync agentcore/faq/ "s3://${FAQ_BUCKET}/faq/"
fi

echo "→ Deploying (creates Runtime, Memory, Gateway, KnowledgeBase, PolicyEngine, Evaluators)"
agentcore deploy --target "${1:-dev}"

echo "→ Granting the runtime execution role Code Interpreter access (see docs/decisions/0010)"
./scripts/grant_code_interpreter_access.sh || echo "  (non-fatal — see script output; you can re-run it any time)"

echo "→ Starting an initial ingestion job for the FAQ knowledge base (see docs/decisions/0011)"
./scripts/sync_faq_knowledge_base.sh || echo "  (non-fatal — ingestion needs an embedding model call; see script output)"

echo
echo "Deployed. Next:"
echo "  agentcore logs            # stream runtime logs"
echo "  agentcore traces list     # inspect a run"
echo "  ./destroy.sh              # tear everything down"
