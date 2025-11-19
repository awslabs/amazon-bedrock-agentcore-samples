# ============================================================================
# Agent2 (Specialist) Runtime - Independent Agent
# ============================================================================

resource "aws_bedrockagentcore_agent_runtime" "agent2" {
  agent_runtime_name = "${replace(var.stack_name, "-", "_")}_${var.agent2_name}"
  description        = "Specialist agent runtime for ${var.stack_name}"
  role_arn           = aws_iam_role.agent2_execution.arn

  agent_runtime_artifact {
    container_configuration {
      container_uri = "${aws_ecr_repository.agent2.repository_url}:${var.image_tag}"
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
    Name        = "${var.stack_name}-agent2-runtime"
    Environment = "production"
    Module      = "BedrockAgentCore"
    Agent       = "Agent2-Specialist"
  }

  depends_on = [
    null_resource.trigger_build_agent2,
    aws_iam_role_policy.agent2_execution,
    aws_iam_role_policy_attachment.agent2_execution_managed
  ]
}
