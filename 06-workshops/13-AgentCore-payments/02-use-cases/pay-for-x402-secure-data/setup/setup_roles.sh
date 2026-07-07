#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SAMPLE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${ENV_FILE:-$SAMPLE_ROOT/.env}"

if [[ -f "$ENV_FILE" ]]; then
  set -o allexport
  source "$ENV_FILE"
  set +o allexport
fi

source "$SCRIPT_DIR/setup_roles_helpers.sh"
source "$SCRIPT_DIR/setup_roles_policies.sh"

need_cmd aws
need_cmd jq
need_cmd python3

AWS_REGION="${AWS_REGION:-us-west-2}"
ROLE_NAME_PREFIX="${ROLE_NAME_PREFIX:-AgentCoreX402SecureData}"
CONTROL_PLANE_ROLE_NAME="${CONTROL_PLANE_ROLE_NAME:-${ROLE_NAME_PREFIX}ControlPlaneRole}"
MANAGEMENT_ROLE_NAME="${MANAGEMENT_ROLE_NAME:-${ROLE_NAME_PREFIX}ManagementRole}"
PROCESS_PAYMENT_ROLE_NAME="${PROCESS_PAYMENT_ROLE_NAME:-${ROLE_NAME_PREFIX}ProcessPaymentRole}"
RESOURCE_RETRIEVAL_ROLE_NAME="${RESOURCE_RETRIEVAL_ROLE_NAME:-${ROLE_NAME_PREFIX}ResourceRetrievalRole}"

CALLER_IDENTITY="$(aws sts get-caller-identity --output json)"
ACCOUNT_ID="$(echo "$CALLER_IDENTITY" | jq -r '.Account')"

if [[ -z "${CONFIRM_AWS_ACCOUNT_ID:-}" || "$CONFIRM_AWS_ACCOUNT_ID" != "$ACCOUNT_ID" ]]; then
  die "CONFIRM_AWS_ACCOUNT_ID does not match the current AWS caller. Update $ENV_FILE before mutating AWS resources."
fi

aws bedrock-agentcore help >/dev/null
aws bedrock-agentcore-control help >/dev/null

CALLER_ARN="$(echo "$CALLER_IDENTITY" | jq -r '.Arn')"
TRUSTED_SETUP_PRINCIPAL_ARN="${TRUSTED_SETUP_PRINCIPAL_ARN:-$(resolve_trusted_setup_principal "$CALLER_ARN" "$ACCOUNT_ID")}"

if [[ -z "$TRUSTED_SETUP_PRINCIPAL_ARN" || "$TRUSTED_SETUP_PRINCIPAL_ARN" == *":root" ]]; then
  die "Set TRUSTED_SETUP_PRINCIPAL_ARN to a specific IAM role or user ARN. Account root trust is not allowed."
fi

CLIENT_TRUST_POLICY="$(client_trust_policy)"
SERVICE_TRUST_POLICY="$(service_trust_policy)"
PROCESS_PAYMENT_TRUST_POLICY="$(process_payment_trust_policy)"
CONTROL_PLANE_POLICY="$(control_plane_policy)"
PASS_ROLE_POLICY="$(pass_role_policy)"
MANAGEMENT_ALLOW_POLICY="$(management_allow_policy)"
MANAGEMENT_DENY_POLICY="$(management_deny_policy)"
PROCESS_PAYMENT_ALLOW_POLICY="$(process_payment_allow_policy)"
PROCESS_PAYMENT_DENY_POLICY="$(process_payment_deny_policy)"
RUNTIME_EXECUTION_POLICY="$(runtime_execution_policy)"
RESOURCE_RETRIEVAL_POLICY="$(resource_retrieval_policy)"

echo "Creating or updating sample-scoped AgentCore Payments roles in region $AWS_REGION."

upsert_role "$CONTROL_PLANE_ROLE_NAME" "AgentCore x402 secure data control plane role" "$CLIENT_TRUST_POLICY"
put_policy "$CONTROL_PLANE_ROLE_NAME" "AllowControlPlaneOperations" "$CONTROL_PLANE_POLICY"
put_policy "$CONTROL_PLANE_ROLE_NAME" "AllowPassRole" "$PASS_ROLE_POLICY"

upsert_role "$MANAGEMENT_ROLE_NAME" "AgentCore x402 secure data management role" "$CLIENT_TRUST_POLICY"
put_policy "$MANAGEMENT_ROLE_NAME" "AllowPaymentManagement" "$MANAGEMENT_ALLOW_POLICY"
put_policy "$MANAGEMENT_ROLE_NAME" "DenyProcessPayment" "$MANAGEMENT_DENY_POLICY"

upsert_role "$PROCESS_PAYMENT_ROLE_NAME" "AgentCore x402 secure data payment execution role" "$PROCESS_PAYMENT_TRUST_POLICY"
put_policy "$PROCESS_PAYMENT_ROLE_NAME" "AllowProcessPayment" "$PROCESS_PAYMENT_ALLOW_POLICY"
put_policy "$PROCESS_PAYMENT_ROLE_NAME" "DenyPaymentManagement" "$PROCESS_PAYMENT_DENY_POLICY"
put_policy "$PROCESS_PAYMENT_ROLE_NAME" "AllowRuntimeExecution" "$RUNTIME_EXECUTION_POLICY"

upsert_role "$RESOURCE_RETRIEVAL_ROLE_NAME" "AgentCore x402 secure data resource retrieval role" "$SERVICE_TRUST_POLICY"
put_policy "$RESOURCE_RETRIEVAL_ROLE_NAME" "AllowResourceRetrieval" "$RESOURCE_RETRIEVAL_POLICY"

CONTROL_PLANE_ROLE_ARN="$(role_arn "$CONTROL_PLANE_ROLE_NAME")"
MANAGEMENT_ROLE_ARN="$(role_arn "$MANAGEMENT_ROLE_NAME")"
PROCESS_PAYMENT_ROLE_ARN="$(role_arn "$PROCESS_PAYMENT_ROLE_NAME")"
RESOURCE_RETRIEVAL_ROLE_ARN="$(role_arn "$RESOURCE_RETRIEVAL_ROLE_NAME")"

update_env_file \
  "CONTROL_PLANE_ROLE_ARN=$CONTROL_PLANE_ROLE_ARN" \
  "MANAGEMENT_ROLE_ARN=$MANAGEMENT_ROLE_ARN" \
  "PROCESS_PAYMENT_ROLE_ARN=$PROCESS_PAYMENT_ROLE_ARN" \
  "RESOURCE_RETRIEVAL_ROLE_ARN=$RESOURCE_RETRIEVAL_ROLE_ARN"

echo "Role setup complete. Role names:"
printf '  %s\n' \
  "$CONTROL_PLANE_ROLE_NAME" \
  "$MANAGEMENT_ROLE_NAME" \
  "$PROCESS_PAYMENT_ROLE_NAME" \
  "$RESOURCE_RETRIEVAL_ROLE_NAME"
echo "Updated $ENV_FILE with role ARN variables. Values are not printed."
if [[ -z "${CREDENTIAL_PROVIDER_SECRET_ARN:-}" ]]; then
  echo "Secrets Manager credential access was not added. Set CREDENTIAL_PROVIDER_SECRET_ARN and rerun if your AgentCore credential provider requires it."
fi
