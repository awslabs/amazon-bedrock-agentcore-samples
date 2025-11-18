terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.21"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "AgentCore"
      Pattern     = "basic-runtime"
      Environment = var.environment
      ManagedBy   = "Terraform"
      StackName   = var.stack_name
    }
  }
}
