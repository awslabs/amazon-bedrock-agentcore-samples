variable "role_name" {
  description = "Name of the IAM role"
  type        = string
}

variable "container_repository_arn" {
  description = "ARN of specific Amazon ECR repository to grant access (default: all)"
  default     = ""
  type        = string
}

variable "knowledge_base_id" {
  description = "Knowledge Base ID to restrict access to"
  type        = string
  default     = "*"
}

variable "guardrail_id" {
  description = "Guardrail ID to restrict access to"
  type        = string
  default     = "*"
}

variable "agent_memory_arn" {
  description = "ARN of specific AgentCore Memory to grant access (default: all)"
  default     = ""
  type        = string
}

variable "secrets_kms_key_arn" {
  description = "ARN of the KMS key used to encrypt secrets"
  type        = string
}

variable "parameters_kms_key_arn" {
  description = "ARN of the KMS key used to encrypt parameters"
  type        = string
}