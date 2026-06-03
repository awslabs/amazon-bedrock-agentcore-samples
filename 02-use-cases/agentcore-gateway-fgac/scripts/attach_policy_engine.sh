#!/usr/bin/env bash
# Attach the Cedar policy engine to the AgentCore Gateway.
#
# Why this is a shim: the v6 AWS Terraform provider provisions both
# `aws_bedrockagentcore_gateway` and `aws_bedrockagentcore_policy_engine`,
# but does not expose `policyEngineConfiguration` on UpdateGateway. We
# call the AWS CLI directly until the provider catches up.
#
# Re-runnable: UpdateGateway is idempotent for the same payload.
#
# Usage:
#   scripts/attach_policy_engine.sh
#
# Required:
#   - AWS credentials with bedrock-agentcore-control:UpdateGateway on the gateway.
#   - `terraform output` available in infra/envs/dev/agentcore.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STACK_DIR="${REPO_ROOT}/infra/envs/dev/agentcore"

cd "${STACK_DIR}"

# Pull stack inputs (region, okta) from tfvars and outputs from state.
REGION="$(awk -F'=' '/^aws_region/ {gsub(/[" ]/, "", $2); print $2; exit}' terraform.tfvars)"
MODE="$(awk -F'=' '/^policy_engine_mode/ {gsub(/[" ]/, "", $2); print $2; exit}' terraform.tfvars)"
MODE="${MODE:-LOG_ONLY}"

GATEWAY_ID="$(terraform output -raw gateway_id)"
POLICY_ENGINE_ARN="$(terraform output -raw policy_engine_arn)"

# Re-fetch the existing gateway so we re-pass required fields (name,
# role, authorizer) without drift. UpdateGateway requires all of them.
GW_JSON="$(aws bedrock-agentcore-control get-gateway \
  --region "${REGION}" \
  --gateway-identifier "${GATEWAY_ID}")"

NAME="$(echo "${GW_JSON}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["name"])')"
ROLE_ARN="$(echo "${GW_JSON}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["roleArn"])')"
AUTHZ_TYPE="$(echo "${GW_JSON}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["authorizerType"])')"
AUTHZ_CFG="$(echo "${GW_JSON}" | python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin)["authorizerConfiguration"]))')"
PROTO_CFG="$(echo "${GW_JSON}" | python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin)["protocolConfiguration"]))')"

CURRENT_PE="$(echo "${GW_JSON}" | python3 -c "import json,sys; d=json.load(sys.stdin); pe=d.get('policyEngineConfiguration') or {}; print(f\"{pe.get('arn','<none>')} mode={pe.get('mode','<none>')}\")")"
echo "Current policy engine on gateway: ${CURRENT_PE}"
echo "Attaching: ${POLICY_ENGINE_ARN} (mode=${MODE})"

aws bedrock-agentcore-control update-gateway \
  --region "${REGION}" \
  --gateway-identifier "${GATEWAY_ID}" \
  --name "${NAME}" \
  --role-arn "${ROLE_ARN}" \
  --authorizer-type "${AUTHZ_TYPE}" \
  --authorizer-configuration "${AUTHZ_CFG}" \
  --protocol-configuration "${PROTO_CFG}" \
  --policy-engine-configuration "{\"arn\":\"${POLICY_ENGINE_ARN}\",\"mode\":\"${MODE}\"}" \
  >/dev/null

echo "Done. Verifying..."
aws bedrock-agentcore-control get-gateway \
  --region "${REGION}" \
  --gateway-identifier "${GATEWAY_ID}" \
  --query 'policyEngineConfiguration' \
  --output json
