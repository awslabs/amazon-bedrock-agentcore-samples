client_trust_policy() {
  jq -n --arg setupPrincipal "$TRUSTED_SETUP_PRINCIPAL_ARN" '{
    Version: "2012-10-17",
    Statement: [{
      Sid: "AllowSpecificSetupPrincipalAssume",
      Effect: "Allow",
      Principal: {AWS: $setupPrincipal},
      Action: "sts:AssumeRole"
    }]
  }'
}

service_trust_policy() {
  jq -n '{
    Version: "2012-10-17",
    Statement: [{
      Sid: "AllowAccessToBedrockAgentCore",
      Effect: "Allow",
      Principal: {Service: "bedrock-agentcore.amazonaws.com"},
      Action: "sts:AssumeRole"
    }]
  }'
}

process_payment_trust_policy() {
  jq -n \
    --arg setupPrincipal "$TRUSTED_SETUP_PRINCIPAL_ARN" \
    --arg accountId "$ACCOUNT_ID" \
    --arg region "$AWS_REGION" \
    '{
    Version: "2012-10-17",
    Statement: [
      {
        Sid: "AllowSpecificSetupPrincipalAssume",
        Effect: "Allow",
        Principal: {AWS: $setupPrincipal},
        Action: "sts:AssumeRole"
      },
      {
        Sid: "AllowAgentCoreRuntimeAssume",
        Effect: "Allow",
        Principal: {Service: "bedrock-agentcore.amazonaws.com"},
        Action: "sts:AssumeRole",
        Condition: {
          StringEquals: {"aws:SourceAccount": $accountId},
          ArnLike: {"aws:SourceArn": ("arn:aws:bedrock-agentcore:" + $region + ":" + $accountId + ":runtime/*")}
        }
      }
    ]
  }'
}

control_plane_policy() {
  jq -n '{
    Version: "2012-10-17",
    Statement: [{
      Sid: "AllowControlPlaneOperations",
      Effect: "Allow",
      Action: [
        "bedrock-agentcore:CreatePaymentManager",
        "bedrock-agentcore:GetPaymentManager",
        "bedrock-agentcore:ListPaymentManagers",
        "bedrock-agentcore:DeletePaymentManager",
        "bedrock-agentcore:UpdatePaymentManager",
        "bedrock-agentcore:CreatePaymentConnector",
        "bedrock-agentcore:GetPaymentConnector",
        "bedrock-agentcore:ListPaymentConnectors",
        "bedrock-agentcore:DeletePaymentConnector",
        "bedrock-agentcore:UpdatePaymentConnector",
        "bedrock-agentcore:CreatePaymentCredentialProvider",
        "bedrock-agentcore:GetPaymentCredentialProvider",
        "bedrock-agentcore:ListPaymentCredentialProviders",
        "bedrock-agentcore:DeletePaymentCredentialProvider",
        "bedrock-agentcore:UpdatePaymentCredentialProvider"
      ],
      Resource: "*"
    }]
  }'
}

pass_role_policy() {
  jq -n --arg accountId "$ACCOUNT_ID" --arg rrRole "$RESOURCE_RETRIEVAL_ROLE_NAME" '{
    Version: "2012-10-17",
    Statement: [{
      Sid: "AllowPassResourceRetrievalRole",
      Effect: "Allow",
      Action: "iam:PassRole",
      Resource: ("arn:aws:iam::" + $accountId + ":role/" + $rrRole)
    }]
  }'
}

management_allow_policy() {
  jq -n '{
    Version: "2012-10-17",
    Statement: [{
      Sid: "AllowPaymentManagement",
      Effect: "Allow",
      Action: [
        "bedrock-agentcore:CreatePaymentInstrument",
        "bedrock-agentcore:GetPaymentInstrument",
        "bedrock-agentcore:ListPaymentInstruments",
        "bedrock-agentcore:DeletePaymentInstrument",
        "bedrock-agentcore:CreatePaymentSession",
        "bedrock-agentcore:GetPaymentSession",
        "bedrock-agentcore:ListPaymentSessions",
        "bedrock-agentcore:UpdatePaymentSession"
      ],
      Resource: "*"
    }]
  }'
}

