output "gateway_id" {
  value       = module.agentcore.gateway_id
  description = "AgentCore Gateway ID."
}

output "gateway_arn" {
  value       = module.agentcore.gateway_arn
  description = "AgentCore Gateway ARN."
}

output "gateway_url" {
  value       = module.agentcore.gateway_url
  description = "MCP endpoint URL clients connect to."
}

output "policy_engine_id" {
  value       = module.agentcore.policy_engine_id
  description = "Policy engine ID."
}

output "policy_engine_arn" {
  value       = module.agentcore.policy_engine_arn
  description = "Policy engine ARN."
}

output "oauth2_provider_arn" {
  value       = module.identity.oauth2_provider_arn
  description = "Okta OAuth2 credential provider ARN."
}
