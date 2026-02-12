resource "aws_iam_policy" "bedrock_permissions" {
  name = "${var.role_name}-bedrock-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "BedrockPermissions"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          "arn:aws:bedrock:${data.aws_region.current.name}::foundation-model/anthropic.*",
          "arn:aws:bedrock:${data.aws_region.current.name}::foundation-model/amazon.*",
          "arn:aws:bedrock:${data.aws_region.current.name}::foundation-model/meta.*"
        ]
      }
    ]
  })
}

resource "aws_iam_policy" "ecr_permissions" {
  name = "${var.role_name}-ecr-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ECRImageAccess"
        Effect = "Allow"
        Action = [
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer"
        ]
        Resource = (
          var.container_repository_arn == "" ?
          [
            "arn:aws:ecr:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:repository/*"
          ] :
          [var.container_repository_arn]
        )
      },
      {
        Sid    = "ECRTokenAccess"
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken"
        ]
        # tfsec:ignore:aws-iam-no-policy-wildcards - Required for ECR access
        # This action does not accept any restrictions on the resource, per the docs:
        # https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazonelasticcontainerregistry.html
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_policy" "logging_permissions" {
  name = "${var.role_name}-logging-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:DescribeLogStreams",
          "logs:CreateLogGroup"
        ]
        Resource = [
          "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:DescribeLogGroups"
        ]
        Resource = [
          "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = [
          "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"
        ]
      }
    ]
  })
}

resource "aws_iam_policy" "monitoring_permissions" {
  name = "${var.role_name}-monitoring-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords",
          "xray:GetSamplingRules",
          "xray:GetSamplingTargets"
        ]
        Resource = [
          "arn:aws:xray:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:trace/*"
        ]
      },
      {
        # tfsec:ignore:aws-iam-no-policy-wildcards - Required for CloudWatch metrics
        # WILDCARD JUSTIFICATION: CloudWatch PutMetricData requires Resource="*" 
        # as per AWS documentation. Condition restricts to bedrock-agentcore namespace only.
        # Reference: https://docs.aws.amazon.com/AmazonCloudWatch/latest/APIReference/API_PutMetricData.html
        Effect   = "Allow"
        Resource = "*"
        Action   = "cloudwatch:PutMetricData"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "bedrock-agentcore"
          }
        }
      }
    ]
  })
}

resource "aws_iam_policy" "agentcore_permissions" {
  name = "${var.role_name}-agentcore-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "GetAgentAccessToken"
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:GetWorkloadAccessToken",
          "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
          "bedrock-agentcore:GetWorkloadAccessTokenForUserId"
        ]
        Resource = [
          "arn:aws:bedrock-agentcore:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:workload-identity-directory/default",
          "arn:aws:bedrock-agentcore:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:workload-identity-directory/default/workload-identity/*"
        ]
      },
      {
        Sid    = "AccessMemory"
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:BatchCreateMemoryRecords",
          "bedrock-agentcore:BatchDeleteMemoryRecords",
          "bedrock-agentcore:BatchUpdateMemoryRecords",
          "bedrock-agentcore:CreateEvent",
          "bedrock-agentcore:DeleteEvent",
          "bedrock-agentcore:DeleteMemoryRecord",
          "bedrock-agentcore:GetEvent",
          "bedrock-agentcore:GetMemory",
          "bedrock-agentcore:GetMemoryRecord",
          "bedrock-agentcore:ListActors",
          "bedrock-agentcore:ListEvents",
          "bedrock-agentcore:ListMemoryRecords",
          "bedrock-agentcore:ListSessions",
          "bedrock-agentcore:ListTagsForResource",
          "bedrock-agentcore:RetrieveMemoryRecords",
          "bedrock-agentcore:TagResource",
        ]
        Resource = (
          var.agent_memory_arn == "" ?
          [
            "arn:aws:bedrock-agentcore:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:memory/*"
          ] :
          [var.agent_memory_arn]
        )
      }
    ]
  })
}

resource "aws_iam_policy" "config_permissions" {
  name = "${var.role_name}-config-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]
        Resource = [
          "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter/amazon/*",
          "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter/cognito/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:cognito_client_secret*",
          "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:zendesk_credentials*",
          "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:langfuse_credentials*",
          "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:gateway_credentials*",
          "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:tavily_key*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey"
        ]
        Resource = [
          var.secrets_kms_key_arn,
          var.parameters_kms_key_arn
        ]
      }
    ]
  })
}

resource "aws_iam_policy" "bedrock_services_permissions" {
  name = "${var.role_name}-bedrock-services-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:Retrieve",
          "bedrock:RetrieveAndGenerate"
        ]
        Resource = [
          "arn:aws:bedrock:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:knowledge-base/${var.knowledge_base_id}"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:ApplyGuardrail"
        ]
        Resource = [
          "arn:aws:bedrock:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:guardrail/${var.guardrail_id}"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          "arn:aws:bedrock:${data.aws_region.current.name}::foundation-model/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:InvokeGateway",
          "bedrock-agentcore:ListGatewayTargets"
        ]
        Resource = [
          "arn:aws:bedrock-agentcore:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:gateway/*"
        ]
      }
    ]
  })
}
