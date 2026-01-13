data "aws_region" "current" {}

resource "aws_cognito_user_pool" "user_pool" {
  name = var.user_pool_name

  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
    require_uppercase = true
  }

  auto_verified_attributes = ["email"]

  username_attributes = ["email"]

  schema {
    attribute_data_type = "String"
    name               = "email"
    required           = true
    mutable            = true
  }
}

resource "aws_cognito_user_pool_domain" "user_pool_domain" {
  domain       = "${var.user_pool_name}-${random_string.domain_suffix.result}"
  user_pool_id = aws_cognito_user_pool.user_pool.id
}

resource "random_string" "domain_suffix" {
  length  = 8
  special = false
  upper   = false
}

resource "aws_cognito_resource_server" "resource_server" {
  identifier = "gateway-api"
  name       = "Gateway API"
  user_pool_id = aws_cognito_user_pool.user_pool.id

  scope {
    scope_name        = "read"
    scope_description = "Read access to gateway"
  }

  scope {
    scope_name        = "write"
    scope_description = "Write access to gateway"
  }
}

resource "aws_cognito_user_pool_client" "user_pool_client" {
  name         = "${var.user_pool_name}-client"
  user_pool_id = aws_cognito_user_pool.user_pool.id

  generate_secret = true
  
  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH"
  ]

  # Enable OAuth flows
  allowed_oauth_flows = ["client_credentials"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_scopes = [
    "gateway-api/read",
    "gateway-api/write"
  ]
  
  # Configure token validity
  access_token_validity = 1
  token_validity_units {
    access_token = "hours"
  }

  depends_on = [aws_cognito_resource_server.resource_server]
}