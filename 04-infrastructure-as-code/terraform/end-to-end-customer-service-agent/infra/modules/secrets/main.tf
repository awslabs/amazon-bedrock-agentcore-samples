resource "aws_secretsmanager_secret" "cognito_client_secret" {
  name = "cognito_client_secret"
}

resource "aws_secretsmanager_secret_version" "cognito_client_secret" {
  secret_id     = aws_secretsmanager_secret.cognito_client_secret.id
  secret_string = var.cognito_client_secret
}

resource "aws_secretsmanager_secret" "zendesk_credentials" {
  name = "zendesk_credentials"
}

resource "aws_secretsmanager_secret_version" "zendesk_credentials" {
  secret_id = aws_secretsmanager_secret.zendesk_credentials.id
  secret_string = jsonencode({
    zendesk_domain    = var.zendesk_domain
    zendesk_email     = var.zendesk_email
    zendesk_api_token = var.zendesk_api_token
  })
}

resource "aws_secretsmanager_secret" "langfuse_credentials" {
  name = "langfuse_credentials"
}

resource "aws_secretsmanager_secret_version" "langfuse_credentials" {
  secret_id = aws_secretsmanager_secret.langfuse_credentials.id
  secret_string = jsonencode({
    langfuse_host       = var.langfuse_host
    langfuse_public_key = var.langfuse_public_key
    langfuse_secret_key = var.langfuse_secret_key
  })
}

resource "aws_secretsmanager_secret" "gateway_credentials" {
  name = "gateway_credentials"
}

resource "aws_secretsmanager_secret_version" "gateway_credentials" {
  secret_id = aws_secretsmanager_secret.gateway_credentials.id
  secret_string = jsonencode({
    gateway_url = var.gateway_url
    api_key     = var.gateway_api_key
  })
}

resource "aws_secretsmanager_secret" "tavily_key" {
  name = "tavily_key"
}

resource "aws_secretsmanager_secret_version" "tavily_key" {
  secret_id = aws_secretsmanager_secret.tavily_key.id
  secret_string = jsonencode({
    tavily_key = var.tavily_api_key
  })
}