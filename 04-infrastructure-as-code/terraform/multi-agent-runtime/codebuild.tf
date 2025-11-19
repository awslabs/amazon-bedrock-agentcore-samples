# ============================================================================
# CodeBuild Project - Build and Push Agent1 (Orchestrator) Docker Image
# ============================================================================

resource "aws_codebuild_project" "agent1_image" {
  name          = "${var.stack_name}-agent1-build"
  description   = "Build Agent1 (Orchestrator) Docker image for ${var.stack_name}"
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
      value = aws_ecr_repository.agent1.name
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
      value = "agent1"
    }
  }

  source {
    type      = "S3"
    location  = "${aws_s3_bucket.agent1_source.id}/${aws_s3_object.agent1_source.key}"
    buildspec = file("${path.module}/buildspec-agent1.yml")
  }

  logs_config {
    cloudwatch_logs {
      group_name = "/aws/codebuild/${var.stack_name}-agent1-build"
    }
  }

  tags = {
    Name   = "${var.stack_name}-agent1-build"
    Module = "CodeBuild"
    Agent  = "Agent1-Orchestrator"
  }

  depends_on = [
    aws_iam_role_policy.codebuild
  ]
}

# ============================================================================
# CodeBuild Project - Build and Push Agent2 (Specialist) Docker Image
# ============================================================================

resource "aws_codebuild_project" "agent2_image" {
  name          = "${var.stack_name}-agent2-build"
  description   = "Build Agent2 (Specialist) Docker image for ${var.stack_name}"
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
      value = aws_ecr_repository.agent2.name
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
      value = "agent2"
    }
  }

  source {
    type      = "S3"
    location  = "${aws_s3_bucket.agent2_source.id}/${aws_s3_object.agent2_source.key}"
    buildspec = file("${path.module}/buildspec-agent2.yml")
  }

  logs_config {
    cloudwatch_logs {
      group_name = "/aws/codebuild/${var.stack_name}-agent2-build"
    }
  }

  tags = {
    Name   = "${var.stack_name}-agent2-build"
    Module = "CodeBuild"
    Agent  = "Agent2-Specialist"
  }

  depends_on = [
    aws_iam_role_policy.codebuild
  ]
}
