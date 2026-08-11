#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Grants the deployed runtime execution role access to AgentCore's
# AWS-managed Code Interpreter sandbox (aws.codeinterpreter.v1).
#
# Not something `agentcore.json` has a field for — there is no top-level
# "codeInterpreters" resource in this CLI version. The what-if pricing tool
# (app/pocvalidator/tools/what_if_pricing.py) calls the managed sandbox
# directly via the bedrock_agentcore SDK, so the only infrastructure gap is
# this IAM grant. See docs/decisions/0010 for the full design rationale.
#
# Idempotent — safe to re-run after every `agentcore deploy`, since a fresh
# deploy can in principle regenerate the execution role's logical ID.
#
# Usage: ./scripts/grant_code_interpreter_access.sh [region]
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
REGION="${1:-${AWS_REGION:-us-east-1}}"

command -v jq >/dev/null 2>&1 || { echo "jq is required." >&2; exit 1; }

ROLE_ARN=$(cd "$PROJECT_DIR" && agentcore status --json 2>/dev/null \
  | jq -r '.deployedState.targets.dev.resources.runtimes.pocvalidator.roleArn // empty')

if [[ -z "$ROLE_ARN" ]]; then
  echo "Could not find the runtime execution role — is the stack deployed? (agentcore status --json)" >&2
  exit 1
fi

ROLE_NAME=$(basename "$ROLE_ARN")
echo "Runtime execution role: $ROLE_NAME"

POLICY_DOC=$(cat <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PocValidatorCodeInterpreterManagedSandbox",
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:StartCodeInterpreterSession",
        "bedrock-agentcore:InvokeCodeInterpreter",
        "bedrock-agentcore:StopCodeInterpreterSession"
      ],
      "Resource": "arn:aws:bedrock-agentcore:${REGION}:aws:code-interpreter/aws.codeinterpreter.v1"
    }
  ]
}
JSON
)

aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "PocValidatorCodeInterpreterAccess" \
  --policy-document "$POLICY_DOC"

echo "Granted StartCodeInterpreterSession/InvokeCodeInterpreter/StopCodeInterpreterSession"
echo "on the AWS-managed sandbox (aws.codeinterpreter.v1) to $ROLE_NAME."
