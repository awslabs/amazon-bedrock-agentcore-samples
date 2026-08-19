# ============================================================================
# CodeBuild Project - Build and Push Orchestrator Agent Docker Image
# ============================================================================

resource "aws_codebuild_project" "orchestrator_image" {
  name          = "${var.stack_name}-orchestrator-build"
  description   = "Build Orchestrator agent Docker image for ${var.stack_name}"
  service_role  = aws_iam_role.codebuild.arn
  build_timeout = 60

  artifacts {
    type = "NO_ARTIFACTS"
  }

  environment {
    compute_type                = "BUILD_GENERAL1_LARGE"
    image                       = "aws/codebuild/amazonlinux2-aarch64-standard:3.0"
    type                        = "ARM_CONTAINER"
    privileged_mode             = true
    image_pull_credentials_type = "CODEBUILD"

    environment_variable {
      name  = "AWS_DEFAULT_REGION"
      value = data.aws_region.current.id
    }

    environment_variable {
      name  = "AWS_ACCOUNT_ID"
      value = data.aws_caller_identity.current.id
    }

    environment_variable {
      name  = "IMAGE_REPO_NAME"
      value = aws_ecr_repository.orchestrator.name
    }

    environment_variable {
      name  = "IMAGE_TAG"
      value = var.image_tag
    }

    environment_variable {
      name  = "STACK_NAME"
      value = var.stack_name
    }

    environment_variable {
      name  = "AGENT_NAME"
      value = "orchestrator"
    }
  }

  source {
    type      = "S3"
    location  = "${aws_s3_bucket.orchestrator_source.id}/${aws_s3_object.orchestrator_source.key}"
    buildspec = file("${path.module}/buildspec-orchestrator.yml")
  }

  logs_config {
    cloudwatch_logs {
      group_name = "/aws/codebuild/${var.stack_name}-orchestrator-build"
    }
  }

  tags = {
    Name   = "${var.stack_name}-orchestrator-build"
    Module = "CodeBuild"
    Agent  = "Orchestrator"
  }

  depends_on = [
    aws_iam_role_policy.codebuild
  ]
}

# ============================================================================
# CodeBuild Project - Build and Push Specialist Agent Docker Image
# ============================================================================

resource "aws_codebuild_project" "specialist_image" {
  name          = "${var.stack_name}-specialist-build"
  description   = "Build Specialist agent Docker image for ${var.stack_name}"
  service_role  = aws_iam_role.codebuild.arn
  build_timeout = 60

  artifacts {
    type = "NO_ARTIFACTS"
  }

  environment {
    compute_type                = "BUILD_GENERAL1_LARGE"
    image                       = "aws/codebuild/amazonlinux2-aarch64-standard:3.0"
    type                        = "ARM_CONTAINER"
    privileged_mode             = true
    image_pull_credentials_type = "CODEBUILD"

    environment_variable {
      name  = "AWS_DEFAULT_REGION"
      value = data.aws_region.current.id
    }

    environment_variable {
      name  = "AWS_ACCOUNT_ID"
      value = data.aws_caller_identity.current.id
    }

    environment_variable {
      name  = "IMAGE_REPO_NAME"
      value = aws_ecr_repository.specialist.name
    }

    environment_variable {
      name  = "IMAGE_TAG"
      value = var.image_tag
    }

    environment_variable {
      name  = "STACK_NAME"
      value = var.stack_name
    }

    environment_variable {
      name  = "AGENT_NAME"
      value = "specialist"
    }
  }

  source {
    type      = "S3"
    location  = "${aws_s3_bucket.specialist_source.id}/${aws_s3_object.specialist_source.key}"
    buildspec = file("${path.module}/buildspec-specialist.yml")
  }

  logs_config {
    cloudwatch_logs {
      group_name = "/aws/codebuild/${var.stack_name}-specialist-build"
    }
  }

  tags = {
    Name   = "${var.stack_name}-specialist-build"
    Module = "CodeBuild"
    Agent  = "Specialist"
  }

  depends_on = [
    aws_iam_role_policy.codebuild
  ]
}

# ============================================================================
# Note: Build triggers are defined in main.tf for proper sequencing
# Specialist builds first, then Orchestrator (which depends on Specialist ARN)
# ============================================================================
