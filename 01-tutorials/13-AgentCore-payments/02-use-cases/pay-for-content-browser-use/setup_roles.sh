#!/usr/bin/env bash
# =============================================================
# setup_roles.sh
#
# Creates the four IAM roles required by the Pay for Content
# (Browser Use) use case. Run once per AWS account before
# opening the notebook.
#
# Roles created:
#   AgentCorePaymentsControlPlaneRole    — provisioning (manager, connector, credential provider)
#   AgentCorePaymentsManagementRole      — session lifecycle (create/get/update sessions, instruments)
#   AgentCorePaymentsProcessPaymentRole  — agent runtime (ProcessPayment, GetPaymentInstrument, GetPaymentInstrumentBalance)
#   AgentCorePaymentsResourceRetrievalRole — service-side token retrieval (assumed by AgentCore service)
#
# After running, copy the printed ARNs into your .env file.
# =============================================================

set -euo pipefail

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
CALLER_ARN=$(aws sts get-caller-identity --query Arn --output text)
REGION=${AWS_REGION:-us-west-2}

# Build the principal for user-assumed trust policies.
# If the caller is an assumed role (SSO, federated, instance profile), include both
# the account root and the specific role ARN so the script works outside direct-user sessions.
CALLER_ROLE_ARN=""
if [[ "$CALLER_ARN" == *":assumed-role/"* ]]; then
    ROLE_NAME=$(echo "$CALLER_ARN" | sed 's/.*:assumed-role\///' | cut -d'/' -f1)
    CALLER_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
fi

if [[ -n "$CALLER_ROLE_ARN" ]]; then
    CLIENT_PRINCIPAL='["arn:aws:iam::'"${ACCOUNT_ID}"':root","'"${CALLER_ROLE_ARN}"'"]'
else
    CLIENT_PRINCIPAL='"arn:aws:iam::'"${ACCOUNT_ID}"':root"'
fi

echo ""
echo "AgentCore payments — IAM role setup"
echo "===================================="
echo "Account: $ACCOUNT_ID  Region: $REGION"
echo ""

# ── Helper ────────────────────────────────────────────────────────────────────
create_or_update_role() {
    local role_name="$1"
    local trust_policy="$2"
    local inline_policy_name="$3"
    local inline_policy="$4"

    if aws iam get-role --role-name "$role_name" &>/dev/null; then
        echo "  ↻ $role_name already exists — updating trust and inline policy"
        aws iam update-assume-role-policy \
            --role-name "$role_name" \
            --policy-document "$trust_policy"
    else
        aws iam create-role \
            --role-name "$role_name" \
            --assume-role-policy-document "$trust_policy" \
            --description "AgentCore payments — $role_name" \
            --output none
        echo "  ✅ Created $role_name"
    fi

    aws iam put-role-policy \
        --role-name "$role_name" \
        --policy-name "$inline_policy_name" \
        --policy-document "$inline_policy"
}

# ── 1. ControlPlaneRole ───────────────────────────────────────────────────────
# Used by notebook Steps 3a–3c: CreatePaymentCredentialProvider,
# CreatePaymentManager, CreatePaymentConnector.
# Uses bedrock-agentcore:* for breadth; explicitly denies ProcessPayment.

CONTROL_PLANE_TRUST=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowAccountAssume",
      "Effect": "Allow",
      "Principal": { "AWS": ${CLIENT_PRINCIPAL} },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
)

CONTROL_PLANE_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ControlPlaneOperations",
      "Effect": "Allow",
      "Action": "bedrock-agentcore:*",
      "Resource": "*"
    },
    {
      "Sid": "DenyDataPlanePaymentExecution",
      "Effect": "Deny",
      "Action": "bedrock-agentcore:ProcessPayment",
      "Resource": "*"
    },
    {
      "Sid": "SecretsManagerForCredentialProvider",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:CreateSecret",
        "secretsmanager:PutSecretValue",
        "secretsmanager:DeleteSecret"
      ],
      "Resource": "arn:aws:secretsmanager:*:${ACCOUNT_ID}:secret:bedrock-agentcore-identity*"
    },
    {
      "Sid": "PassRoles",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": [
        "arn:aws:iam::${ACCOUNT_ID}:role/AgentCorePaymentsResourceRetrievalRole",
        "arn:aws:iam::${ACCOUNT_ID}:role/AgentCorePaymentsManagementRole"
      ]
    }
  ]
}
EOF
)

echo "Creating ControlPlaneRole..."
create_or_update_role \
    "AgentCorePaymentsControlPlaneRole" \
    "$CONTROL_PLANE_TRUST" \
    "AgentCorePaymentsControlPlanePolicy" \
    "$CONTROL_PLANE_POLICY"

# ── 2. ManagementRole ─────────────────────────────────────────────────────────
# Used by notebook Steps 3d, 4, verify:
# CreatePaymentInstrument, CreatePaymentSession, GetPaymentSession.
# Explicitly denies ProcessPayment.

