# ECR Repository for Orchestrator
resource "aws_ecr_repository" "orchestrator_repo" {
  name                 = "orchestrator_agent"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "orchestrator-agent-repo"
  }
}

# Build and push orchestrator container to ECR
resource "null_resource" "build_and_push_orchestrator" {
  depends_on = [aws_ecr_repository.orchestrator_repo]

  # Build and push the container
  provisioner "local-exec" {
    command = <<-EOT
      # Get ECR login token
      aws ecr get-login-password --region ${local.region} | docker login --username AWS --password-stdin ${local.account_id}.dkr.ecr.${local.region}.amazonaws.com

      # Build the container for ARM64 (required by AgentCore)
      cd ${path.root}/../agent
      docker build --platform linux/arm64 -f Dockerfile.orchestrator -t orchestrator_agent:latest .

      # Tag for ECR
      docker tag orchestrator_agent:latest ${aws_ecr_repository.orchestrator_repo.repository_url}:latest

      # Push to ECR
      docker push ${aws_ecr_repository.orchestrator_repo.repository_url}:latest
    EOT
  }

  # Rebuild if source files change
  triggers = {
    dockerfile_hash = filemd5("${path.root}/../agent/Dockerfile.orchestrator")
    orchestrator_code_hash = filemd5("${path.root}/../agent/main_agent.py")
    requirements_hash = filemd5("${path.root}/../agent/requirements.txt")
    ecr_repo_url = aws_ecr_repository.orchestrator_repo.repository_url
  }
}

# AgentCore Runtime for Orchestrator
resource "aws_bedrockagentcore_agent_runtime" "orchestrator" {
  agent_runtime_name = "orchestrator_agent"
  description        = "AgentCore runtime for orchestrator agent"
  role_arn          = aws_iam_role.agentcore_runtime_execution_role.arn

  agent_runtime_artifact {
    container_configuration {
      container_uri = "${aws_ecr_repository.orchestrator_repo.repository_url}:latest"
    }
  }

  environment_variables = {
    COGNITO_CONFIG_SECRET_ARN = aws_secretsmanager_secret.cognito_config.arn
    CAMERA_ROLE_ARN          = var.camera_role_arn
    CAMERA_REGION            = var.camera_region
    CLIP_BUCKET              = var.smart_home_bucket_name
    DYNAMO_TABLE             = aws_dynamodb_table.sessions.name
    MEMORY_ID                = aws_bedrockagentcore_memory.orchestrator_memory.id
  }

  network_configuration {
    network_mode = "PUBLIC"
  }

  protocol_configuration {
    server_protocol = "HTTP"
  }

  depends_on = [
    aws_iam_role.agentcore_runtime_execution_role,
    aws_cognito_user_pool_client.orchestrator_client,
    null_resource.build_and_push_orchestrator
  ]

  tags = {
    Name = "orchestrator-agent"
  }
}
