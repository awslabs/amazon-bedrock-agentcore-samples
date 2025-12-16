# ============================================================================
# Observability Module - CloudWatch Logs and X-Ray Traces Delivery
# ============================================================================

# ============================================================================
# Application Logs Setup
# ============================================================================

# CloudWatch Log Group for vended log delivery
resource "aws_cloudwatch_log_group" "agent_runtime_logs" {
  name              = "/aws/vendedlogs/bedrock-agentcore/${aws_bedrockagentcore_agent_runtime.weather_agent.agent_runtime_id}"
  retention_in_days = 14

  tags = {
    Name    = "${var.stack_name}-agent-logs"
    Purpose = "Agent runtime application logs"
    Module  = "Observability"
  }

  depends_on = [aws_bedrockagentcore_agent_runtime.weather_agent]
}

# Delivery Source for Application Logs
resource "aws_cloudwatch_log_delivery_source" "logs" {
  name         = "${aws_bedrockagentcore_agent_runtime.weather_agent.agent_runtime_id}-logs-source"
  log_type     = "APPLICATION_LOGS"
  resource_arn = aws_bedrockagentcore_agent_runtime.weather_agent.agent_runtime_arn

  depends_on = [aws_bedrockagentcore_agent_runtime.weather_agent]
}

# Delivery Destination for Logs (CloudWatch Logs)
resource "aws_cloudwatch_log_delivery_destination" "logs" {
  name = "${aws_bedrockagentcore_agent_runtime.weather_agent.agent_runtime_id}-logs-destination"

  delivery_destination_configuration {
    destination_resource_arn = aws_cloudwatch_log_group.agent_runtime_logs.arn
  }

  tags = {
    Name    = "${var.stack_name}-logs-destination"
    Purpose = "CloudWatch Logs delivery destination"
    Module  = "Observability"
  }

  depends_on = [aws_cloudwatch_log_group.agent_runtime_logs]
}

# Delivery Connection for Logs
resource "aws_cloudwatch_log_delivery" "logs" {
  delivery_source_name     = aws_cloudwatch_log_delivery_source.logs.name
  delivery_destination_arn = aws_cloudwatch_log_delivery_destination.logs.arn

  tags = {
    Name    = "${var.stack_name}-logs-delivery"
    Purpose = "Connect logs source to CloudWatch destination"
    Module  = "Observability"
  }

  depends_on = [
    aws_cloudwatch_log_delivery_source.logs,
    aws_cloudwatch_log_delivery_destination.logs
  ]
}

# ============================================================================
# X-Ray Traces Setup
# ============================================================================

# Delivery Source for Traces
resource "aws_cloudwatch_log_delivery_source" "traces" {
  name         = "${aws_bedrockagentcore_agent_runtime.weather_agent.agent_runtime_id}-traces-source"
  log_type     = "TRACES"
  resource_arn = aws_bedrockagentcore_agent_runtime.weather_agent.agent_runtime_arn

  depends_on = [aws_bedrockagentcore_agent_runtime.weather_agent]
}

# Delivery Destination for Traces (X-Ray)
resource "aws_cloudwatch_log_delivery_destination" "traces" {
  name                      = "${aws_bedrockagentcore_agent_runtime.weather_agent.agent_runtime_id}-traces-destination"
  delivery_destination_type = "XRAY"

  tags = {
    Name    = "${var.stack_name}-traces-destination"
    Purpose = "X-Ray traces delivery destination"
    Module  = "Observability"
  }
}

# Delivery Connection for Traces
resource "aws_cloudwatch_log_delivery" "traces" {
  delivery_source_name     = aws_cloudwatch_log_delivery_source.traces.name
  delivery_destination_arn = aws_cloudwatch_log_delivery_destination.traces.arn

  tags = {
    Name    = "${var.stack_name}-traces-delivery"
    Purpose = "Connect traces source to X-Ray destination"
    Module  = "Observability"
  }

  depends_on = [
    aws_cloudwatch_log_delivery_source.traces,
    aws_cloudwatch_log_delivery_destination.traces
  ]
}

# ============================================================================
# Outputs
# ============================================================================

output "log_group_name" {
  description = "CloudWatch Log Group name for agent runtime vended logs"
  value       = aws_cloudwatch_log_group.agent_runtime_logs.name
}

output "log_group_arn" {
  description = "ARN of the CloudWatch Log Group"
  value       = aws_cloudwatch_log_group.agent_runtime_logs.arn
}

output "logs_delivery_id" {
  description = "ID of the logs delivery connection"
  value       = aws_cloudwatch_log_delivery.logs.id
}

output "traces_delivery_id" {
  description = "ID of the traces delivery connection"
  value       = aws_cloudwatch_log_delivery.traces.id
}
