resource "aws_ssm_parameter" "kb_id" {
  name  = "/amazon/kb_id"
  type  = "SecureString"
  value = var.knowledge_base_id
}

resource "aws_ssm_parameter" "ac_stm_memory_id" {
  name  = "/amazon/ac_stm_memory_id"
  type  = "SecureString"
  value = var.ac_stm_memory_id
}

resource "aws_ssm_parameter" "guardrail_id" {
  name  = "/amazon/guardrail_id"
  type  = "SecureString"
  value = var.guardrail_id
}

resource "aws_ssm_parameter" "user_pool_id" {
  name  = "/cognito/user_pool_id"
  type  = "SecureString"
  value = var.user_pool_id
}

resource "aws_ssm_parameter" "client_id" {
  name  = "/cognito/client_id"
  type  = "SecureString"
  value = var.client_id
}

resource "aws_ssm_parameter" "gateway_url" {
  name  = "/amazon/gateway_url"
  type  = "SecureString"
  value = var.gateway_url
}

resource "aws_ssm_parameter" "oauth_token_url" {
  name  = "/cognito/oauth_token_url"
  type  = "SecureString"
  value = var.oauth_token_url
}