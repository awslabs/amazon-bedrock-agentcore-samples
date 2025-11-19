# ============================================================================
# Agent1 (Orchestrator) Outputs
# ============================================================================

output "agent1_runtime_id" {
  description = "ID of agent1 (orchestrator) runtime"
  value       = aws_bedrockagentcore_agent_runtime.agent1.agent_runtime_id
}

output "agent1_runtime_arn" {
  description = "ARN of agent1 (orchestrator) runtime"
  value       = aws_bedrockagentcore_agent_runtime.agent1.agent_runtime_arn
}

output "agent1_runtime_version" {
  description = "Version of agent1 runtime"
  value       = aws_bedrockagentcore_agent_runtime.agent1.agent_runtime_version
}

output "agent1_ecr_repository_url" {
  description = "URL of the ECR repository for agent1"
  value       = aws_ecr_repository.agent1.repository_url
}

output "agent1_execution_role_arn" {
  description = "ARN of the agent1 execution role"
  value       = aws_iam_role.agent1_execution.arn
}

# ============================================================================
# Agent2 (Specialist) Outputs
# ============================================================================

output "agent2_runtime_id" {
  description = "ID of agent2 (specialist) runtime"
  value       = aws_bedrockagentcore_agent_runtime.agent2.agent_runtime_id
}

output "agent2_runtime_arn" {
  description = "ARN of agent2 (specialist) runtime"
  value       = aws_bedrockagentcore_agent_runtime.agent2.agent_runtime_arn
}

output "agent2_runtime_version" {
  description = "Version of agent2 runtime"
  value       = aws_bedrockagentcore_agent_runtime.agent2.agent_runtime_version
}

output "agent2_ecr_repository_url" {
  description = "URL of the ECR repository for agent2"
  value       = aws_ecr_repository.agent2.repository_url
}

output "agent2_execution_role_arn" {
  description = "ARN of the agent2 execution role"
  value       = aws_iam_role.agent2_execution.arn
}

# ============================================================================
# Build & Storage Outputs
# ============================================================================

output "agent1_codebuild_project_name" {
  description = "Name of the CodeBuild project for agent1"
  value       = aws_codebuild_project.agent1_image.name
}

output "agent2_codebuild_project_name" {
  description = "Name of the CodeBuild project for agent2"
  value       = aws_codebuild_project.agent2_image.name
}

output "agent1_source_bucket_name" {
  description = "S3 bucket containing agent1 source code"
  value       = aws_s3_bucket.agent1_source.id
}

output "agent2_source_bucket_name" {
  description = "S3 bucket containing agent2 source code"
  value       = aws_s3_bucket.agent2_source.id
}

output "agent1_source_code_md5" {
  description = "MD5 hash of agent1 source code (triggers rebuild when changed)"
  value       = data.archive_file.agent1_source.output_md5
}

output "agent2_source_code_md5" {
  description = "MD5 hash of agent2 source code (triggers rebuild when changed)"
  value       = data.archive_file.agent2_source.output_md5
}

# ============================================================================
# Testing Information
# ============================================================================

output "test_agent1_command" {
  description = "AWS CLI command to test agent1 (orchestrator)"
  value       = "aws bedrock-agentcore invoke-agent-runtime --agent-runtime-id ${aws_bedrockagentcore_agent_runtime.agent1.agent_runtime_id} --qualifier DEFAULT --payload '{\"prompt\": \"Hello, how are you?\"}' --region ${data.aws_region.current.id} response.json"
}

output "test_agent2_command" {
  description = "AWS CLI command to test agent2 (specialist)"
  value       = "aws bedrock-agentcore invoke-agent-runtime --agent-runtime-id ${aws_bedrockagentcore_agent_runtime.agent2.agent_runtime_id} --qualifier DEFAULT --payload '{\"prompt\": \"Explain cloud computing\"}' --region ${data.aws_region.current.id} response.json"
}

output "test_script_command" {
  description = "Command to test multi-agent communication"
  value       = "python test_multi_agent.py ${aws_bedrockagentcore_agent_runtime.agent1.agent_runtime_arn}"
}
