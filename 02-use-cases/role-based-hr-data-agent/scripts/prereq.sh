#!/bin/bash
# =============================================================================
# role-based-hr-data-agent — Master Prerequisites Deployment Script
#
# Deploys all infrastructure required before configuring AgentCore Gateway
# and Runtime. Run once per environment.
#
# Steps:
#   1. Create S3 bucket for Lambda artifacts
#   2. Package and upload Lambda ZIPs (HR Provider + Interceptors)
#   3. Deploy infrastructure.yaml CloudFormation stack
#   4. Deploy cognito.yaml CloudFormation stack
#   5. Create Cognito persona app clients
#
# Usage:
#   bash scripts/prereq.sh [--region us-east-1] [--env dev]
# =============================================================================

set -euo pipefail

REGION="us-east-1"
ENV="dev"
CONFIG="prerequisite/prereqs_config.yaml"
STACK_INFRA="hr-dlp-infrastructure-${ENV}"
STACK_COGNITO="hr-dlp-cognito-${ENV}"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --region) REGION="$2"; shift 2 ;;
    --env) ENV="$2"; STACK_INFRA="hr-dlp-infrastructure-${ENV}"; STACK_COGNITO="hr-dlp-cognito-${ENV}"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET="hr-dlp-deploy-${ACCOUNT_ID}-${REGION}"

echo "============================================================"
echo "  Role-Based HR Data Agent — Prerequisites Deployment"
echo "  Region: ${REGION}  |  Environment: ${ENV}"
echo "  Account: ${ACCOUNT_ID}"
echo "============================================================"

# ---------------------------------------------------------------------------
# Step 1: Create S3 bucket
# ---------------------------------------------------------------------------
echo ""
echo "Step 1: Creating S3 bucket: ${BUCKET}"
if aws s3api head-bucket --bucket "${BUCKET}" --region "${REGION}" 2>/dev/null; then
  echo "  Bucket already exists — skipping creation"