management_deny_policy() {
  jq -n '{
    Version: "2012-10-17",
    Statement: [{
      Sid: "DenyProcessPayment",
      Effect: "Deny",
      Action: "bedrock-agentcore:ProcessPayment",
      Resource: "*"
    }]
  }'
}

process_payment_allow_policy() {
  jq -n '{
    Version: "2012-10-17",
    Statement: [{
      Sid: "AllowProcessPayment",
      Effect: "Allow",
      Action: [
        "bedrock-agentcore:ProcessPayment",
        "bedrock-agentcore:GetPaymentInstrument",
        "bedrock-agentcore:GetPaymentSession"
      ],
      Resource: "*"
    }]
  }'
}

process_payment_deny_policy() {
  jq -n '{
    Version: "2012-10-17",
    Statement: [{
      Sid: "DenyPaymentManagement",
      Effect: "Deny",
      Action: [
        "bedrock-agentcore:CreatePaymentInstrument",
        "bedrock-agentcore:DeletePaymentInstrument",
        "bedrock-agentcore:CreatePaymentSession",
        "bedrock-agentcore:UpdatePaymentSession"
      ],
      Resource: "*"
    }]
  }'
}

runtime_execution_policy() {
  jq -n --arg accountId "$ACCOUNT_ID" --arg region "$AWS_REGION" '{
    Version: "2012-10-17",
    Statement: [
      {
        Sid: "RuntimeECRAccess",
        Effect: "Allow",
        Action: [
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer",
          "ecr:GetAuthorizationToken"
        ],
        Resource: "*"
      },
      {
        Sid: "RuntimeCloudWatchLogs",
        Effect: "Allow",
        Action: [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams",
          "logs:PutLogEvents"
        ],
        Resource: [
          ("arn:aws:logs:" + $region + ":" + $accountId + ":log-group:/aws/bedrock-agentcore/runtimes/*"),
          ("arn:aws:logs:" + $region + ":" + $accountId + ":log-group:*")
        ]
      },
      {
        Sid: "RuntimeXRay",
        Effect: "Allow",
        Action: [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords",
          "xray:GetSamplingRules",
          "xray:GetSamplingTargets"
        ],
        Resource: "*"
      },
      {
        Sid: "RuntimeCloudWatchMetrics",
        Effect: "Allow",
        Action: "cloudwatch:PutMetricData",
        Resource: "*",
        Condition: {
          StringEquals: {"cloudwatch:namespace": "bedrock-agentcore"}
        }
      },
      {
        Sid: "BedrockModelInvocation",
        Effect: "Allow",
        Action: [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ],
        Resource: [
          "arn:aws:bedrock:*::foundation-model/*",
          ("arn:aws:bedrock:*:" + $accountId + ":inference-profile/*"),
          ("arn:aws:bedrock:*:" + $accountId + ":application-inference-profile/*")
        ]
      }
    ]
  }'
}

resource_retrieval_policy() {
  if [[ -n "${CREDENTIAL_PROVIDER_SECRET_ARN:-}" ]]; then
    jq -n --arg secretArn "$CREDENTIAL_PROVIDER_SECRET_ARN" '{
      Version: "2012-10-17",
      Statement: [
        {
          Sid: "AllowResourcePaymentToken",
          Effect: "Allow",
          Action: "bedrock-agentcore:GetResourcePaymentToken",
          Resource: "*"
        },
        {
          Sid: "AllowSpecificCredentialSecret",
          Effect: "Allow",
          Action: "secretsmanager:GetSecretValue",
          Resource: $secretArn
        }
      ]
    }'
  else
    jq -n '{
      Version: "2012-10-17",
      Statement: [{
        Sid: "AllowResourcePaymentToken",
        Effect: "Allow",
        Action: "bedrock-agentcore:GetResourcePaymentToken",
        Resource: "*"
      }]
    }'
  fi
}
