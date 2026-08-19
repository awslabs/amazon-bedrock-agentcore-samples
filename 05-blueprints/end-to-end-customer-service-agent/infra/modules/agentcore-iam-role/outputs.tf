output "role_arn" {
  description = "ARN of the IAM role"
  value       = aws_iam_role.bedrock_agentcore_role.arn
}

output "role_name" {
  description = "Name of the IAM role"
  value       = aws_iam_role.bedrock_agentcore_role.name
}