provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "agentcore-ecommerce-demo"
      Environment = "dev"
      Stack       = "agentcore"
      ManagedBy   = "terraform"
    }
  }
}