MANAGEMENT_TRUST=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowAccountAssume",
      "Effect": "Allow",
      "Principal": { "AWS": ${CLIENT_PRINCIPAL} },
      "Action": "sts:AssumeRole"
    },
    {
      "Sid": "AllowAccessToBedrockAgentcore",
      "Effect": "Allow",
      "Principal": { "Service": "bedrock-agentcore.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
)

MANAGEMENT_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "InstrumentAndSessionManagement",
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:CreatePaymentInstrument",
        "bedrock-agentcore:GetPaymentInstrument",
        "bedrock-agentcore:ListPaymentInstruments",
        "bedrock-agentcore:DeletePaymentInstrument",
        "bedrock-agentcore:CreatePaymentSession",
        "bedrock-agentcore:GetPaymentSession",
        "bedrock-agentcore:ListPaymentSessions"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DenyProcessPayment",
      "Effect": "Deny",
      "Action": "bedrock-agentcore:ProcessPayment",
      "Resource": "*"
    }
  ]
}
EOF
)

echo "Creating ManagementRole..."
create_or_update_role \
    "AgentCorePaymentsManagementRole" \
    "$MANAGEMENT_TRUST" \
    "AgentCorePaymentsManagementPolicy" \
    "$MANAGEMENT_POLICY"

# ── 3. ProcessPaymentRole ─────────────────────────────────────────────────────
# Used by the Strands agent at runtime (Steps 3e and 6):
# ProcessPayment, GetPaymentInstrument (required by AgentCorePaymentsPlugin SDK),
# and GetPaymentInstrumentBalance.
# Cannot create sessions or access credentials.

PROCESS_PAYMENT_TRUST=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowAccountAssume",
      "Effect": "Allow",
      "Principal": { "AWS": ${CLIENT_PRINCIPAL} },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
)

PROCESS_PAYMENT_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowProcessPayment",
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:ProcessPayment",
        "bedrock-agentcore:GetPaymentInstrument",
        "bedrock-agentcore:GetPaymentInstrumentBalance"
      ],
      "Resource": "*"
    }
  ]
}
EOF
)

echo "Creating ProcessPaymentRole..."
create_or_update_role \
    "AgentCorePaymentsProcessPaymentRole" \
    "$PROCESS_PAYMENT_TRUST" \
    "AllowProcessPayment" \
    "$PROCESS_PAYMENT_POLICY"

# ── 4. ResourceRetrievalRole ──────────────────────────────────────────────────
# Assumed by the AgentCore service (not the notebook) to retrieve payment tokens.
# Trust policy allows bedrock-agentcore.amazonaws.com to assume this role.

RESOURCE_RETRIEVAL_TRUST=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowAccessToBedrockAgentcore",
      "Effect": "Allow",
      "Principal": { "Service": "bedrock-agentcore.amazonaws.com" },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "aws:SourceAccount": "${ACCOUNT_ID}"
        },
        "ArnLike": {
          "aws:SourceArn": "arn:aws:bedrock-agentcore:${REGION}:${ACCOUNT_ID}:payment-manager/*"
        }
      }
    }
  ]
}
EOF
)

RESOURCE_RETRIEVAL_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BedrockAgentCoreGetResourcePaymentToken",
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:GetWorkloadAccessToken",
        "bedrock-agentcore:CreateWorkloadIdentity",
        "bedrock-agentcore:GetResourcePaymentToken"
      ],
      "Resource": [
        "arn:aws:bedrock-agentcore:*:${ACCOUNT_ID}:token-vault/default",
        "arn:aws:bedrock-agentcore:*:${ACCOUNT_ID}:token-vault/default/paymentcredentialprovider/*",
        "arn:aws:bedrock-agentcore:*:${ACCOUNT_ID}:token-vault/default/*",
        "arn:aws:bedrock-agentcore:*:${ACCOUNT_ID}:workload-identity-directory/default",
        "arn:aws:bedrock-agentcore:*:${ACCOUNT_ID}:workload-identity-directory/default/workload-identity/*"
      ]
    },
    {
      "Sid": "SecretsManagerAccess",
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "arn:aws:secretsmanager:*:${ACCOUNT_ID}:secret:*"
    },
    {
      "Sid": "StsAddTokenContext",
      "Effect": "Allow",
      "Action": "sts:SetContext",
      "Resource": "arn:aws:sts::${ACCOUNT_ID}:self"
    }
  ]
}
EOF
)

echo "Creating ResourceRetrievalRole..."
create_or_update_role \
    "AgentCorePaymentsResourceRetrievalRole" \
    "$RESOURCE_RETRIEVAL_TRUST" \
    "AgentCorePaymentsResourceRetrievalPolicy" \
    "$RESOURCE_RETRIEVAL_POLICY"

# ── Print ARNs ────────────────────────────────────────────────────────────────
echo ""
echo "✅ All roles ready. Copy these ARNs into your .env:"
echo ""
for role in \
    AgentCorePaymentsControlPlaneRole \
    AgentCorePaymentsManagementRole \
    AgentCorePaymentsProcessPaymentRole \
    AgentCorePaymentsResourceRetrievalRole; do
    arn=$(aws iam get-role --role-name "$role" --query Role.Arn --output text)
    echo "  $arn"
done
echo ""
