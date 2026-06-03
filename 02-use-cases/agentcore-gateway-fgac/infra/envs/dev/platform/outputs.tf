output "alb_dns_name" {
  value       = module.compute.alb_dns_name
  description = "Raw ALB DNS name. Use alb_fqdn for any URL where the public ACM cert needs to validate."
}

output "alb_fqdn" {
  value       = module.compute.alb_fqdn
  description = "Public DNS name covered by the ALB's ACM cert. Consumed by the agentcore stack as the OpenAPI host."
}

output "alb_arn" {
  value       = module.compute.alb_arn
  description = "ALB ARN."
}

output "alb_security_group_id" {
  value       = module.compute.alb_security_group_id
  description = "Security group attached to the ALB."
}

output "ecr_repository_url" {
  value       = module.compute.ecr_repository_url
  description = "ECR repository URL where the application container image is pushed."
}

output "ecs_cluster_name" {
  value       = module.compute.ecs_cluster_name
  description = "ECS cluster name."
}

output "ecs_service_name" {
  value       = module.compute.ecs_service_name
  description = "ECS service name."
}

output "vpc_id" {
  value       = module.network.vpc_id
  description = "VPC ID, exposed for the agentcore stack."
}

output "private_subnet_ids" {
  value       = module.network.private_subnet_ids
  description = "Private subnet IDs, exposed for the agentcore stack."
}

output "app_security_group_id" {
  value       = module.compute.app_security_group_id
  description = "Security group attached to ECS tasks. Used by the remote bootstrap script."
}

output "task_definition_arn" {
  value       = module.compute.task_definition_arn
  description = "App task definition ARN. Used by the remote bootstrap script."
}

output "task_log_group_name" {
  value       = module.compute.task_log_group_name
  description = "CloudWatch Logs group for the app task."
}
