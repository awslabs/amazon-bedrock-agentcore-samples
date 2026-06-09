permit(
  principal,
  action in [
    AgentCore::Action::"flag-suspicious___flag_suspicious",
    AgentCore::Action::"query-tools___query_accounts",
    AgentCore::Action::"query-tools___query_transactions"
  ],
  resource
)
when {
  principal.hasTag("scope") &&
  principal.getTag("scope") like "*platform/banking*"
};
