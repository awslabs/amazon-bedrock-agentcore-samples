variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "runtime_name" {
  description = "AgentCore runtime name"
  type        = string
  default     = "athena_text_to_sql_mcp_server"
}

variable "smart_home_bucket_name" {
  description = "S3 bucket name for Smart Home data"
  type        = string
  sensitive   = true
}

variable "athena_database" {
  description = "Athena database name"
  type        = string
  default     = "camera-database"
}

variable "athena_workgroup" {
  description = "Athena workgroup name"
  type        = string
  default     = "camera-streams-workgroup"
}

variable "user_pool_name" {
  description = "Cognito User Pool name"
  type        = string
  default     = "smarthome-agentcore-runtime-pool"
}

variable "resource_server_id" {
  description = "Cognito Resource Server ID"
  type        = string
  default     = "smarthome-agentcore-runtime-id"
}

variable "resource_server_name" {
  description = "Cognito Resource Server name"
  type        = string
  default     = "smarthome-agentcore-runtime-name"
}

variable "client_name" {
  description = "Cognito Client name"
  type        = string
  default     = "smarthome-agentcore-runtime-client"
}

variable "agent_name" {
  description = "AgentCore agent name"
  type        = string
  default     = "athena_text_to_sql_mcp_server"
}

variable "camera_role_arn" {
  description = "Cross-account camera role ARN"
  type        = string
  sensitive   = true
}

variable "camera_region" {
  description = "Camera region"
  type        = string
  default     = "eu-west-1"
}
