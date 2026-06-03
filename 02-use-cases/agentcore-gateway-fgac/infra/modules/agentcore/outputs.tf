output "gateway_id" {
  value       = aws_bedrockagentcore_gateway.this.gateway_id
  description = "AgentCore Gateway ID."
}

output "gateway_arn" {
  value       = aws_bedrockagentcore_gateway.this.gateway_arn
  description = "AgentCore Gateway ARN. Used in Cedar policy `resource ==` clauses."
}

output "gateway_url" {
  value       = aws_bedrockagentcore_gateway.this.gateway_url
  description = "MCP endpoint URL clients connect to."
}

output "gateway_role_arn" {
  value       = aws_iam_role.gateway.arn
  description = "Service role assumed by the Gateway."
}

output "policy_engine_arn" {
  value       = aws_bedrockagentcore_policy_engine.this.policy_engine_arn
  description = "Policy engine ARN. Attach to the gateway out-of-band until Terraform provider supports policyEngineConfiguration."
}

output "policy_engine_id" {
  value       = aws_bedrockagentcore_policy_engine.this.policy_engine_id
  description = "Policy engine ID."
}
