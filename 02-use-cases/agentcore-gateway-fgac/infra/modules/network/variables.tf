variable "name_prefix" {
  type        = string
  description = "Prefix applied to all resource names in this module."
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR block for the VPC."
  default     = "10.30.0.0/16"
}

variable "az_count" {
  type        = number
  description = "Number of availability zones to span."
  default     = 3
}

variable "create_public_subnets" {
  type        = bool
  description = "When true, provision public subnets, an Internet Gateway, and a public route table. Required for an internet-facing ALB during JWT integration testing. Leave false for the production-shaped fully-private VPC."
  default     = false
}
