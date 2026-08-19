# ============================================================================
# Memory - For Persistent Conversation Context
# ============================================================================

resource "aws_bedrockagentcore_memory" "memory" {
  name                  = "${replace(var.stack_name, "-", "_")}_${var.memory_name}"
  description           = "Memory for ${var.stack_name} weather agent to maintain conversation context"
  event_expiry_duration = 30 # Days

  tags = merge(
    var.common_tags,
    {
      Name   = "${var.stack_name}-memory"
      Module = "AgentCore-Tools"
      Tool   = "Memory"
    }
  )
}
