variable "name_prefix" {
  type        = string
  description = "Prefix applied to all resource names in this module."
}

variable "vpc_id" {
  type        = string
  description = "VPC the database subnet group belongs to."
}

variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR. Used to scope outbound rules; ingress is restricted by SG reference."
}

variable "subnet_ids" {
  type        = list(string)
  description = "Private subnet IDs for the RDS subnet group (must span at least 2 AZs)."
}

variable "db_name" {
  type        = string
  description = "Initial database name."
  default     = "ecommerce"
}

variable "db_username" {
  type        = string
  description = "Master username for the RDS instance."
  default     = "ecommerce"
}

variable "instance_class" {
  type        = string
  description = "RDS instance class."
  default     = "db.t4g.micro"
}

variable "allocated_storage_gb" {
  type        = number
  description = "Allocated storage in GB."
  default     = 20
}

variable "engine_version" {
  type        = string
  description = "Postgres engine version."
  default     = "18.4"
}
