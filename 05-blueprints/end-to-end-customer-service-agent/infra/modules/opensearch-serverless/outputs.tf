output "collection_arn" {
  description = "ARN of the OpenSearch Serverless collection"
  value       = awscc_opensearchserverless_collection.os_collection.arn
}

output "collection_endpoint" {
  description = "Endpoint of the OpenSearch Serverless collection"
  value       = awscc_opensearchserverless_collection.os_collection.collection_endpoint
}

output "collection_name" {
  description = "Name of the OpenSearch Serverless collection"
  value       = awscc_opensearchserverless_collection.os_collection.name
}