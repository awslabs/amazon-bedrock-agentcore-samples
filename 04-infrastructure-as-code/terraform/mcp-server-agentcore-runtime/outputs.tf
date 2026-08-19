output "agent_runtime_id" {
  description = "ID of the created agent runtime"
  value       = aws_bedrockagentcore_agent_runtime.mcp_server.agent_runtime_id
}

output "agent_runtime_arn" {
  description = "ARN of the created agent runtime"
  value       = aws_bedrockagentcore_agent_runtime.mcp_server.agent_runtime_arn
}

output "agent_runtime_version" {
  description = "Version of the created agent runtime"
  value       = aws_bedrockagentcore_agent_runtime.mcp_server.agent_runtime_version
}

output "ecr_repository_url" {
  description = "URL of the ECR repository"
  value       = aws_ecr_repository.server_ecr.repository_url
}

output "ecr_repository_arn" {
  description = "ARN of the ECR repository"
  value       = aws_ecr_repository.server_ecr.arn
}

output "agent_execution_role_arn" {
  description = "ARN of the agent execution role"
  value       = aws_iam_role.agent_execution.arn
}

output "codebuild_project_name" {
  description = "Name of the CodeBuild project"
  value       = aws_codebuild_project.agent_image.name
}

output "codebuild_project_arn" {
  description = "ARN of the CodeBuild project"
  value       = aws_codebuild_project.agent_image.arn
}

output "source_bucket_name" {
  description = "S3 bucket containing agent source code"
  value       = aws_s3_bucket.agent_source.id
}

output "source_bucket_arn" {
  description = "ARN of the S3 bucket containing agent source code"
  value       = aws_s3_bucket.agent_source.arn
}

output "source_object_key" {
  description = "S3 object key for the agent source code archive"
  value       = aws_s3_object.agent_source.key
}

output "source_code_md5" {
  description = "MD5 hash of the agent source code (triggers rebuild when changed)"
  value       = data.archive_file.agent_source.output_md5
}

# ============================================================================
# Cognito Outputs
# ============================================================================

output "cognito_user_pool_id" {
  description = "ID of the Cognito User Pool"
  value       = aws_cognito_user_pool.mcp_user_pool.id
}

output "cognito_user_pool_arn" {
  description = "ARN of the Cognito User Pool"
  value       = aws_cognito_user_pool.mcp_user_pool.arn
}

output "cognito_user_pool_client_id" {
  description = "ID of the Cognito User Pool Client"
  value       = aws_cognito_user_pool_client.mcp_client.id
}

output "cognito_discovery_url" {
  description = "Cognito OIDC Discovery URL"
  value       = "https://cognito-idp.${data.aws_region.current.id}.amazonaws.com/${aws_cognito_user_pool.mcp_user_pool.id}/.well-known/openid-configuration"
}

output "test_username" {
  description = "Test username for authentication"
  value       = "testuser"
}

output "test_password" {
  description = "Test password for authentication"
  value       = "MyPassword123!"
  sensitive   = true
}

output "get_token_command" {
  description = "Command to get authentication token"
  value       = "python get_token.py ${aws_cognito_user_pool_client.mcp_client.id} testuser MyPassword123! ${data.aws_region.current.id}"
}
