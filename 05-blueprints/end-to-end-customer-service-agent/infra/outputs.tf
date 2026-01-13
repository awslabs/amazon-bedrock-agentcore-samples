output "agent_runtime_arn" {
  description = "ARN of deployed AgentCore Runtime"
  value       = aws_bedrockagentcore_agent_runtime.agent_runtime.agent_runtime_arn
}

output "bedrock_role_arn" {
  description = "ARN of the Bedrock agent role"
  value       = module.bedrock_role.role_arn
}

output "knowledge_base_id" {
  description = "ID of the knowledge base"
  value       = module.kb_stack.knowledge_base_id
}

output "guardrail_id" {
  description = "ID of the guardrail"
  value       = module.guardrail.guardrail_id
}

output "user_pool_id" {
  description = "ID of the Cognito user pool"
  value       = module.cognito.user_pool_id
}

output "client_id" {
  description = "ID of the Cognito client"
  value       = module.cognito.user_pool_client_id
}

output "data_source_id" {
  description = "ID of the knowledge base data source"
  value       = module.kb_stack.data_source_id
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket for knowledge base"
  value       = module.kb_stack.s3_bucket_name
}

output "gateway_url" {
  description = "URL of the AgentCore Gateway"
  value       = aws_bedrockagentcore_gateway.cx_gateway.gateway_url
}

output "gateway_id" {
  description = "ID of the AgentCore Gateway"
  value       = aws_bedrockagentcore_gateway.cx_gateway.gateway_id
}

output "oauth_token_url" {
  description = "OAuth token endpoint URL for Cognito"
  value       = module.cognito.oauth_token_url
}

output "client_secret" {
  description = "Cognito client secret"
  value       = module.cognito.client_secret
  sensitive   = true
}

output "user_pool_client_id" {
  description = "Cognito user pool client ID"
  value       = module.cognito.user_pool_client_id
}
