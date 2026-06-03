# AgentCore Identity wiring for Okta.
#
# Two resources:
#
# 1. Workload identity: gives AgentCore Gateway and any agents a stable
#    identity in the AgentCore Identity service. Holds the list of OAuth2
#    return URLs that downstream OAuth flows can redirect to.
#
# 2. OAuth2 credential provider (Custom): registers Okta as the OAuth2
#    provider that AgentCore can use for outbound flows on behalf of
#    workload-identity holders. Client credentials are passed write-only
#    (`*_wo` attributes) so they never enter Terraform state.

resource "aws_bedrockagentcore_workload_identity" "this" {
  name = replace("${var.name_prefix}-workload", "-", "_")

  allowed_resource_oauth2_return_urls = var.okta_allowed_return_urls
}

resource "aws_bedrockagentcore_oauth2_credential_provider" "okta" {
  name                       = replace("${var.name_prefix}-okta", "-", "_")
  credential_provider_vendor = "CustomOauth2"

  oauth2_provider_config {
    custom_oauth2_provider_config {
      client_id_wo                  = var.okta_client_id
      client_secret_wo              = var.okta_client_secret
      client_credentials_wo_version = var.okta_client_credentials_version

      oauth_discovery {
        discovery_url = var.okta_discovery_url
      }
    }
  }
}
