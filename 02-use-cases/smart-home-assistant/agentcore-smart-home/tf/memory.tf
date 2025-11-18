# AgentCore Memory
resource "aws_bedrockagentcore_memory" "orchestrator_memory" {
  name                  = "orchestrator_long_term_mem"
  description          = "Long-term memory for orchestrator agent"
  event_expiry_duration = 90

  tags = {
    Name        = "orchestrator-memory"
    Environment = "dev"
  }
}

# User Preference Strategy
resource "aws_bedrockagentcore_memory_strategy" "user_preferences" {
  name        = "UserPreferences"
  memory_id   = aws_bedrockagentcore_memory.orchestrator_memory.id
  type        = "USER_PREFERENCE"
  description = "Captures users preferences and behavior"
  namespaces  = ["connected-home/user/{actorId}/preferences"]
}

# Semantic Strategy
resource "aws_bedrockagentcore_memory_strategy" "user_semantic" {
  name        = "UserSemantic"
  memory_id   = aws_bedrockagentcore_memory.orchestrator_memory.id
  type        = "SEMANTIC"
  description = "Stores facts from conversations"
  namespaces  = ["connected-home/user/{actorId}/semantic"]
}
