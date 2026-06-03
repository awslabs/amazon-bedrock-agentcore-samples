locals {
  name_prefix = "${var.project_name}-dev"
}

# Read the platform stack's outputs (ALB DNS, etc).
data "terraform_remote_state" "platform" {
  backend = "local"

  config = {
    path = var.platform_state_path
  }
}

module "identity" {
  source = "../../../modules/identity"

  name_prefix                     = local.name_prefix
  okta_issuer                     = var.okta_issuer
  okta_discovery_url              = "${var.okta_issuer}/.well-known/openid-configuration"
  okta_client_id                  = var.okta_client_id
  okta_client_secret              = var.okta_client_secret
  okta_client_credentials_version = var.okta_client_credentials_version
  okta_allowed_return_urls        = var.okta_allowed_return_urls
}

module "agentcore" {
  source = "../../../modules/agentcore"

  name_prefix              = local.name_prefix
  alb_fqdn                 = data.terraform_remote_state.platform.outputs.alb_fqdn
  okta_discovery_url       = "${var.okta_issuer}/.well-known/openid-configuration"
  okta_audience            = var.okta_audience
  okta_allowed_clients     = var.okta_allowed_client_ids
  okta_oauth2_provider_arn = module.identity.oauth2_provider_arn
  openapi_schema_path      = var.openapi_schema_path
  policy_engine_mode       = var.policy_engine_mode
}
