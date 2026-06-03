# AgentCore Gateway with:
#   - Inbound:  customJWTAuthorizer against Okta (validates iss/aud/clients/role).
#   - Outbound: single openApiSchema target pointing at the internal ALB,
#               using OAuth TOKEN_EXCHANGE to swap the inbound user JWT for
#               a target-scoped access token via Okta. The exchanged token
#               carries the same Okta-issued claims (incl. `role`), which
#               the ALB jwt-validation action then verifies.
#
# Notes on what is NOT in Terraform yet (provider gaps):
#   - Attaching the Policy engine to the Gateway requires an UpdateGateway
#     call with `policyEngineConfiguration`, which the v6 provider does not
#     surface. We provision the engine; attaching is a CLI shim — see
#     `scripts/attach_policy_engine.sh`.
#   - Cedar policy text creation has no Terraform resource yet
#     (`aws_bedrockagentcore_policy` does not exist). Same shim story.

resource "aws_bedrockagentcore_gateway" "this" {
  name          = "${var.name_prefix}-gateway"
  protocol_type = "MCP"
  role_arn      = aws_iam_role.gateway.arn

  authorizer_type = "CUSTOM_JWT"

  authorizer_configuration {
    custom_jwt_authorizer {
      discovery_url    = var.okta_discovery_url
      allowed_audience = [var.okta_audience]
      allowed_clients  = var.okta_allowed_clients
    }
  }

  protocol_configuration {
    mcp {
      search_type = "SEMANTIC"
    }
  }
}

locals {
  # AgentCore requires a non-empty HTTPS `servers` entry on the OpenAPI
  # spec; the app-side spec is environment-agnostic, so we splice in the
  # ALB FQDN here from the platform stack output. Must be the public
  # FQDN (not the *.elb.amazonaws.com name) so the ACM cert validates
  # when AgentCore Gateway calls in.
  openapi_payload = jsonencode(merge(
    jsondecode(file(var.openapi_schema_path)),
    { servers = [{ url = "https://${var.alb_fqdn}" }] },
  ))
}

resource "aws_bedrockagentcore_gateway_target" "ecommerce" {
  gateway_identifier = aws_bedrockagentcore_gateway.this.gateway_id
  name               = "ecommerce-tools"
  description        = "All eCommerce API operations. Per-role authorization is enforced by AgentCore Policy on tools/call."

  target_configuration {
    mcp {
      open_api_schema {
        inline_payload {
          payload = local.openapi_payload
        }
      }
    }
  }

  credential_provider_configuration {
    oauth {
      provider_arn = var.okta_oauth2_provider_arn
      grant_type   = "TOKEN_EXCHANGE"
      # Okta rejects token-exchange requests that include `openid` in the
      # scope list (`openid_not_allowed_token_exchange`). Use a custom
      # scope defined on the `agentcore-demo` authz server instead.
      scopes = ["gateway.invoke"]

      custom_parameters = {
        # Okta requires `audience` on token-exchange so the new token is
        # scoped at the backend resource server (matches the ALB
        # jwt-validation `aud` check).
        audience           = var.okta_audience
        subject_token_type = "urn:ietf:params:oauth:token-type:access_token"
      }
    }
  }
}

# Cedar Policy engine. Create here so the engine ARN is declarative; the
# actual Cedar policy statements and the engine-to-gateway attachment are
# provisioned out-of-band until the Terraform provider catches up.
#
# Random suffix on the name avoids collisions with tombstoned engines from
# the AgentCore deletion bug (Delete returns success but the name stays
# reserved server-side). Suffix is generated once on first apply and
# persisted in state; it only rolls if `name_prefix` changes (which would
# already replace the engine anyway, since Name is immutable).
resource "random_id" "policy_engine_suffix" {
  byte_length = 4
  keepers = {
    name_prefix = var.name_prefix
  }
}

resource "aws_bedrockagentcore_policy_engine" "this" {
  name        = replace("${var.name_prefix}-policies-${random_id.policy_engine_suffix.hex}", "-", "_")
  description = "Per-tool authorization policies for the eCommerce gateway."
}
