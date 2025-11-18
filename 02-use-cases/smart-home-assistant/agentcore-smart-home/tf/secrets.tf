# AWS Secrets Manager secret for Cognito configuration
resource "aws_secretsmanager_secret" "cognito_config" {
  name                    = "agentcore/cognito-mcp-config"
  description             = "Cognito configuration for AgentCore MCP access"
  recovery_window_in_days = 0

  tags = {
    Name = "agentcore-cognito-config"
  }
}

# Store Cognito configuration in the secret
resource "aws_secretsmanager_secret_version" "cognito_config" {
  secret_id = aws_secretsmanager_secret.cognito_config.id
  secret_string = jsonencode({
    user_pool_id    = aws_cognito_user_pool.smarthome_pool.id
    client_id       = aws_cognito_user_pool_client.smarthome_client.id
    client_secret   = aws_cognito_user_pool_client.smarthome_client.client_secret
    discovery_url   = "https://cognito-idp.${local.region}.amazonaws.com/${aws_cognito_user_pool.smarthome_pool.id}/.well-known/openid-configuration"
    scope_string    = "smarthome-agentcore-runtime-id/invoke"
    region          = local.region
    mcp_server_url  = "https://${aws_bedrockagentcore_gateway.mcp_gateway.gateway_id}.gateway.bedrock-agentcore.${local.region}.amazonaws.com/mcp"
  })
}
