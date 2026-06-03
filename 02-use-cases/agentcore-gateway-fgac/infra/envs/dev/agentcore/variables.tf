variable "aws_region" {
  type        = string
  description = "AWS region."
  default     = "ap-southeast-1"
}

variable "project_name" {
  type        = string
  description = "Short project identifier used as a name prefix. Must match the platform stack."
  default     = "agentcore-ecommerce"
}

variable "platform_state_path" {
  type        = string
  description = "Filesystem path to the platform stack's terraform.tfstate. Default points at the sibling platform directory."
  default     = "../platform/terraform.tfstate"
}

# --- Okta -----------------------------------------------------------------

variable "okta_issuer" {
  type        = string
  description = "Okta authorization server issuer URL."
}

variable "okta_audience" {
  type        = string
  description = "Audience expected on Okta-issued tokens."
  default     = "agentcore-ecommerce"
}

variable "okta_allowed_client_ids" {
  type        = list(string)
  description = "Okta client IDs allowed by the Gateway customJWTAuthorizer."
}

variable "okta_client_id" {
  type        = string
  description = "Okta OIDC application client ID."
  sensitive   = true
}

variable "okta_client_secret" {
  type        = string
  description = "Okta OIDC application client secret. Marked ephemeral — never enters Terraform state."
  sensitive   = true
  ephemeral   = true
}

variable "okta_client_credentials_version" {
  type        = number
  description = "Bump after rotating the Okta client secret to force AgentCore to re-store it."
  default     = 1
}

variable "okta_allowed_return_urls" {
  type        = list(string)
  description = "OAuth2 redirect URIs accepted by the AgentCore workload identity."
  default     = []
}

# --- AgentCore -----------------------------------------------------------

variable "openapi_schema_path" {
  type        = string
  description = "Path to the OpenAPI 3.1 spec for the eCommerce API."
  default     = "../../../../openapi.json"
}

variable "policy_engine_mode" {
  type        = string
  description = "AgentCore Policy enforcement mode: LOG_ONLY or ENFORCE."
  default     = "LOG_ONLY"
}
