#!/usr/bin/env bash
set -euo pipefail

# deploy_cfn.sh — Deploy Amazon Bedrock AgentCore infrastructure via CloudFormation
#
# Usage:
#   bash scripts/deploy_cfn.sh us-east-1 dev
#   bash scripts/deploy_cfn.sh us-east-1 prod LOG_ONLY
#
# Prerequisites:
#   - prereq.sh completed (Lambda, Cognito, IAM roles, SSM parameters)
#   - runtime.zip packaged via package_runtime.sh
#   - AWS CLI configured with sufficient permissions

REGION="${1:-us-east-1}"
ENV="${2:-dev}"
CEDAR_MODE="${3:-LOG_ONLY}"  # LOG_ONLY or ENFORCE

STACK_NAME="hr-data-agent-agentcore-${ENV}"
TEMPLATE_FILE="cfn/agentcore-infrastructure.yaml"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Amazon Bedrock AgentCore CloudFormation Deployment"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Region       : ${REGION}"
echo "Environment  : ${ENV}"
echo "Stack        : ${STACK_NAME}"
echo "Cedar mode   : ${CEDAR_MODE}"
echo ""

# ============================================================================
# Step 1: Read prerequisites from AWS Systems Manager Parameter Store
# ============================================================================
echo "→ Reading prerequisites from SSM..."

_get_param() {
  aws ssm get-parameter --region "${REGION}" --name "$1" --query 'Parameter.Value' --output text 2>/dev/null || echo ""
}

LAMBDA_ARN=$(_get_param "/app/hrdlp/lambda-arn")
REQUEST_INTERCEPTOR_ARN=$(_get_param "/app/hrdlp/request-interceptor-arn")
RESPONSE_INTERCEPTOR_ARN=$(_get_param "/app/hrdlp/response-interceptor-arn")
GATEWAY_ROLE_ARN=$(_get_param "/app/hrdlp/gateway-role-arn")
RUNTIME_ROLE_ARN=$(_get_param "/app/hrdlp/runtime-role-arn")
COGNITO_USER_POOL_ID=$(_get_param "/app/hrdlp/cognito-user-pool-id")
DEPLOY_BUCKET=$(_get_param "/app/hrdlp/deploy-bucket")

# Collect persona client IDs
HR_MANAGER_CLIENT=$(_get_param "/app/hrdlp/personas/hr-manager/client-id")
HR_SPECIALIST_CLIENT=$(_get_param "/app/hrdlp/personas/hr-specialist/client-id")
EMPLOYEE_CLIENT=$(_get_param "/app/hrdlp/personas/employee/client-id")
ADMIN_CLIENT=$(_get_param "/app/hrdlp/personas/admin/client-id")

# Build comma-separated list of non-empty client IDs
PERSONA_CLIENTS=""
for CLIENT in "${HR_MANAGER_CLIENT}" "${HR_SPECIALIST_CLIENT}" "${EMPLOYEE_CLIENT}" "${ADMIN_CLIENT}"; do
  if [[ -n "${CLIENT}" ]]; then
    if [[ -z "${PERSONA_CLIENTS}" ]]; then
      PERSONA_CLIENTS="${CLIENT}"
    else
      PERSONA_CLIENTS="${PERSONA_CLIENTS},${CLIENT}"
    fi
  fi
done

# Build interceptor configurations for Gateway update
INTERCEPTOR_CONFIGS="[]"
if [[ -n "${REQUEST_INTERCEPTOR_ARN}" && -n "${RESPONSE_INTERCEPTOR_ARN}" ]]; then
  INTERCEPTOR_CONFIGS="[{\"interceptor\":{\"lambda\":{\"arn\":\"${REQUEST_INTERCEPTOR_ARN}\"}},\"interceptionPoints\":[\"REQUEST\"],\"inputConfiguration\":{\"passRequestHeaders\":true}},{\"interceptor\":{\"lambda\":{\"arn\":\"${RESPONSE_INTERCEPTOR_ARN}\"}},\"interceptionPoints\":[\"RESPONSE\"],\"inputConfiguration\":{\"passRequestHeaders\":true}}]"
elif [[ -n "${REQUEST_INTERCEPTOR_ARN}" ]]; then
  INTERCEPTOR_CONFIGS="[{\"interceptor\":{\"lambda\":{\"arn\":\"${REQUEST_INTERCEPTOR_ARN}\"}},\"interceptionPoints\":[\"REQUEST\"],\"inputConfiguration\":{\"passRequestHeaders\":true}}]"
