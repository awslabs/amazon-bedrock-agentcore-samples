# ============================================================================
# Orchestrator Agent Runtime - Depends on Specialist Agent
# ============================================================================

resource "aws_bedrockagentcore_agent_runtime" "orchestrator" {
  agent_runtime_name = "${replace(var.stack_name, "-", "_")}_${var.orchestrator_name}"
  description        = "Orchestrator agent runtime for ${var.stack_name}"
  role_arn           = aws_iam_role.orchestrator_execution.arn

  agent_runtime_artifact {
    container_configuration {
      container_uri = "${aws_ecr_repository.orchestrator.repository_url}:${var.image_tag}"
    }
  }

  network_configuration {
    network_mode = var.network_mode
  }

  # CRITICAL: Specialist Agent ARN for A2A communication
  environment_variables = {
    AWS_REGION         = data.aws_region.current.id
    AWS_DEFAULT_REGION = data.aws_region.current.id
    SPECIALIST_ARN     = aws_bedrockagentcore_agent_runtime.specialist.agent_runtime_arn
  }

  tags = {
    Name        = "${var.stack_name}-orchestrator-runtime"
    Environment = "production"
    Module      = "BedrockAgentCore"
    Agent       = "Orchestrator"
  }

  # CRITICAL: Must wait for Specialist Agent to be created first
  depends_on = [
    aws_bedrockagentcore_agent_runtime.specialist,
    null_resource.trigger_build_orchestrator,
    aws_iam_role_policy.orchestrator_execution,
    aws_iam_role_policy.orchestrator_invoke_specialist,
    aws_iam_role_policy_attachment.orchestrator_execution_managed
  ]
}
