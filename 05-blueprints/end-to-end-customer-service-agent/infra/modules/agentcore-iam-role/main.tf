data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

resource "aws_iam_role" "bedrock_agentcore_role" {
  name = var.role_name

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AssumeRolePolicy"
        Effect = "Allow"
        Principal = {
          Service = "bedrock-agentcore.amazonaws.com"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
          ArnLike = {
            "aws:SourceArn" = "arn:aws:bedrock-agentcore:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:*"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "bedrock_permissions" {
  role       = aws_iam_role.bedrock_agentcore_role.name
  policy_arn = aws_iam_policy.bedrock_permissions.arn
}

resource "aws_iam_role_policy_attachment" "ecr_permissions" {
  role       = aws_iam_role.bedrock_agentcore_role.name
  policy_arn = aws_iam_policy.ecr_permissions.arn
}

resource "aws_iam_role_policy_attachment" "logging_permissions" {
  role       = aws_iam_role.bedrock_agentcore_role.name
  policy_arn = aws_iam_policy.logging_permissions.arn
}

resource "aws_iam_role_policy_attachment" "monitoring_permissions" {
  role       = aws_iam_role.bedrock_agentcore_role.name
  policy_arn = aws_iam_policy.monitoring_permissions.arn
}

resource "aws_iam_role_policy_attachment" "agentcore_permissions" {
  role       = aws_iam_role.bedrock_agentcore_role.name
  policy_arn = aws_iam_policy.agentcore_permissions.arn
}

resource "aws_iam_role_policy_attachment" "config_permissions" {
  role       = aws_iam_role.bedrock_agentcore_role.name
  policy_arn = aws_iam_policy.config_permissions.arn
}

resource "aws_iam_role_policy_attachment" "bedrock_services_permissions" {
  role       = aws_iam_role.bedrock_agentcore_role.name
  policy_arn = aws_iam_policy.bedrock_services_permissions.arn
}