output "agentcore_runtime_role_arn" {
  description = "ARN of the AgentCore runtime execution role"
  value       = aws_iam_role.agentcore_runtime_execution_role.arn
}

output "agentcore_runtime_role_name" {
  description = "Name of the AgentCore runtime execution role"
  value       = aws_iam_role.agentcore_runtime_execution_role.name
}

output "cognito_user_pool_id" {
  description = "Cognito User Pool ID"
  value       = aws_cognito_user_pool.smarthome_pool.id
}

output "cognito_client_id" {
  description = "Cognito Client ID"
  value       = aws_cognito_user_pool_client.smarthome_client.id
}

output "cognito_client_secret" {
  description = "Cognito Client Secret"
  value       = aws_cognito_user_pool_client.smarthome_client.client_secret
  sensitive   = true
}

output "cognito_discovery_url" {
  description = "Cognito OIDC Discovery URL"
  value       = "https://cognito-idp.${local.region}.amazonaws.com/${aws_cognito_user_pool.smarthome_pool.id}/.well-known/openid-configuration"
}

output "agentcore_runtime_name" {
  description = "AgentCore runtime name"
  value       = aws_bedrockagentcore_agent_runtime.main.agent_runtime_name
}

output "agentcore_runtime_arn" {
  description = "AgentCore runtime ARN"
  value       = aws_bedrockagentcore_agent_runtime.main.agent_runtime_arn
}

output "agentcore_runtime_id" {
  description = "AgentCore runtime ID"
  value       = aws_bedrockagentcore_agent_runtime.main.agent_runtime_id
}

output "ecr_repository_url" {
  description = "ECR repository URL"
  value       = aws_ecr_repository.agentcore_repo.repository_url
}

output "container_image_uri" {
  description = "Container image URI"
  value       = "${aws_ecr_repository.agentcore_repo.repository_url}:latest"
}

output "cognito_config_secret_arn" {
  description = "ARN of the Cognito configuration secret"
  value       = aws_secretsmanager_secret.cognito_config.arn
}

output "orchestrator_user_pool_id" {
  description = "Orchestrator Cognito User Pool ID"
  value       = aws_cognito_user_pool.orchestrator_pool.id
}

output "orchestrator_client_id" {
  description = "Orchestrator Cognito User Pool Client ID"
  value       = aws_cognito_user_pool_client.orchestrator_client.id
}

output "orchestrator_discovery_url" {
  description = "Orchestrator Cognito OIDC Discovery URL"
  value       = "https://cognito-idp.${local.region}.amazonaws.com/${aws_cognito_user_pool.orchestrator_pool.id}/.well-known/openid-configuration"
}

output "orchestrator_runtime_arn" {
  description = "ARN of the orchestrator AgentCore runtime"
  value       = aws_bedrockagentcore_agent_runtime.orchestrator.agent_runtime_arn
}

output "orchestrator_runtime_id" {
  description = "ID of the orchestrator AgentCore runtime"
  value       = aws_bedrockagentcore_agent_runtime.orchestrator.agent_runtime_id
}

output "orchestrator_ecr_url" {
  description = "ECR repository URL for orchestrator"
  value       = aws_ecr_repository.orchestrator_repo.repository_url
}

output "agentcore_base_policy_arn" {
  description = "ARN of the base AgentCore policy"
  value       = aws_iam_policy.agentcore_base_policy.arn
}

output "agentcore_mcp_policy_arn" {
  description = "ARN of the MCP-specific AgentCore policy"
  value       = aws_iam_policy.agentcore_mcp_policy.arn
}

output "gateway_id" {
  description = "ID of the AgentCore Gateway"
  value       = aws_bedrockagentcore_gateway.mcp_gateway.gateway_id
}

output "gateway_url" {
  description = "URL of the AgentCore Gateway"
  value       = aws_bedrockagentcore_gateway.mcp_gateway.gateway_url
}

output "oauth2_provider_arn" {
  description = "ARN of the OAuth2 credential provider"
  value       = aws_bedrockagentcore_oauth2_credential_provider.cognito_oauth2.credential_provider_arn
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB sessions table"
  value       = aws_dynamodb_table.sessions.name
}

output "dynamodb_table_arn" {
  description = "ARN of the DynamoDB sessions table"
  value       = aws_dynamodb_table.sessions.arn
}

output "memory_id" {
  description = "ID of the orchestrator memory"
  value       = aws_bedrockagentcore_memory.orchestrator_memory.id
}

output "memory_arn" {
  description = "ARN of the orchestrator memory"
  value       = aws_bedrockagentcore_memory.orchestrator_memory.arn
}
