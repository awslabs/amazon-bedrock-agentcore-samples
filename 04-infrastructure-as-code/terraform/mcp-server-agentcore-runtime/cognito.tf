# ============================================================================
# Cognito User Pool for JWT Authentication
# ============================================================================

resource "aws_cognito_user_pool" "mcp_user_pool" {
  name = "${var.stack_name}-user-pool"

  password_policy {
    minimum_length    = 8
    require_uppercase = false
    require_lowercase = false
    require_numbers   = false
    require_symbols   = false
  }

  schema {
    name                = "email"
    attribute_data_type = "String"
    required            = false
    mutable             = true
  }

  tags = {
    Name      = "${var.stack_name}-user-pool"
    StackName = var.stack_name
    Module    = "Cognito"
  }
}

# ============================================================================
# Cognito User Pool Client
# ============================================================================

resource "aws_cognito_user_pool_client" "mcp_client" {
  name         = "${var.stack_name}-client"
  user_pool_id = aws_cognito_user_pool.mcp_user_pool.id

  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH"
  ]

  generate_secret               = false
  prevent_user_existence_errors = "ENABLED"
}

# ============================================================================
# Test User
# ============================================================================

resource "aws_cognito_user" "test_user" {
  user_pool_id = aws_cognito_user_pool.mcp_user_pool.id
  username     = "testuser"

  message_action = "SUPPRESS"
}

# ============================================================================
# Set Permanent Password for Test User
# ============================================================================

resource "null_resource" "set_cognito_password" {
  triggers = {
    user_id = aws_cognito_user.test_user.id
  }

  provisioner "local-exec" {
    command = <<-EOT
      aws cognito-idp admin-set-user-password \
        --user-pool-id ${aws_cognito_user_pool.mcp_user_pool.id} \
        --username testuser \
        --password 'MyPassword123!' \
        --permanent \
        --region ${data.aws_region.current.id}
    EOT
  }

  depends_on = [
    aws_cognito_user.test_user
  ]
}
