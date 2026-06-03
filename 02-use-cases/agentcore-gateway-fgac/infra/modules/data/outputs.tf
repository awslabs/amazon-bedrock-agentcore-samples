output "db_instance_id" {
  value       = aws_db_instance.this.id
  description = "RDS instance identifier."
}

output "db_endpoint" {
  value       = aws_db_instance.this.endpoint
  description = "Host:port endpoint for the RDS instance."
}

output "db_address" {
  value       = aws_db_instance.this.address
  description = "DNS name of the RDS instance (no port)."
}

output "db_port" {
  value       = aws_db_instance.this.port
  description = "Port the RDS instance listens on."
}

output "db_name" {
  value       = aws_db_instance.this.db_name
  description = "Initial database name."
}

output "master_user_secret_arn" {
  value       = aws_db_instance.this.master_user_secret[0].secret_arn
  description = "Secrets Manager ARN holding the AWS-managed master credentials JSON ({username, password})."
}

output "security_group_id" {
  value       = aws_security_group.db.id
  description = "Security group attached to the RDS instance. Compute module grants ingress to its app SG against this SG."
}
