output "alb_dns_name" {
  value       = aws_lb.internal.dns_name
  description = "Raw ALB DNS name (e.g. *.elb.amazonaws.com). Mostly informational — callers should use alb_fqdn so the publicly-trusted ACM cert validates."
}

output "alb_fqdn" {
  value       = var.alb_fqdn
  description = "Public DNS name covered by the ALB's ACM cert. Use this as the host in any URL targeting the ALB."
}

output "alb_arn" {
  value       = aws_lb.internal.arn
  description = "Internal ALB ARN."
}

output "alb_security_group_id" {
  value       = aws_security_group.alb.id
  description = "Security group attached to the internal ALB. Callers (e.g. AgentCore Gateway VPC endpoint) add ingress rules referencing this SG."
}

output "ecr_repository_url" {
  value       = aws_ecr_repository.app.repository_url
  description = "ECR repository URL where the application container image is pushed."
}

output "ecs_cluster_name" {
  value       = aws_ecs_cluster.this.name
  description = "ECS cluster name."
}

output "ecs_service_name" {
  value       = aws_ecs_service.app.name
  description = "ECS service name."
}

output "app_security_group_id" {
  value       = aws_security_group.app.id
  description = "Security group attached to ECS tasks."
}

output "task_definition_arn" {
  value       = aws_ecs_task_definition.app.arn
  description = "Task definition ARN of the app. Used by `scripts/bootstrap_remote_db.sh` to launch a one-off Fargate task for DB bootstrap."
}

output "task_log_group_name" {
  value       = aws_cloudwatch_log_group.app.name
  description = "CloudWatch Logs group the app container streams to. Bootstrap script tails this for the one-off task."
}
