variable "kb_name" {
  description = "Name for the knowledge base"
  type        = string
}

variable "bedrock_role_name" {
  description = "Name of the Bedrock IAM role"
  type        = string
}

variable "bedrock_role_arn" {
  description = "ARN of the Bedrock IAM role"
  type        = string
}

variable "opensearch_arn" {
  description = "ARN of the OpenSearch Serverless collection"
  type        = string
}

variable "opensearch_index_name" {
  description = "Name of the OpenSearch index"
  type        = string
}

variable "kb_model_arn" {
  description = "ARN of the embedding model for the knowledge base"
  type        = string
  default     = "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0"
}

variable "s3_arn" {
  description = "ARN of the S3 bucket for data source"
  type        = string
}