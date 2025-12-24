# ============================================================================
# Code Interpreter Tool - For Python Code Execution and Data Analysis
# ============================================================================

resource "aws_bedrockagentcore_code_interpreter" "code_interpreter" {
  name        = "${replace(var.stack_name, "-", "_")}_code_interpreter"
  description = "Code interpreter tool for ${var.stack_name} weather agent to analyze weather data and create visualizations"

  network_configuration {
    network_mode = var.network_mode
  }

  tags = merge(
    var.common_tags,
    {
      Name   = "${var.stack_name}-code-interpreter-tool"
      Module = "AgentCore-Tools"
      Tool   = "CodeInterpreter"
    }
  )
}