elif [[ -n "${RESPONSE_INTERCEPTOR_ARN}" ]]; then
  INTERCEPTOR_CONFIGS="[{\"interceptor\":{\"lambda\":{\"arn\":\"${RESPONSE_INTERCEPTOR_ARN}\"}},\"interceptionPoints\":[\"RESPONSE\"],\"inputConfiguration\":{\"passRequestHeaders\":true}}]"
fi

# Validate required parameters
if [[ -z "${LAMBDA_ARN}" || -z "${GATEWAY_ROLE_ARN}" || -z "${RUNTIME_ROLE_ARN}" || -z "${COGNITO_USER_POOL_ID}" || -z "${DEPLOY_BUCKET}" || -z "${PERSONA_CLIENTS}" ]]; then
  echo "ERROR: Missing required SSM parameters. Run prereq.sh first." >&2
  echo ""
  echo "Required parameters:"
  echo "  /app/hrdlp/lambda-arn             : ${LAMBDA_ARN:-MISSING}"
  echo "  /app/hrdlp/gateway-role-arn       : ${GATEWAY_ROLE_ARN:-MISSING}"
  echo "  /app/hrdlp/runtime-role-arn       : ${RUNTIME_ROLE_ARN:-MISSING}"
  echo "  /app/hrdlp/cognito-user-pool-id   : ${COGNITO_USER_POOL_ID:-MISSING}"
  echo "  /app/hrdlp/deploy-bucket          : ${DEPLOY_BUCKET:-MISSING}"
  echo "  Persona client IDs                : ${PERSONA_CLIENTS:-MISSING}"
  exit 1
fi

echo "  ✓ Lambda ARN              : ${LAMBDA_ARN}"
echo "  ✓ Gateway role ARN        : ${GATEWAY_ROLE_ARN}"
echo "  ✓ Runtime role ARN        : ${RUNTIME_ROLE_ARN}"
echo "  ✓ Cognito User Pool ID    : ${COGNITO_USER_POOL_ID}"
echo "  ✓ Deploy bucket           : ${DEPLOY_BUCKET}"
echo "  ✓ Persona client IDs      : $(echo "${PERSONA_CLIENTS}" | tr ',' '\n' | wc -l | tr -d ' ') clients"
if [[ -n "${REQUEST_INTERCEPTOR_ARN}" ]]; then
  echo "  ✓ Request interceptor ARN : ${REQUEST_INTERCEPTOR_ARN}"
fi
if [[ -n "${RESPONSE_INTERCEPTOR_ARN}" ]]; then
  echo "  ✓ Response interceptor ARN: ${RESPONSE_INTERCEPTOR_ARN}"
fi
echo ""

# ============================================================================
# Step 2: Upload runtime artifact to S3
# ============================================================================
RUNTIME_ZIP="dist/runtime.zip"
RUNTIME_S3_KEY="hr-data-agent/runtime.zip"

if [[ ! -f "${RUNTIME_ZIP}" ]]; then
  echo "ERROR: ${RUNTIME_ZIP} not found. Run: bash scripts/package_runtime.sh" >&2
  exit 1
fi

echo "→ Uploading runtime artifact to S3..."
aws s3 cp "${RUNTIME_ZIP}" "s3://${DEPLOY_BUCKET}/${RUNTIME_S3_KEY}" --region "${REGION}"
echo "  ✓ s3://${DEPLOY_BUCKET}/${RUNTIME_S3_KEY}"
echo ""

# ============================================================================
# Step 3: Deploy CloudFormation stack
# ============================================================================
echo "→ Deploying CloudFormation stack: ${STACK_NAME}..."
echo "  (This will take ~5-6 minutes)"
echo ""

