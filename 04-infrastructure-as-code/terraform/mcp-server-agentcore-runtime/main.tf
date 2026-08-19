# ============================================================================
# AgentCore Runtime - Main Agent Runtime Resource
# ============================================================================

resource "aws_bedrockagentcore_agent_runtime" "mcp_server" {
  agent_runtime_name = replace("${var.stack_name}_${var.agent_name}", "-", "_")
  description        = var.description
  role_arn           = aws_iam_role.agent_execution.arn

  agent_runtime_artifact {
    container_configuration {
      container_uri = "${aws_ecr_repository.server_ecr.repository_url}:${var.image_tag}"
    }
  }

  network_configuration {
    network_mode = var.network_mode
  }

  # MCP Protocol Configuration
  protocol_configuration {
    server_protocol = "MCP"
  }

  # JWT Authorization with Cognito
  authorizer_configuration {
    custom_jwt_authorizer {
      allowed_clients = [aws_cognito_user_pool_client.mcp_client.id]
      discovery_url   = "https://cognito-idp.${data.aws_region.current.id}.amazonaws.com/${aws_cognito_user_pool.mcp_user_pool.id}/.well-known/openid-configuration"
    }
  }

  environment_variables = merge(
    {
      AWS_REGION         = var.aws_region
      AWS_DEFAULT_REGION = var.aws_region
    },
    var.environment_variables
  )

  depends_on = [
    null_resource.trigger_build,
    null_resource.set_cognito_password,
    aws_iam_role_policy.agent_execution,
    aws_iam_role_policy_attachment.agent_execution_managed
  ]
}
