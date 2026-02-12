# Container Image Variables
variable "force_image_rebuild" {
  description = "Set true to force rebuild+push of container image even if source seems unchanged"
  default     = false
  type        = bool
}

variable "container_image_build_tool" {
  description = "Either 'docker' or a Docker-compatible alternative e.g. 'finch'"
  default     = "docker"
  type        = string
}

# Bedrock Role Variables
variable "bedrock_role_name" {
  description = "Name of the Bedrock agent role"
  type        = string
}

# Cognito Variables
variable "user_pool_name" {
  description = "Name of the Cognito user pool"
  type        = string
}

# Knowledge Base Stack Variables
variable "kb_stack_name" {
  description = "Name for the knowledge base stack"
  type        = string
}


variable "kb_model_arn" {
  description = "ARN of the embedding model for the knowledge base"
  type        = string
  default     = "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0"
}

# Zendesk Variables
variable "zendesk_domain" {
  description = "Zendesk domain"
  default     = ""
  type        = string
}

variable "zendesk_email" {
  description = "Zendesk email"
  default     = ""
  type        = string
}

variable "zendesk_api_token" {
  description = "Zendesk API token"
  default     = ""
  type        = string
  sensitive   = true
}

# Langfuse Variables
variable "langfuse_host" {
  description = "Langfuse host"
  default     = "https://cloud.langfuse.com"
  type        = string
}

variable "langfuse_public_key" {
  description = "Langfuse public key"
  default     = ""
  type        = string
}

variable "langfuse_secret_key" {
  description = "Langfuse secret key"
  default     = ""
  type        = string
  sensitive   = true
}

# Gateway Variables
variable "gateway_url" {
  description = "Gateway URL"
  type        = string
}

variable "gateway_api_key" {
  description = "Gateway API key"
  type        = string
  sensitive   = true
}

# Tavily Variables
variable "tavily_api_key" {
  description = "Tavily API key"
  default     = ""
  type        = string
  sensitive   = true
}
