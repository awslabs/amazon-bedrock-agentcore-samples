output "workload_identity_arn" {
  value       = aws_bedrockagentcore_workload_identity.this.workload_identity_arn
  description = "AgentCore workload identity ARN. Reference from runtimes / agents that need to act on behalf of this identity."
}

output "workload_identity_name" {
  value       = aws_bedrockagentcore_workload_identity.this.name
  description = "AgentCore workload identity resource name."
}

output "oauth2_provider_arn" {
  value       = aws_bedrockagentcore_oauth2_credential_provider.okta.credential_provider_arn
  description = "ARN of the Okta OAuth2 credential provider. Pass to gateway / runtime resources that need to mint tokens via Okta."
}

output "oauth2_provider_name" {
  value       = aws_bedrockagentcore_oauth2_credential_provider.okta.name
  description = "Name of the Okta OAuth2 credential provider."
}
