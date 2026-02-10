# ============================================================================
# S3 Buckets for Weather Agent
# ============================================================================

# Agent Source Code Bucket
resource "aws_s3_bucket" "agent_source" {
  bucket_prefix = "${var.stack_name}-agent-source-"
  force_destroy = true

  tags = {
    Name    = "${var.stack_name}-agent-source"
    Purpose = "Store Weather Agent source code for CodeBuild"
  }
}

# Results Bucket (for agent-generated artifacts)
resource "aws_s3_bucket" "results" {
  bucket_prefix = "${var.stack_name}-results-"
  force_destroy = true

  tags = {
    Name    = "${var.stack_name}-results"
    Purpose = "Store Weather Agent generated artifacts"
  }
}

# Block public access - Agent Source
resource "aws_s3_bucket_public_access_block" "agent_source" {
  bucket = aws_s3_bucket.agent_source.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Block public access - Results Bucket
resource "aws_s3_bucket_public_access_block" "results" {
  bucket = aws_s3_bucket.results.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enable versioning - Agent Source
resource "aws_s3_bucket_versioning" "agent_source" {
  bucket = aws_s3_bucket.agent_source.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Enable versioning - Results Bucket
resource "aws_s3_bucket_versioning" "results" {
  bucket = aws_s3_bucket.results.id

  versioning_configuration {
    status = "Enabled"
  }
}

# ============================================================================
# Archive and Upload Agent Source Code
# ============================================================================

# Archive agent-code/ directory
data "archive_file" "agent_source" {
  type        = "zip"
  source_dir  = "${path.module}/agent-code"
  output_path = "${path.module}/.terraform/agent-code.zip"
}

# Upload Agent source to S3
resource "aws_s3_object" "agent_source" {
  bucket = aws_s3_bucket.agent_source.id
  key    = "agent-code-${data.archive_file.agent_source.output_md5}.zip"
  source = data.archive_file.agent_source.output_path
  etag   = data.archive_file.agent_source.output_md5

  tags = {
    Name  = "agent-source-code"
    Agent = "WeatherAgent"
    MD5   = data.archive_file.agent_source.output_md5
  }
}
