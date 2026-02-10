# ============================================================================
# Weather Agent Runtime Outputs
# ============================================================================

output "agent_runtime_id" {
  description = "ID of the weather agent runtime"
  value       = aws_bedrockagentcore_agent_runtime.weather_agent.agent_runtime_id
}

output "agent_runtime_arn" {
  description = "ARN of the weather agent runtime"
  value       = aws_bedrockagentcore_agent_runtime.weather_agent.agent_runtime_arn
}

output "agent_runtime_version" {
  description = "Version of the weather agent runtime"
  value       = aws_bedrockagentcore_agent_runtime.weather_agent.agent_runtime_version
}

output "agent_ecr_repository_url" {
  description = "URL of the ECR repository for weather agent"
  value       = aws_ecr_repository.weather_ecr.repository_url
}

output "agent_execution_role_arn" {
  description = "ARN of the weather agent execution role"
  value       = aws_iam_role.agent_execution.arn
}


# ============================================================================
# Build & Storage Outputs
# ============================================================================

output "codebuild_project_name" {
  description = "Name of the CodeBuild project for weather agent"
  value       = aws_codebuild_project.agent_image.name
}

output "source_bucket_name" {
  description = "S3 bucket containing weather agent source code"
  value       = aws_s3_bucket.agent_source.id
}

output "results_bucket_name" {
  description = "Name of the S3 bucket for agent results"
  value       = aws_s3_bucket.results.id
}

output "source_code_md5" {
  description = "MD5 hash of agent source code (triggers rebuild when changed)"
  value       = data.archive_file.agent_source.output_md5
}

# ============================================================================
# Testing Information
# ============================================================================

output "test_agent_command" {
  description = "AWS CLI command to test weather agent"
  value       = "aws bedrock-agentcore invoke-agent-runtime --agent-runtime-arn ${aws_bedrockagentcore_agent_runtime.weather_agent.agent_runtime_arn} --qualifier DEFAULT --payload '{\"prompt\": \"What's the weather like today and suggest activities?\"}' --region ${data.aws_region.current.id} response.json"
}

output "test_script_command" {
  description = "Command to run the comprehensive test script"
  value       = "python test_weather_agent.py ${aws_bedrockagentcore_agent_runtime.weather_agent.agent_runtime_arn}"
}

# ============================================================================
# Tool Resource Outputs
# ============================================================================

output "browser_id" {
  description = "ID of the browser tool"
  value       = aws_bedrockagentcore_browser.browser.browser_id
}

output "browser_arn" {
  description = "ARN of the browser tool"
  value       = aws_bedrockagentcore_browser.browser.browser_arn
}

output "code_interpreter_id" {
  description = "ID of the code interpreter tool"
  value       = aws_bedrockagentcore_code_interpreter.code_interpreter.code_interpreter_id
}

output "code_interpreter_arn" {
  description = "ARN of the code interpreter tool"
  value       = aws_bedrockagentcore_code_interpreter.code_interpreter.code_interpreter_arn
}

output "memory_id" {
  description = "ID of the memory resource"
  value       = aws_bedrockagentcore_memory.memory.id
}

output "memory_arn" {
  description = "ARN of the memory resource"
  value       = aws_bedrockagentcore_memory.memory.arn
}
