variable "name" {
  description = "Name for the knowledge base stack"
  type        = string
}

variable "kb_model_arn" {
  description = "ARN of the embedding model for the knowledge base"
  type        = string
  default     = "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0"
}