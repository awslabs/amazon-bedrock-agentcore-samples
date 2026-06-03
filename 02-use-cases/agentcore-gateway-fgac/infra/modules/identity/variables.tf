variable "name_prefix" {
  type        = string
  description = "Prefix applied to all resource names in this module."
}

variable "okta_issuer" {
  type        = string
  description = "Okta authorization server issuer URL."
}

variable "okta_discovery_url" {
  type        = string
  description = "Okta OIDC discovery URL (issuer + /.well-known/openid-configuration). AgentCore Identity uses this to resolve token / authorization endpoints."
}

variable "okta_client_id" {
  type        = string
  description = "Okta OIDC application client ID. Passed write-only — never stored in Terraform state."
  sensitive   = true
  ephemeral   = true
}

variable "okta_client_secret" {
  type        = string
  description = "Okta OIDC application client secret. Passed write-only — never stored in Terraform state."
  sensitive   = true
  ephemeral   = true
}

variable "okta_client_credentials_version" {
  type        = number
  description = "Bump this number to roll the AgentCore-stored client credentials. Increment after rotating the Okta client secret."
  default     = 1
}

variable "okta_allowed_return_urls" {
  type        = list(string)
  description = "OAuth2 redirect URIs that the AgentCore workload identity will accept (e.g. demo CLI callback URLs)."
  default     = []
}
