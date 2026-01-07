# KMS key for encryption
resource "aws_kms_key" "parameter_key" {
  description = "KMS key for SSM parameters encryption"
}

resource "aws_kms_alias" "parameter_key" {
  name          = "alias/ssm-parameters"
  target_key_id = aws_kms_key.parameter_key.key_id
}

resource "aws_ssm_parameter" "kb_id" {
  name   = "/amazon/kb_id"
  type   = "SecureString"
  value  = var.knowledge_base_id
  key_id = aws_kms_key.parameter_key.key_id
}

resource "aws_ssm_parameter" "ac_stm_memory_id" {
  name   = "/amazon/ac_stm_memory_id"
  type   = "SecureString"
  value  = var.ac_stm_memory_id
  key_id = aws_kms_key.parameter_key.key_id
}

resource "aws_ssm_parameter" "guardrail_id" {
  name   = "/amazon/guardrail_id"
  type   = "SecureString"
  value  = var.guardrail_id
  key_id = aws_kms_key.parameter_key.key_id
}

resource "aws_ssm_parameter" "user_pool_id" {
  name   = "/cognito/user_pool_id"
  type   = "SecureString"
  value  = var.user_pool_id
  key_id = aws_kms_key.parameter_key.key_id
}

resource "aws_ssm_parameter" "client_id" {
  name   = "/cognito/client_id"
  type   = "SecureString"
  value  = var.client_id
  key_id = aws_kms_key.parameter_key.key_id
}

resource "aws_ssm_parameter" "gateway_url" {
  name   = "/amazon/gateway_url"
  type   = "SecureString"
  value  = var.gateway_url
  key_id = aws_kms_key.parameter_key.key_id
}

resource "aws_ssm_parameter" "oauth_token_url" {
  name   = "/cognito/oauth_token_url"
  type   = "SecureString"
  value  = var.oauth_token_url
  key_id = aws_kms_key.parameter_key.key_id
}