aws cloudformation deploy \
  --region "${REGION}" \
  --stack-name "${STACK_NAME}" \
  --template-file "${TEMPLATE_FILE}" \
  --parameter-overrides \
      Environment="${ENV}" \
      LambdaArn="${LAMBDA_ARN}" \
      RequestInterceptorArn="${REQUEST_INTERCEPTOR_ARN}" \
      ResponseInterceptorArn="${RESPONSE_INTERCEPTOR_ARN}" \
      GatewayRoleArn="${GATEWAY_ROLE_ARN}" \
      RuntimeRoleArn="${RUNTIME_ROLE_ARN}" \
      CognitoUserPoolId="${COGNITO_USER_POOL_ID}" \
      PersonaClientIds="${PERSONA_CLIENTS}" \
      RuntimeS3Bucket="${DEPLOY_BUCKET}" \
      RuntimeS3Key="${RUNTIME_S3_KEY}" \
      CedarPolicyMode="${CEDAR_MODE}" \
  --capabilities CAPABILITY_IAM \
  --no-fail-on-empty-changeset

echo ""
echo "  ✓ Stack deployed: ${STACK_NAME}"
echo ""

# ============================================================================
# Step 4: Read stack outputs and write to SSM
# ============================================================================
echo "→ Reading stack outputs..."

_get_output() {
  aws cloudformation describe-stacks \
    --region "${REGION}" \
    --stack-name "${STACK_NAME}" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" \
    --output text
}

GATEWAY_ID=$(_get_output "GatewayId")
GATEWAY_URL=$(_get_output "GatewayUrl")
GATEWAY_ARN=$(_get_output "GatewayArn")
RUNTIME_ID=$(_get_output "RuntimeId")
RUNTIME_URL=$(_get_output "RuntimeUrl")

if [[ -z "${GATEWAY_ID}" || -z "${RUNTIME_ID}" || -z "${RUNTIME_URL}" ]]; then
  echo "ERROR: Failed to read stack outputs. Check CloudFormation console for errors." >&2
  exit 1
fi

echo "  ✓ Gateway ID          : ${GATEWAY_ID}"
echo "  ✓ Gateway URL         : ${GATEWAY_URL}"
echo "  ✓ Gateway ARN         : ${GATEWAY_ARN}"
echo "  ✓ Runtime ID          : ${RUNTIME_ID}"
echo "  ✓ Runtime URL         : ${RUNTIME_URL}"
echo ""

echo "→ Writing outputs to SSM..."
aws ssm put-parameter --region "${REGION}" --name "/app/hrdlp/gateway-id" --value "${GATEWAY_ID}" --type String --overwrite
aws ssm put-parameter --region "${REGION}" --name "/app/hrdlp/gateway-url" --value "${GATEWAY_URL}" --type String --overwrite
aws ssm put-parameter --region "${REGION}" --name "/app/hrdlp/gateway-arn" --value "${GATEWAY_ARN}" --type String --overwrite
aws ssm put-parameter --region "${REGION}" --name "/app/hrdlp/runtime-id" --value "${RUNTIME_ID}" --type String --overwrite
aws ssm put-parameter --region "${REGION}" --name "/app/hrdlp/runtime-url" --value "${RUNTIME_URL}" --type String --overwrite
echo "  ✓ SSM parameters updated"
echo ""

# ============================================================================
# Step 5: Create Cedar Policy Engine and attach to Gateway (boto3)
# ============================================================================
echo "→ Creating Cedar Policy Engine and policies..."
echo "  (Using boto3 script - CloudFormation has circular dependency issues)"
echo ""

python scripts/create_cedar_policies.py --region "${REGION}" --env "${ENV}" --mode "${CEDAR_MODE}"

if [[ $? -ne 0 ]]; then
  echo "ERROR: Failed to create Cedar policies." >&2
  exit 1
fi

echo "  ✓ Cedar policies created and attached to Gateway"
echo ""

# ============================================================================
# Done
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Deployment complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Next steps:"
echo "  1. Run the Streamlit app:"
echo "     streamlit run app.py"
echo ""
echo "  2. Test with a query:"
echo "     curl -X POST \"${RUNTIME_URL}\" \\"
echo "       -H \"Authorization: Bearer \${JWT_TOKEN}\" \\"
echo "       -H \"Content-Type: application/json\" \\"
echo "       -d '{\"userPrompt\": \"search for employees in engineering\"}'"
echo ""
if [[ "${CEDAR_MODE}" == "LOG_ONLY" ]]; then
  echo "⚠️  Cedar mode is LOG_ONLY — policies log but do not block requests."
  echo "   To enforce, redeploy with: bash scripts/deploy_cfn.sh ${REGION} ${ENV} ENFORCE"
  echo ""
fi
