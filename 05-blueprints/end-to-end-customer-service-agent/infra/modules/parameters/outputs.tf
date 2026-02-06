output "kb_id_parameter_name" {
  description = "Name of the knowledge base ID parameter"
  value       = aws_ssm_parameter.kb_id.name
}

output "memory_id_parameter_name" {
  description = "Name of the knowledge base ID parameter"
  value       = aws_ssm_parameter.ac_stm_memory_id.name
}

output "guardrail_id_parameter_name" {
  description = "Name of the guardrail ID parameter"
  value       = aws_ssm_parameter.guardrail_id.name
}

output "user_pool_id_parameter_name" {
  description = "Name of the user pool ID parameter"
  value       = aws_ssm_parameter.user_pool_id.name
}

output "client_id_parameter_name" {
  description = "Name of the client ID parameter"
  value       = aws_ssm_parameter.client_id.name
}

output "kms_key_arn" {
  description = "ARN of the KMS key used for parameters encryption"
  value       = aws_kms_key.parameter_key.arn
}