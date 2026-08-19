# ============================================================================
# ECR Repository - Container Registry for Weather Agent Image
# ============================================================================

# Weather Agent ECR Repository
resource "aws_ecr_repository" "weather_ecr" {
  name                 = "${var.stack_name}-${var.ecr_repository_name}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  force_delete = true

  tags = {
    Name   = "${var.stack_name}-agent-ecr-repository"
    Module = "ECR"
    Agent  = "WeatherAgent"
  }
}

# ECR Repository Policy - Weather Agent
resource "aws_ecr_repository_policy" "weather_ecr" {
  repository = aws_ecr_repository.weather_ecr.name

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

# ECR Lifecycle Policy - Weather Agent - Keep last 5 images
resource "aws_ecr_lifecycle_policy" "weather_ecr" {
  repository = aws_ecr_repository.weather_ecr.name

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
