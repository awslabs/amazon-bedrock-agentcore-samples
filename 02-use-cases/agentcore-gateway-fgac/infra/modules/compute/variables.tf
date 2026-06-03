variable "name_prefix" {
  type        = string
  description = "Prefix applied to all resource names in this module."
}

variable "vpc_id" {
  type        = string
  description = "VPC for the ECS service and ALB."
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnets for ECS tasks (always private)."
}

variable "alb_subnet_ids" {
  type        = list(string)
  description = "Subnets the ALB lives in. Public subnets when alb_internet_facing=true; same as private_subnet_ids otherwise."
}

variable "alb_internet_facing" {
  type        = bool
  description = "When true, the ALB is internet-facing (scheme = internet-facing) and accepts traffic from any source. When false, internal-only. The JWT-validation action runs in either mode."
  default     = false
}

variable "alb_ingress_cidrs" {
  type        = list(string)
  description = "CIDRs allowed to reach the ALB on 443. Only meaningful when alb_internet_facing=true; for internal ALBs the SG ingress is granted by callers (Gateway VPCE, etc.)."
  default     = []
}

variable "db_address" {
  type        = string
  description = "RDS instance DNS hostname."
}

variable "db_port" {
  type        = number
  description = "Port the RDS instance listens on."
}

variable "db_name" {
  type        = string
  description = "Initial database name."
}

variable "db_master_secret_arn" {
  type        = string
  description = "Secrets Manager ARN holding {username, password} for RDS. ECS task pulls credentials from here at runtime."
}

variable "db_security_group_id" {
  type        = string
  description = "RDS security group ID. The compute module adds an ingress rule from the app SG to this SG."
}

variable "okta_issuer" {
  type        = string
  description = "Okta authorization server issuer URL. Used as the expected `iss` value by the ALB jwt-validation action."
}

variable "okta_audience" {
  type        = string
  description = "Audience expected on Okta-issued tokens. Validated as an additional claim by the ALB."
}

variable "okta_jwks_uri" {
  type        = string
  description = "Okta JWKS endpoint. Fetched by the ALB to verify token signatures. Must be publicly reachable from the ALB (out-of-band of the VPC)."
}

variable "route53_zone_id" {
  type        = string
  description = "Route53 hosted zone ID where the ALB's DNS-validated ACM cert and alias record are created."
}

variable "alb_fqdn" {
  type        = string
  description = "Fully-qualified domain name pointed at the ALB (e.g. alb.demo.example.com). Must sit under the zone identified by route53_zone_id. Used as the ACM cert subject and as the OpenAPI spec's `servers[].url` host."
}

variable "container_image" {
  type        = string
  description = "Full image URI for the application container. Leave empty until the first image is pushed; the service stays at desired_count = 0 until set."
  default     = ""
}

variable "container_port" {
  type        = number
  description = "Port the app listens on inside the container."
  default     = 8000
}

variable "task_cpu" {
  type        = number
  description = "Fargate task CPU units (1024 = 1 vCPU)."
  default     = 512
}

variable "task_memory" {
  type        = number
  description = "Fargate task memory in MiB."
  default     = 1024
}

variable "log_retention_days" {
  type        = number
  description = "CloudWatch Logs retention in days."
  default     = 14
}
