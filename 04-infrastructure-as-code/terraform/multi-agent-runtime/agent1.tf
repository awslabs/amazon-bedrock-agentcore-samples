# ============================================================================
# Agent1 (Orchestrator) Runtime - Depends on Agent2
# ============================================================================

resource "aws_bedrockagentcore_agent_runtime" "agent1" {
  agent_runtime_name = "${replace(var.stack_name, "-", "_")}_${var.agent1_name}"
  description        = "Orchestrator agent runtime for ${var.stack_name}"
  role_arn           = aws_iam_role.agent1_execution.arn

  agent_runtime_artifact {
    container_configuration {
      container_uri = "${aws_ecr_repository.agent1.repository_url}:${var.image_tag}"
    }
  }

  network_configuration {
    network_mode = var.network_mode
  }

  # CRITICAL: Agent2 ARN for A2A communication
  environment_variables = {
    AWS_REGION         = data.aws_region.current.id
    AWS_DEFAULT_REGION = data.aws_region.current.id
    AGENT2_ARN         = aws_bedrockagentcore_agent_runtime.agent2.agent_runtime_arn
  }

  tags = {
    Name        = "${var.stack_name}-agent1-runtime"
    Environment = "production"
    Module      = "BedrockAgentCore"
    Agent       = "Agent1-Orchestrator"
  }

  # CRITICAL: Must wait for Agent2 to be created first
  depends_on = [
    aws_bedrockagentcore_agent_runtime.agent2,
    null_resource.trigger_build_agent1,
    aws_iam_role_policy.agent1_execution,
    aws_iam_role_policy.agent1_invoke_agent2,
    aws_iam_role_policy_attachment.agent1_execution_managed
  ]
}
