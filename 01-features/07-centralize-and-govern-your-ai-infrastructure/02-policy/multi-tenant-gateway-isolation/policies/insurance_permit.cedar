permit(
  principal,
  action in [
    AgentCore::Action::"submit-decision___submit_decision",
    AgentCore::Action::"notify-team___notify_team",
    AgentCore::Action::"query-tools___query_claims",
    AgentCore::Action::"query-tools___query_members",
    AgentCore::Action::"query-tools___query_providers",
    AgentCore::Action::"query-tools___query_benefits"
  ],
  resource
)
when {
  principal.hasTag("scope") &&
  principal.getTag("scope") like "*platform/insurance*"
};
