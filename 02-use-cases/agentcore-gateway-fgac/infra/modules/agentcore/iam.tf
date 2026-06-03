data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Service role assumed by AgentCore Gateway when calling AWS APIs and the
# OAuth2 credential provider on outbound target calls.
data "aws_iam_policy_document" "gateway_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["bedrock-agentcore.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "gateway" {
  name               = "${var.name_prefix}-gateway"
  assume_role_policy = data.aws_iam_policy_document.gateway_assume.json
}

# Permissions Gateway needs at runtime:
# - GetWorkloadAccessToken: fetch the agent identity token
# - GetResourceOauth2Token: invoke the credential provider for outbound flows
# - secretsmanager:GetSecretValue: read the OAuth client secret stored by Identity
data "aws_iam_policy_document" "gateway_runtime" {
  statement {
    sid = "AccessTokenVault"
    actions = [
      "bedrock-agentcore:GetWorkloadAccessToken",
      "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
      "bedrock-agentcore:GetResourceOauth2Token",
    ]
    resources = [
      "arn:aws:bedrock-agentcore:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:workload-identity-directory/default",
      "arn:aws:bedrock-agentcore:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:workload-identity-directory/default/workload-identity/*",
      "arn:aws:bedrock-agentcore:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:token-vault/default",
      "arn:aws:bedrock-agentcore:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:token-vault/default/oauth2credentialprovider/*",
    ]
  }

  statement {
    sid       = "ReadOAuthClientSecret"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = ["arn:aws:secretsmanager:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:secret:bedrock-agentcore-identity!default/oauth2/*"]
  }

  # During UpdateGateway --policy-engine-configuration, AgentCore assumes
  # the gateway role (session name GenesisPolicyEngineCheck) and probes
  # GetPolicyEngine on the engine and AuthorizeAction on the gateway —
  # the runtime Cedar evaluation path.
  statement {
    sid       = "ReadPolicyEngine"
    actions   = ["bedrock-agentcore:GetPolicyEngine"]
    resources = [aws_bedrockagentcore_policy_engine.this.policy_engine_arn]
  }

  statement {
    sid = "AuthorizeGatewayActions"
    actions = [
      "bedrock-agentcore:AuthorizeAction",
      "bedrock-agentcore:PartiallyAuthorizeActions",
    ]
    resources = [
      aws_bedrockagentcore_gateway.this.gateway_arn,
      aws_bedrockagentcore_policy_engine.this.policy_engine_arn,
    ]
  }
}

resource "aws_iam_role_policy" "gateway_runtime" {
  name   = "${var.name_prefix}-gateway-runtime"
  role   = aws_iam_role.gateway.id
  policy = data.aws_iam_policy_document.gateway_runtime.json
}
