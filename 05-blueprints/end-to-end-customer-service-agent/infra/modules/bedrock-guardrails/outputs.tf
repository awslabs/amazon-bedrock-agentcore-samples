output "guardrail_id" {
  description = "ID of the Bedrock guardrail"
  value       = aws_bedrock_guardrail.guardrail.guardrail_id
}

output "guardrail_arn" {
  description = "ARN of the Bedrock guardrail"
  value       = aws_bedrock_guardrail.guardrail.guardrail_arn
}