# Base IAM policy for all AgentCore runtimes
resource "aws_iam_policy" "agentcore_base_policy" {
  name        = "AgentCoreBasePolicy"
  description = "Base policy for AgentCore runtimes with common permissions"

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
        Resource = ["arn:aws:ecr:${local.region}:${local.account_id}:repository/*"]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:DescribeLogStreams",
          "logs:CreateLogGroup"
        ]
        Resource = [
          "arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"
        ]
      },
      {
        Effect = "Allow"
        Action = ["logs:DescribeLogGroups"]
        Resource = ["arn:aws:logs:${local.region}:${local.account_id}:log-group:*"]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = [
          "arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"
        ]
      },
      {
        Sid      = "ECRTokenAccess"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords",
          "xray:GetSamplingRules",
          "xray:GetSamplingTargets"
        ]
        Resource = ["*"]
      },
      {
        Effect   = "Allow"
        Resource = "*"
        Action   = "cloudwatch:PutMetricData"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "bedrock-agentcore"
          }
        }
      },
      {
        Sid    = "GetAgentAccessToken"
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:GetWorkloadAccessToken",
          "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
          "bedrock-agentcore:GetWorkloadAccessTokenForUserId"
        ]
        Resource = [
          "arn:aws:bedrock-agentcore:${local.region}:${local.account_id}:workload-identity-directory/default",
          "arn:aws:bedrock-agentcore:${local.region}:${local.account_id}:workload-identity-directory/default/workload-identity/customer_support_agent-*"
        ]
      },
      {
        Sid    = "BedrockModelInvocation"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
          "bedrock:ApplyGuardrail",
          "bedrock:Retrieve"
        ]
        Resource = [
          "arn:aws:bedrock:*::foundation-model/*",
          "arn:aws:bedrock:${local.region}:${local.account_id}:*"
        ]
      },
      {
        Sid    = "AllowAgentToUseMemory"
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:CreateEvent",
          "bedrock-agentcore:ListEvents",
          "bedrock-agentcore:GetMemoryRecord",
          "bedrock-agentcore:GetMemory",
          "bedrock-agentcore:RetrieveMemoryRecords",
          "bedrock-agentcore:ListMemoryRecords"
        ]
        Resource = ["arn:aws:bedrock-agentcore:${local.region}:${local.account_id}:*"]
      },
      {
        Sid      = "GetMemoryId"
        Effect   = "Allow"
        Action   = ["ssm:GetParameter"]
        Resource = ["arn:aws:ssm:${local.region}:${local.account_id}:parameter/*"]
      },
      {
        Sid    = "GatewayAccess"
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:GetGateway",
          "bedrock-agentcore:InvokeGateway"
        ]
        Resource = [
          "arn:aws:bedrock-agentcore:${local.region}:${local.account_id}:gateway/*"
        ]
      },
      {
        Sid    = "SecretsManagerAccess"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          "arn:aws:secretsmanager:${local.region}:${local.account_id}:secret:*"
        ]
      }
    ]
  })
}

# Gateway-specific policy for workload identity access
resource "aws_iam_policy" "agentcore_gateway_policy" {
  name        = "AgentCoreGatewayPolicy"
  description = "Gateway-specific policy for workload identity and OAuth token access"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "WorkloadIdentityAccess"
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:GetWorkloadAccessToken",
          "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
          "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
          "bedrock-agentcore:GetResourceOauth2Token"
        ]
        Resource = [
          "arn:aws:bedrock-agentcore:${local.region}:${local.account_id}:token-vault/*",
          "arn:aws:bedrock-agentcore:${local.region}:${local.account_id}:workload-identity-directory/*"
        ]
      }
    ]
  })
}

# MCP-specific policy for Athena, Glue, and S3 access
resource "aws_iam_policy" "agentcore_mcp_policy" {
  name        = "AgentCoreMCPPolicy"
  description = "MCP-specific policy for Athena, Glue, and S3 access"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AthenaAccess"
        Effect = "Allow"
        Action = [
          "athena:StartQueryExecution",
          "athena:GetQueryExecution",
          "athena:GetQueryResults",
          "athena:StopQueryExecution",
          "athena:GetWorkGroup"
        ]
        Resource = [
          "arn:aws:athena:${local.region}:${local.account_id}:workgroup/${var.athena_workgroup}"
        ]
      },
      {
        Sid    = "GlueAccess"
        Effect = "Allow"
        Action = [
          "glue:GetDatabase",
          "glue:GetTable",
          "glue:GetPartitions"
        ]
        Resource = [
          "arn:aws:glue:${local.region}:${local.account_id}:catalog",
          "arn:aws:glue:${local.region}:${local.account_id}:database/${var.athena_database}",
          "arn:aws:glue:${local.region}:${local.account_id}:table/${var.athena_database}/*"
        ]
      },
      {
        Sid    = "AthenaS3Access"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket",
          "s3:PutObject",
          "s3:GetBucketLocation"
        ]
        Resource = [
          "arn:aws:s3:::${var.smart_home_bucket_name}",
          "arn:aws:s3:::${var.smart_home_bucket_name}/*"
        ]
      },
      {
        Sid    = "DynamoDBAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          "${aws_dynamodb_table.sessions.arn}"
        ]
      }
    ]
  })
}

# Camera access policy for cross-account KVS and S3 clip uploads
resource "aws_iam_policy" "agentcore_camera_policy" {
  name        = "AgentCoreCameraPolicy"
  description = "Policy for cross-account camera access and clip generation"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AssumeRoleForCamera"
        Effect = "Allow"
        Action = ["sts:AssumeRole"]
        Resource = "arn:aws:iam::641758013508:role/HasselaCameraExternalAccessRole"
      },
      {
        Sid    = "KinesisVideoAccess"
        Effect = "Allow"
        Action = [
          "kinesisvideo:GetDataEndpoint",
          "kinesisvideo:GetMedia",
          "kinesisvideo:ListStreams",
          "kinesisvideo:DescribeStream"
        ]
        Resource = "*"
      },
      {
        Sid    = "S3ClipUpload"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject"
        ]
        Resource = "arn:aws:s3:::${var.smart_home_bucket_name}/*"
      }
    ]
  })
}
