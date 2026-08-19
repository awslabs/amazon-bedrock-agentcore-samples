output "knowledge_base_id" {
  description = "ID of the Bedrock Knowledge Base"
  value       = module.knowledge_base.knowledge_base_id
}

output "knowledge_base_arn" {
  description = "ARN of the Bedrock Knowledge Base"
  value       = module.knowledge_base.knowledge_base_arn
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket"
  value       = aws_s3_bucket.kb_bucket.bucket
}

output "data_source_id" {
  description = "ID of the data source"
  value       = module.knowledge_base.data_source_id
}

output "collection_arn" {
  description = "ARN of the OpenSearch Serverless collection"
  value       = module.opensearch.collection_arn
}