else
  if [[ "${REGION}" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "${BUCKET}" --region "${REGION}"
  else
    aws s3api create-bucket --bucket "${BUCKET}" --region "${REGION}" \
      --create-bucket-configuration LocationConstraint="${REGION}"
  fi
  echo "  Bucket created: ${BUCKET}"

  # Block all public access
  aws s3api put-public-access-block \
    --bucket "${BUCKET}" \
    --public-access-block-configuration \
      BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
  echo "  Block Public Access enabled"

  # Enable default encryption (SSE-S3 / AES-256)
  aws s3api put-bucket-encryption \
    --bucket "${BUCKET}" \
    --server-side-encryption-configuration \
      '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"},"BucketKeyEnabled":true}]}'
  echo "  Default encryption (AES-256) enabled"

  # Enforce TLS-only access
  aws s3api put-bucket-policy \
    --bucket "${BUCKET}" \
    --policy "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Sid\":\"DenyNonTLS\",\"Effect\":\"Deny\",\"Principal\":\"*\",\"Action\":\"s3:*\",\"Resource\":[\"arn:aws:s3:::${BUCKET}\",\"arn:aws:s3:::${BUCKET}/*\"],\"Condition\":{\"Bool\":{\"aws:SecureTransport\":\"false\"}}}]}"
  echo "  TLS-only bucket policy applied"
fi
# Store bucket name in SSM so agentcore_agent_runtime.py create can read it
aws ssm put-parameter \
  --name "/app/hrdlp/deploy-bucket" \
  --value "${BUCKET}" \
  --type String \
  --overwrite \
  --region "${REGION}" > /dev/null
echo "  SSM: /app/hrdlp/deploy-bucket = ${BUCKET}"

# ---------------------------------------------------------------------------
# Step 2: Package and upload Lambda ZIPs
# ---------------------------------------------------------------------------
echo ""
echo "Step 2: Packaging Lambda functions"

TMP_DIR=$(mktemp -d)
trap "rm -rf ${TMP_DIR}" EXIT

# HR Data Provider
echo "  Packaging HR Data Provider..."
cp prerequisite/lambda/python/*.py "${TMP_DIR}/"
(cd "${TMP_DIR}" && zip -q hr-data-provider.zip *.py)
aws s3 cp "${TMP_DIR}/hr-data-provider.zip" "s3://${BUCKET}/hr-data-provider/deployment.zip"
echo "  Uploaded: s3://${BUCKET}/hr-data-provider/deployment.zip"

# Interceptors
echo "  Packaging Interceptors..."
mkdir -p "${TMP_DIR}/interceptors"
cp prerequisite/lambda/interceptors/*.py "${TMP_DIR}/interceptors/"
(cd "${TMP_DIR}/interceptors" && zip -q ../hr-interceptors.zip *.py)
aws s3 cp "${TMP_DIR}/hr-interceptors.zip" "s3://${BUCKET}/hr-interceptors/deployment.zip"
echo "  Uploaded: s3://${BUCKET}/hr-interceptors/deployment.zip"

# ---------------------------------------------------------------------------
# Step 3: Deploy infrastructure.yaml
# ---------------------------------------------------------------------------
echo ""
echo "Step 3: Deploying infrastructure CloudFormation stack: ${STACK_INFRA}"
aws cloudformation deploy \
  --template-file prerequisite/infrastructure.yaml \
  --stack-name "${STACK_INFRA}" \
  --region "${REGION}" \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    LambdaS3Bucket="${BUCKET}" \
    LambdaS3Key="hr-data-provider/deployment.zip" \
    InterceptorS3Key="hr-interceptors/deployment.zip" \
    Environment="${ENV}" \
  --no-fail-on-empty-changeset
echo "  Infrastructure stack deployed"

# ---------------------------------------------------------------------------
# Step 4: Deploy cognito.yaml
# ---------------------------------------------------------------------------
echo ""
echo "Step 4: Deploying Cognito CloudFormation stack: ${STACK_COGNITO}"
COGNITO_DOMAIN_PREFIX="hr-dlp-agent"
aws cloudformation deploy \
  --template-file prerequisite/cognito.yaml \
  --stack-name "${STACK_COGNITO}" \
  --region "${REGION}" \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    Environment="${ENV}" \
    CognitoDomainPrefix="${COGNITO_DOMAIN_PREFIX}" \
  --no-fail-on-empty-changeset
echo "  Cognito stack deployed"

# ---------------------------------------------------------------------------
# Step 5: Create persona app clients
# ---------------------------------------------------------------------------
echo ""
echo "Step 5: Creating Cognito persona app clients"
python scripts/cognito_credentials_provider.py create --config "${CONFIG}" --region "${REGION}"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "  Prerequisites deployment complete!"
echo ""
echo "  Next steps:"
echo "  1. Build and upload runtime package:"
echo "     bash scripts/package_runtime.sh"
echo "     BUCKET=\$(aws ssm get-parameter --name /app/hrdlp/deploy-bucket --query Parameter.Value --output text)"
echo "     aws s3 cp dist/runtime.zip s3://\${BUCKET}/hr-data-agent/runtime.zip"
echo ""
echo "  2. Create AgentCore Gateway:"
echo "     python scripts/agentcore_gateway.py create --config ${CONFIG}"
echo "     (Gateway ARN printed + stored in SSM /app/hrdlp/gateway-arn)"
echo ""
echo "  3. Create Cedar Policy Engine and attach to Gateway:"
echo "     python scripts/create_cedar_policies.py --region ${REGION} --env ${ENV}"
echo "     # Creates engine, attaches to gateway (preserving interceptors), creates 3 policies"
echo "     # Add --mode ENFORCE to block unauthorized requests (default: LOG_ONLY)"
echo ""
echo "  4. Create AgentCore Runtime:"
echo "     python scripts/agentcore_agent_runtime.py create"
echo ""
echo "  5. Run tests:"
echo "     python test/test_gateway.py --persona hr-manager"
echo "     python test/test_dlp_redaction.py"
echo "     python test/test_agent.py --persona hr-manager"
echo ""
echo "  6. Run the Streamlit app:"
echo "     streamlit run app.py"
echo ""
echo "     The app reads all config from SSM automatically — no manual setup."
echo "     Usage: select a persona → Get OAuth Token → Discover Tools → send a query."
echo "     Switch personas to see DLP redaction applied based on OAuth scopes."
echo "============================================================"
