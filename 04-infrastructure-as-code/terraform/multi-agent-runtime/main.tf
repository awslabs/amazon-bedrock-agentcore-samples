# ============================================================================
# Wait for IAM propagation before triggering builds
# ============================================================================

resource "time_sleep" "wait_for_iam" {
  depends_on = [
    aws_iam_role_policy.codebuild,
    aws_iam_role_policy.agent1_execution,
    aws_iam_role_policy.agent2_execution
  ]

  create_duration = "30s"
}

# ============================================================================
# Trigger CodeBuild - Sequential Build Process
# Agent2 builds first (independent), then Agent1 (depends on Agent2)
# ============================================================================

# Trigger Agent2 Build (Independent - Builds First)
resource "null_resource" "trigger_build_agent2" {
  triggers = {
    build_project   = aws_codebuild_project.agent2_image.id
    image_tag       = var.image_tag
    ecr_repository  = aws_ecr_repository.agent2.id
    source_code_md5 = data.archive_file.agent2_source.output_md5
  }

  provisioner "local-exec" {
    command = "${path.module}/scripts/build-image.sh \"${aws_codebuild_project.agent2_image.name}\" \"${data.aws_region.current.id}\" \"${aws_ecr_repository.agent2.name}\" \"${var.image_tag}\" \"${aws_ecr_repository.agent2.repository_url}\""
  }

  depends_on = [
    aws_codebuild_project.agent2_image,
    aws_ecr_repository.agent2,
    aws_iam_role_policy.codebuild,
    aws_s3_object.agent2_source,
    time_sleep.wait_for_iam
  ]
}

# Trigger Agent1 Build (Depends on Agent2 Build Completion)
resource "null_resource" "trigger_build_agent1" {
  triggers = {
    build_project   = aws_codebuild_project.agent1_image.id
    image_tag       = var.image_tag
    ecr_repository  = aws_ecr_repository.agent1.id
    source_code_md5 = data.archive_file.agent1_source.output_md5
    # Also rebuild if Agent2 build changes
    agent2_build = null_resource.trigger_build_agent2.id
  }

  provisioner "local-exec" {
    command = "${path.module}/scripts/build-image.sh \"${aws_codebuild_project.agent1_image.name}\" \"${data.aws_region.current.id}\" \"${aws_ecr_repository.agent1.name}\" \"${var.image_tag}\" \"${aws_ecr_repository.agent1.repository_url}\""
  }

  depends_on = [
    aws_codebuild_project.agent1_image,
    aws_ecr_repository.agent1,
    aws_iam_role_policy.codebuild,
    aws_s3_object.agent1_source,
    null_resource.trigger_build_agent2,  # CRITICAL: Wait for Agent2 build
    time_sleep.wait_for_iam
  ]
}
