# ============================================================================
# ECR Repositories - Container Registries for Agent Images
# ============================================================================

# Orchestrator Agent ECR Repository
resource "aws_ecr_repository" "orchestrator" {
  name                 = "${var.stack_name}-${var.ecr_repository_name}-orchestrator"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  force_delete = true

  tags = {
    Name   = "${var.stack_name}-orchestrator-ecr-repository"
    Module = "ECR"
    Agent  = "Orchestrator"
  }
}

# Specialist Agent ECR Repository
resource "aws_ecr_repository" "specialist" {
  name                 = "${var.stack_name}-${var.ecr_repository_name}-specialist"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  force_delete = true

  tags = {
    Name   = "${var.stack_name}-specialist-ecr-repository"
    Module = "ECR"
    Agent  = "Specialist"
  }
}

# ECR Repository Policy - Orchestrator
resource "aws_ecr_repository_policy" "orchestrator" {
  repository = aws_ecr_repository.orchestrator.name

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

# ECR Repository Policy - Specialist
resource "aws_ecr_repository_policy" "specialist" {
  repository = aws_ecr_repository.specialist.name

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

# ECR Lifecycle Policy - Orchestrator - Keep last 5 images
resource "aws_ecr_lifecycle_policy" "orchestrator" {
  repository = aws_ecr_repository.orchestrator.name

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

# ECR Lifecycle Policy - Specialist - Keep last 5 images
resource "aws_ecr_lifecycle_policy" "specialist" {
  repository = aws_ecr_repository.specialist.name

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
