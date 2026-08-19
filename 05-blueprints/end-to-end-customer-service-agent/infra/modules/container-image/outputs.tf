output "ecr_repository_arn" {
  description = "ARN of the Amazon ECR repository for the agent container image"
  value       = aws_ecr_repository.ecr_repository.arn
}

output "ecr_repository_uri" {
  description = "URI of the Amazon ECR repository for the agent container image"
  value       = aws_ecr_repository.ecr_repository.repository_url
}

output "ecr_image_uri" {
  description = "URI of the Amazon ECR repository for the agent container image"
  value       = terraform_data.ecr_image.output
}
