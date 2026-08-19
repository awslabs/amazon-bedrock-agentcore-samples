output "knowledge_base_id" {
  description = "The ID of the Bedrock Agent Knowledge Base"
  value       = aws_bedrockagent_knowledge_base.sample_kb.id
}

output "knowledge_base_arn" {
  description = "The ARN of the Bedrock Agent Knowledge Base"
  value       = aws_bedrockagent_knowledge_base.sample_kb.arn
}

output "data_source_id" {
  description = "The ID of the data source"
  value       = aws_bedrockagent_data_source.sample_kb.data_source_id
}