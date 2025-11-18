# Cognito User Pool for Orchestrator (User Authentication)
resource "aws_cognito_user_pool" "orchestrator_pool" {
  name = "orchestrator-user-pool"

  # Password policy
  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_numbers   = true
    require_symbols   = false
    require_uppercase = true
  }

  # User attributes
  # username_attributes = ["email"]  # Removed to allow normal usernames
  
  # Auto-verified attributes
  auto_verified_attributes = ["email"]

  # Account recovery
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  tags = {
    Name = "orchestrator-user-pool"
  }
}

# Cognito User Pool Client for Orchestrator
resource "aws_cognito_user_pool_client" "orchestrator_client" {
  name         = "orchestrator-client"
  user_pool_id = aws_cognito_user_pool.orchestrator_pool.id

  # Authentication flows
  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_SRP_AUTH"
  ]

  # Token validity
  access_token_validity  = 1  # 1 hour
  id_token_validity     = 1  # 1 hour
  refresh_token_validity = 30 # 30 days

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  # Prevent user existence errors
  prevent_user_existence_errors = "ENABLED"

  # Read and write attributes
  read_attributes = ["email", "name"]
  write_attributes = ["email", "name"]
}

# Create a test user for orchestrator
resource "aws_cognito_user" "orchestrator_test_user" {
  user_pool_id = aws_cognito_user_pool.orchestrator_pool.id
  username     = "testuser"
  
  attributes = {
    email          = "test@example.com"
    email_verified = "true"
  }

  password = "MyPassword123!"
}

# Cognito User Pool for MCP Gateway (Client Credentials)
resource "aws_cognito_user_pool" "smarthome_pool" {
  name = var.user_pool_name

  tags = {
    Name = var.user_pool_name
  }
}

# Cognito User Pool Domain
resource "aws_cognito_user_pool_domain" "smarthome_domain" {
  domain       = replace(lower(aws_cognito_user_pool.smarthome_pool.id), "_", "")
  user_pool_id = aws_cognito_user_pool.smarthome_pool.id
}

# Cognito Resource Server
resource "aws_cognito_resource_server" "smarthome_resource_server" {
  identifier   = var.resource_server_id
  name         = var.resource_server_name
  user_pool_id = aws_cognito_user_pool.smarthome_pool.id

  scope {
    scope_name        = "invoke"
    scope_description = "Scope for invoking the agentcore gateway"
  }
}

# Cognito User Pool Client (M2M)
resource "aws_cognito_user_pool_client" "smarthome_client" {
  name         = var.client_name
  user_pool_id = aws_cognito_user_pool.smarthome_pool.id

  generate_secret = true

  allowed_oauth_flows                  = ["client_credentials"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_scopes                 = ["${var.resource_server_id}/invoke"]
  supported_identity_providers         = ["COGNITO"]

  explicit_auth_flows = ["ALLOW_REFRESH_TOKEN_AUTH"]

  depends_on = [aws_cognito_resource_server.smarthome_resource_server]
}
