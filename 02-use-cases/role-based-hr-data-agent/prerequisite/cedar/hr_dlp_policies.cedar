// HR DLP Gateway — Cedar Authorization Policies
//
// These policies enforce OAuth scope-based authorization on each HR tool.
// Attach this policy set to your AgentCore Gateway via the AWS Console or CLI.
//
// Scope format issued by Amazon Cognito: hr-dlp-gateway/<scope>
//   hr-dlp-gateway/read    — basic employee search
//   hr-dlp-gateway/pii     — PII access (email, phone)
//   hr-dlp-gateway/address — address data access
//   hr-dlp-gateway/comp    — compensation data access
//
// Mode: LOG_ONLY (testing) | ENFORCE (production)
// Switch with: scripts/utils/switch_policy_mode.py
//
// IMPORTANT: Before attaching these policies, replace <YOUR-ACCOUNT-ID> and
// <YOUR-GATEWAY-ID> in each policy resource ARN with your actual values.
// The Gateway ARN is stored in SSM at /app/hrdlp/gateway-arn after running
// scripts/agentcore_gateway.py create.

// ---------------------------------------------------------------------------
// Policy 1: Employee Search
// Required scope: hr-dlp-gateway/read
// ---------------------------------------------------------------------------
permit(
  principal is AgentCore::OAuthUser,
  action == AgentCore::Action::"hr-lambda-target___search_employee",
  resource == AgentCore::Gateway::"arn:aws:bedrock-agentcore:us-east-1:<YOUR-ACCOUNT-ID>:gateway/<YOUR-GATEWAY-ID>"
)
when {
  principal.hasTag("scope") &&
  principal.getTag("scope") like "*hr-dlp-gateway/read*"
};

// ---------------------------------------------------------------------------
// Policy 2: Employee Profile
// Required scope: hr-dlp-gateway/read  (PII/address redacted by Response Interceptor)
// ---------------------------------------------------------------------------
permit(
  principal is AgentCore::OAuthUser,
  action == AgentCore::Action::"hr-lambda-target___get_employee_profile",
  resource == AgentCore::Gateway::"arn:aws:bedrock-agentcore:us-east-1:<YOUR-ACCOUNT-ID>:gateway/<YOUR-GATEWAY-ID>"
)
when {
  principal.hasTag("scope") &&
  principal.getTag("scope") like "*hr-dlp-gateway/read*"
};

// ---------------------------------------------------------------------------
// Policy 3: Employee Compensation
// Required scope: hr-dlp-gateway/comp
// ---------------------------------------------------------------------------
permit(
  principal is AgentCore::OAuthUser,
  action == AgentCore::Action::"hr-lambda-target___get_employee_compensation",
  resource == AgentCore::Gateway::"arn:aws:bedrock-agentcore:us-east-1:<YOUR-ACCOUNT-ID>:gateway/<YOUR-GATEWAY-ID>"
)
when {
  principal.hasTag("scope") &&
  principal.getTag("scope") like "*hr-dlp-gateway/comp*"
};

// ---------------------------------------------------------------------------
// DEPLOYMENT INSTRUCTIONS
// ---------------------------------------------------------------------------
//
// 1. Replace <YOUR-ACCOUNT-ID> and <YOUR-GATEWAY-ID> with your actual values.
//    The Gateway ARN is printed by scripts/agentcore_gateway.py create and
//    stored in SSM at /app/hrdlp/gateway-arn.
//
// 2. Create Policy Engine:
//    aws bedrock-agentcore-control create-policy-engine \
//      --name hr-dlp-policies \
//      --policy-document file://prerequisite/cedar/hr_dlp_policies.cedar \
//      --region us-east-1
//
// 3. Attach to Gateway (LOG_ONLY for testing):
//    aws bedrock-agentcore-control update-gateway \
//      --gateway-identifier <gateway-id> \
//      --policy-engine-configuration \
//        arn=<policy-engine-arn>,mode=LOG_ONLY
//
// 4. Switch to ENFORCE for production:
//    python scripts/utils/switch_policy_mode.py --mode ENFORCE
