#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Starts an ingestion job for the PocValidatorFaqKB knowledge base, so the
# FAQ docs under agentcore/faq/ (already synced to S3 by deploy.sh) get
# embedded and indexed.
#
# Separate from `agentcore deploy`: deploy provisions the Knowledge Base
# *resource* (a control-plane, CloudFormation-driven operation), but does not
# ingest documents into it — ingestion is a distinct, explicit step (and the
# one that calls an embedding model). See docs/decisions/0011 for why this
# script exists rather than folding ingestion into the CDK stack.
#
# Usage: ./scripts/sync_faq_knowledge_base.sh [region]
# ============================================================================

REGION="${1:-${AWS_REGION:-us-east-1}}"
KB_NAME="PocValidatorFaqKB"

command -v jq >/dev/null 2>&1 || { echo "jq is required." >&2; exit 1; }

KB_ID=$(aws bedrock-agent list-knowledge-bases --region "$REGION" --output json \
  | jq -r --arg name "$KB_NAME" '.knowledgeBaseSummaries[] | select(.name | contains($name)) | .knowledgeBaseId' | head -1)

if [[ -z "$KB_ID" || "$KB_ID" == "None" ]]; then
  echo "Could not find knowledge base '${KB_NAME}' in ${REGION} — is it deployed?" >&2
  exit 1
fi

DATA_SOURCE_ID=$(aws bedrock-agent list-data-sources --knowledge-base-id "$KB_ID" --region "$REGION" \
  --query "dataSourceSummaries[0].dataSourceId" --output text)

if [[ -z "$DATA_SOURCE_ID" || "$DATA_SOURCE_ID" == "None" ]]; then
  echo "Knowledge base ${KB_ID} has no data source configured." >&2
  exit 1
fi

echo "Knowledge base: $KB_ID   Data source: $DATA_SOURCE_ID"
echo "Starting ingestion job..."

JOB_ID=$(aws bedrock-agent start-ingestion-job \
  --knowledge-base-id "$KB_ID" \
  --data-source-id "$DATA_SOURCE_ID" \
  --region "$REGION" \
  --query "ingestionJob.ingestionJobId" --output text)

echo "Ingestion job started: $JOB_ID"
echo "Check status with:"
echo "  aws bedrock-agent get-ingestion-job --knowledge-base-id $KB_ID --data-source-id $DATA_SOURCE_ID --ingestion-job-id $JOB_ID --region $REGION"
