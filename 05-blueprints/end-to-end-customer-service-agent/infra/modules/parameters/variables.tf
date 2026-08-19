variable "knowledge_base_id" {
  description = "Bedrock Knowledge Base ID"
  type        = string
}

variable "ac_stm_memory_id" {
  description = "Agent core STM memory"
  type        = string
}

variable "guardrail_id" {
  description = "Bedrock Guardrail ID"
  type        = string
}

variable "user_pool_id" {
  description = "Cognito User Pool ID"
  type        = string
}

variable "client_id" {
  description = "Cognito Client ID"
  type        = string
}

variable "gateway_url" {
  description = "Gateway URL for MCP connection"
  type        = string
}

variable "oauth_token_url" {
  description = "OAuth token URL for Cognito client credentials"
  type        = string
}