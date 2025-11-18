# OAuth2 Credential Provider for Gateway
resource "aws_bedrockagentcore_oauth2_credential_provider" "cognito_oauth2" {
  name = "cognito-oauth2-provider"

  credential_provider_vendor = "CustomOauth2"
  oauth2_provider_config {
    custom_oauth2_provider_config {
      client_id     = aws_cognito_user_pool_client.smarthome_client.id
      client_secret = aws_cognito_user_pool_client.smarthome_client.client_secret

      oauth_discovery {
        discovery_url = "https://cognito-idp.${local.region}.amazonaws.com/${aws_cognito_user_pool.smarthome_pool.id}/.well-known/openid-configuration"
      }
    }
  }
}

# Gateway IAM Role
resource "aws_iam_role" "gateway_role" {
  name = "agentcore-gateway-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AssumeRolePolicy"
        Effect = "Allow"
        Principal = {
          Service = "bedrock-agentcore.amazonaws.com"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = local.account_id
          }
          ArnLike = {
            "aws:SourceArn" = "arn:aws:bedrock-agentcore:${local.region}:${local.account_id}:*"
          }
        }
      }
    ]
  })

  tags = {
    Name = "agentcore-gateway-role"
  }
}

# Attach base policy to gateway role
resource "aws_iam_role_policy_attachment" "gateway_base_policy" {
  role       = aws_iam_role.gateway_role.name
  policy_arn = aws_iam_policy.agentcore_base_policy.arn
}

# Attach gateway-specific policy to gateway role
resource "aws_iam_role_policy_attachment" "gateway_specific_policy" {
  role       = aws_iam_role.gateway_role.name
  policy_arn = aws_iam_policy.agentcore_gateway_policy.arn
}

# AgentCore Gateway
resource "aws_bedrockagentcore_gateway" "mcp_gateway" {
  name        = "mcp-gateway"
  description = "Gateway for MCP server access"
  role_arn    = aws_iam_role.gateway_role.arn

  authorizer_type = "CUSTOM_JWT"
  authorizer_configuration {
    custom_jwt_authorizer {
      discovery_url   = "https://cognito-idp.${local.region}.amazonaws.com/${aws_cognito_user_pool.smarthome_pool.id}/.well-known/openid-configuration"
      allowed_clients = [aws_cognito_user_pool_client.smarthome_client.id]
    }
  }

  protocol_type = "MCP"
  protocol_configuration {
    mcp {
      instructions       = "Gateway for accessing MCP server tools"
      search_type        = "SEMANTIC"
      supported_versions = ["2025-03-26"]
    }
  }

  tags = {
    Name = "mcp-gateway"
  }
}

# Gateway Target created via Python script
resource "null_resource" "create_gateway_target" {
  depends_on = [
    aws_bedrockagentcore_gateway.mcp_gateway,
    aws_bedrockagentcore_oauth2_credential_provider.cognito_oauth2,
    aws_bedrockagentcore_agent_runtime.main
  ]

  provisioner "local-exec" {
    command = "python3 create_gateway_target.py create"
  }

  triggers = {
    gateway_id = aws_bedrockagentcore_gateway.mcp_gateway.gateway_id
    runtime_arn = aws_bedrockagentcore_agent_runtime.main.agent_runtime_arn
    oauth2_provider_arn = aws_bedrockagentcore_oauth2_credential_provider.cognito_oauth2.credential_provider_arn
  }
}

# Separate resource for cleanup
resource "null_resource" "cleanup_gateway_target" {
  provisioner "local-exec" {
    when = destroy
    command = "python3 create_gateway_target.py delete"
  }
}
