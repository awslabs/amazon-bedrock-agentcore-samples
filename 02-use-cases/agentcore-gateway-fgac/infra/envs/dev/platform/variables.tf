variable "aws_region" {
  type        = string
  description = "AWS region to deploy into."
  default     = "ap-southeast-1"
}

variable "project_name" {
  type        = string
  description = "Short project identifier used as a name prefix."
  default     = "agentcore-ecommerce"
}

# --- Okta -----------------------------------------------------------------
# These values come from your Okta tenant. See README "Setting up Okta".

variable "okta_issuer" {
  type        = string
  description = "Okta authorization server issuer URL."
}

variable "okta_audience" {
  type        = string
  description = "Audience expected on Okta-issued access tokens."
  default     = "agentcore-ecommerce"
}

variable "okta_jwks_uri" {
  type        = string
  description = "Okta JWKS endpoint URL. The ALB fetches keys from here to verify inbound JWT signatures."
}

# --- DNS / TLS ------------------------------------------------------------

variable "route53_zone_id" {
  type        = string
  description = "Route53 hosted zone ID where the ALB's DNS-validated ACM cert and alias record are created."
}

variable "alb_fqdn" {
  type        = string
  description = "Fully-qualified domain name to point at the ALB (e.g. alb.demo.example.com). Must sit under the zone identified by route53_zone_id."
}

# --- ALB / network --------------------------------------------------------

variable "alb_internet_facing" {
  type        = bool
  description = "When true, expose the ALB to the public internet for JWT integration testing. Set false for production-shaped fully-private ALB."
  default     = true
}

variable "alb_ingress_cidrs" {
  type        = list(string)
  description = "CIDRs allowed to reach the public ALB on 443. Set to your own IP (/32) for the demo. Use [] to block all ingress. Required when alb_internet_facing = true."
}

# --- App container --------------------------------------------------------

variable "container_image" {
  type        = string
  description = "Full image URI for the application container. Leave empty until the first push; the ECS service holds at desired_count = 0 until set."
  default     = ""
}
