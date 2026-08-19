variable "guardrail_name" {
  description = "Name of the Bedrock guardrail"
  type        = string
}

variable "blocked_input_messaging" {
  description = "Message to display when input is blocked"
  type        = string
}

variable "blocked_outputs_messaging" {
  description = "Message to display when output is blocked"
  type        = string
}

variable "description" {
  description = "Description of the guardrail"
  type        = string
}

