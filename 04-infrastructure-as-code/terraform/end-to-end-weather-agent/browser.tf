# ============================================================================
# Browser Tool - For Web Browsing Capabilities
# ============================================================================

resource "aws_bedrockagentcore_browser" "browser" {
  name        = "${replace(var.stack_name, "-", "_")}_browser"
  description = "Browser tool for ${var.stack_name} weather agent to access weather websites and advisories"

  network_configuration {
    network_mode = var.network_mode
  }

  tags = merge(
    var.common_tags,
    {
      Name   = "${var.stack_name}-browser-tool"
      Module = "AgentCore-Tools"
      Tool   = "Browser"
    }
  )
}
