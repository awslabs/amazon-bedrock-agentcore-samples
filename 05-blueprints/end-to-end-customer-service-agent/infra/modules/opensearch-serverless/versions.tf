terraform {
  required_providers {
    opensearch = {
      source  = "opensearch-project/opensearch"
      version = "~> 2.0"
    }
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
    awscc = {
      source  = "hashicorp/awscc"
      version = "~> 0.70"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.9"
    }
  }
}