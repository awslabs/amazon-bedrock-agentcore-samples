# ECR Repository for MCP Agent
resource "aws_ecr_repository" "agentcore_repo" {
  name                 = var.agent_name
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = var.agent_name
  }
}

# ECR Repository Policy to allow AgentCore to pull images
resource "aws_ecr_repository_policy" "agentcore_repo_policy" {
  repository = aws_ecr_repository.agentcore_repo.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowAgentCorePull"
        Effect = "Allow"
        Principal = {
          Service = "bedrock-agentcore.amazonaws.com"
        }
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = local.account_id
          }
        }
      }
    ]
  })
}

# Build and push MCP container to ECR
resource "null_resource" "build_and_push_container" {
  depends_on = [aws_ecr_repository.agentcore_repo]

  # Build and push the container
  provisioner "local-exec" {
    command = <<-EOT
      # Get ECR login token
      aws ecr get-login-password --region ${local.region} | docker login --username AWS --password-stdin ${local.account_id}.dkr.ecr.${local.region}.amazonaws.com

      # Build the container for ARM64 (required by AgentCore)
      cd ${path.root}/../agent
      docker build --platform linux/arm64 -t ${var.agent_name}:latest .

      # Tag for ECR
      docker tag ${var.agent_name}:latest ${aws_ecr_repository.agentcore_repo.repository_url}:latest

      # Push to ECR
      docker push ${aws_ecr_repository.agentcore_repo.repository_url}:latest
    EOT
  }

  # Rebuild if source files change
  triggers = {
    dockerfile_hash = filemd5("${path.root}/../agent/Dockerfile")
    agent_code_hash = filemd5("${path.root}/../agent/text_to_sql.py")
    requirements_hash = filemd5("${path.root}/../agent/requirements.txt")
    ecr_repo_url = aws_ecr_repository.agentcore_repo.repository_url
  }
}

# AgentCore Runtime Execution Role
resource "aws_iam_role" "agentcore_runtime_execution_role" {
  name = "agentcore-${var.runtime_name}-role"

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
            "aws:SourceAccount" = local.account_id
          }
          ArnLike = {
            "aws:SourceArn" = "arn:aws:bedrock-agentcore:${local.region}:${local.account_id}:*"
          }
        }
      }
    ]
  })

  tags = {
    Name = "agentcore-${var.runtime_name}-role"
  }
}

# Attach base policy to runtime role
resource "aws_iam_role_policy_attachment" "runtime_base_policy" {
  role       = aws_iam_role.agentcore_runtime_execution_role.name
  policy_arn = aws_iam_policy.agentcore_base_policy.arn
}

# Attach MCP policy to runtime role
resource "aws_iam_role_policy_attachment" "runtime_mcp_policy" {
  role       = aws_iam_role.agentcore_runtime_execution_role.name
  policy_arn = aws_iam_policy.agentcore_mcp_policy.arn
}

# Attach camera policy to runtime role
resource "aws_iam_role_policy_attachment" "runtime_camera_policy" {
  role       = aws_iam_role.agentcore_runtime_execution_role.name
  policy_arn = aws_iam_policy.agentcore_camera_policy.arn
}

# AgentCore Agent Runtime
resource "aws_bedrockagentcore_agent_runtime" "main" {
  agent_runtime_name = var.agent_name
  description        = "AgentCore runtime for ${var.agent_name}"
  role_arn          = aws_iam_role.agentcore_runtime_execution_role.arn

  agent_runtime_artifact {
    container_configuration {
      container_uri = "${aws_ecr_repository.agentcore_repo.repository_url}:latest"
    }
  }

  environment_variables = {
    ATHENA_DB         = var.athena_database
    ATHENA_WORK_GROUP = var.athena_workgroup
    S3_BUCKET_NAME    = var.smart_home_bucket_name
    AWS_REGION        = local.region
  }

  authorizer_configuration {
    custom_jwt_authorizer {
      discovery_url   = "https://cognito-idp.${local.region}.amazonaws.com/${aws_cognito_user_pool.smarthome_pool.id}/.well-known/openid-configuration"
      allowed_clients = [aws_cognito_user_pool_client.smarthome_client.id]
    }
  }

  network_configuration {
    network_mode = "PUBLIC"
  }

  protocol_configuration {
    server_protocol = "MCP"
  }

  depends_on = [
    aws_iam_role.agentcore_runtime_execution_role,
    aws_cognito_user_pool_client.smarthome_client,
    null_resource.build_and_push_container
  ]

  tags = {
    Name = var.agent_name
  }
}
