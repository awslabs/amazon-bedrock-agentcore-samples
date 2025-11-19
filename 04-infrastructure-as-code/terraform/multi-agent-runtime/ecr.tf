# ============================================================================
# ECR Repositories - Container Registries for Agent Images
# ============================================================================

# Agent1 (Orchestrator) ECR Repository
resource "aws_ecr_repository" "agent1" {
  name                 = "${var.stack_name}-${var.ecr_repository_name}-agent1"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  force_delete = true

  tags = {
    Name   = "${var.stack_name}-agent1-ecr-repository"
    Module = "ECR"
    Agent  = "Agent1-Orchestrator"
  }
}

# Agent2 (Specialist) ECR Repository
resource "aws_ecr_repository" "agent2" {
  name                 = "${var.stack_name}-${var.ecr_repository_name}-agent2"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  force_delete = true

  tags = {
    Name   = "${var.stack_name}-agent2-ecr-repository"
    Module = "ECR"
    Agent  = "Agent2-Specialist"
  }
}

# ECR Repository Policy - Agent1
resource "aws_ecr_repository_policy" "agent1" {
  repository = aws_ecr_repository.agent1.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowPullFromAccount"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.id}:root"
        }
        Action = [
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer"
        ]
      }
    ]
  })
}

# ECR Repository Policy - Agent2
resource "aws_ecr_repository_policy" "agent2" {
  repository = aws_ecr_repository.agent2.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowPullFromAccount"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.id}:root"
        }
        Action = [
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer"
        ]
      }
    ]
  })
}

# ECR Lifecycle Policy - Agent1 - Keep last 5 images
resource "aws_ecr_lifecycle_policy" "agent1" {
  repository = aws_ecr_repository.agent1.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 5 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 5
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# ECR Lifecycle Policy - Agent2 - Keep last 5 images
resource "aws_ecr_lifecycle_policy" "agent2" {
  repository = aws_ecr_repository.agent2.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 5 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 5
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
