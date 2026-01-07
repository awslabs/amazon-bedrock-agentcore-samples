# KMS key for secrets encryption
resource "aws_kms_key" "secrets_key" {
  description = "KMS key for Secrets Manager encryption"
}

resource "aws_kms_alias" "secrets_key" {
  name          = "alias/secrets-manager"
  target_key_id = aws_kms_key.secrets_key.key_id
}

resource "aws_secretsmanager_secret" "cognito_client_secret" {
  name       = "cognito_client_secret"
  kms_key_id = aws_kms_key.secrets_key.key_id
}

resource "aws_secretsmanager_secret_version" "cognito_client_secret" {
  secret_id     = aws_secretsmanager_secret.cognito_client_secret.id
  secret_string = var.cognito_client_secret
}

resource "aws_secretsmanager_secret_rotation" "cognito_client_secret" {
  secret_id = aws_secretsmanager_secret.cognito_client_secret.id
  
  rotation_rules {
    automatically_after_days = 30
  }
}

resource "aws_secretsmanager_secret" "zendesk_credentials" {
  name       = "zendesk_credentials"
  kms_key_id = aws_kms_key.secrets_key.key_id
}

resource "aws_secretsmanager_secret_version" "zendesk_credentials" {
  secret_id = aws_secretsmanager_secret.zendesk_credentials.id
  secret_string = jsonencode({
    zendesk_domain    = var.zendesk_domain
    zendesk_email     = var.zendesk_email
    zendesk_api_token = var.zendesk_api_token
  })
}

resource "aws_secretsmanager_secret_rotation" "zendesk_credentials" {
  secret_id = aws_secretsmanager_secret.zendesk_credentials.id
  
  rotation_rules {
    automatically_after_days = 90
  }
}

resource "aws_secretsmanager_secret" "langfuse_credentials" {
  name       = "langfuse_credentials"
  kms_key_id = aws_kms_key.secrets_key.key_id
}

resource "aws_secretsmanager_secret_version" "langfuse_credentials" {
  secret_id = aws_secretsmanager_secret.langfuse_credentials.id
  secret_string = jsonencode({
    langfuse_host       = var.langfuse_host
    langfuse_public_key = var.langfuse_public_key
    langfuse_secret_key = var.langfuse_secret_key
  })
}

resource "aws_secretsmanager_secret_rotation" "langfuse_credentials" {
  secret_id = aws_secretsmanager_secret.langfuse_credentials.id
  
  rotation_rules {
    automatically_after_days = 90
  }
}

resource "aws_secretsmanager_secret" "gateway_credentials" {
  name       = "gateway_credentials"
  kms_key_id = aws_kms_key.secrets_key.key_id
}

resource "aws_secretsmanager_secret_version" "gateway_credentials" {
  secret_id = aws_secretsmanager_secret.gateway_credentials.id
  secret_string = jsonencode({
    gateway_url = var.gateway_url
    api_key     = var.gateway_api_key
  })
}

resource "aws_secretsmanager_secret_rotation" "gateway_credentials" {
  secret_id = aws_secretsmanager_secret.gateway_credentials.id
  
  rotation_rules {
    automatically_after_days = 90
  }
}

resource "aws_secretsmanager_secret" "tavily_key" {
  name       = "tavily_key"
  kms_key_id = aws_kms_key.secrets_key.key_id
}

resource "aws_secretsmanager_secret_version" "tavily_key" {
  secret_id = aws_secretsmanager_secret.tavily_key.id
  secret_string = jsonencode({
    tavily_key = var.tavily_api_key
  })
}

resource "aws_secretsmanager_secret_rotation" "tavily_key" {
  secret_id = aws_secretsmanager_secret.tavily_key.id
  
  rotation_rules {
    automatically_after_days = 90
  }
}