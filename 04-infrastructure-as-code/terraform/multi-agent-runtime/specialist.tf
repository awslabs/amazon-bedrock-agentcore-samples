# ============================================================================
# Specialist Agent Runtime - Independent Agent
# ============================================================================

resource "aws_bedrockagentcore_agent_runtime" "specialist" {
  agent_runtime_name = "${replace(var.stack_name, "-", "_")}_${var.specialist_name}"
  description        = "Specialist agent runtime for ${var.stack_name}"
  role_arn           = aws_iam_role.specialist_execution.arn

  agent_runtime_artifact {
    container_configuration {
      container_uri = "${aws_ecr_repository.specialist.repository_url}:${var.image_tag}"
    }
  }

  network_configuration {
    network_mode = var.network_mode
  }

  environment_variables = {
    AWS_REGION         = data.aws_region.current.id
    AWS_DEFAULT_REGION = data.aws_region.current.id
  }

  tags = {
    Name        = "${var.stack_name}-specialist-runtime"
    Environment = "production"
    Module      = "BedrockAgentCore"
    Agent       = "Specialist"
  }

  depends_on = [
    null_resource.trigger_build_specialist,
    aws_iam_role_policy.specialist_execution,
    aws_iam_role_policy_attachment.specialist_execution_managed
  ]
}
