# ============================================================================
# S3 Buckets for Agent Source Code (CDK Asset Equivalent)
# ============================================================================

# Agent1 (Orchestrator) Source Bucket
resource "aws_s3_bucket" "agent1_source" {
  bucket_prefix = "${var.stack_name}-agent1-source-"
  force_destroy = true

  tags = {
    Name    = "${var.stack_name}-agent1-source"
    Purpose = "Store Agent1 Orchestrator source code for CodeBuild"
  }
}

# Agent2 (Specialist) Source Bucket
resource "aws_s3_bucket" "agent2_source" {
  bucket_prefix = "${var.stack_name}-agent2-source-"
  force_destroy = true

  tags = {
    Name    = "${var.stack_name}-agent2-source"
    Purpose = "Store Agent2 Specialist source code for CodeBuild"
  }
}

# Block public access - Agent1
resource "aws_s3_bucket_public_access_block" "agent1_source" {
  bucket = aws_s3_bucket.agent1_source.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Block public access - Agent2
resource "aws_s3_bucket_public_access_block" "agent2_source" {
  bucket = aws_s3_bucket.agent2_source.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enable versioning - Agent1
resource "aws_s3_bucket_versioning" "agent1_source" {
  bucket = aws_s3_bucket.agent1_source.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Enable versioning - Agent2
resource "aws_s3_bucket_versioning" "agent2_source" {
  bucket = aws_s3_bucket.agent2_source.id

  versioning_configuration {
    status = "Enabled"
  }
}

# ============================================================================
# Archive and Upload Agent Source Code
# ============================================================================

# Archive agent1-code/ directory
data "archive_file" "agent1_source" {
  type        = "zip"
  source_dir  = "${path.module}/agent1-code"
  output_path = "${path.module}/.terraform/agent1-code.zip"
}

# Archive agent2-code/ directory
data "archive_file" "agent2_source" {
  type        = "zip"
  source_dir  = "${path.module}/agent2-code"
  output_path = "${path.module}/.terraform/agent2-code.zip"
}

# Upload Agent1 source to S3
resource "aws_s3_object" "agent1_source" {
  bucket = aws_s3_bucket.agent1_source.id
  key    = "agent1-code-${data.archive_file.agent1_source.output_md5}.zip"
  source = data.archive_file.agent1_source.output_path
  etag   = data.archive_file.agent1_source.output_md5

  tags = {
    Name  = "agent1-source-code"
    Agent = "Agent1-Orchestrator"
    MD5   = data.archive_file.agent1_source.output_md5
  }
}

# Upload Agent2 source to S3
resource "aws_s3_object" "agent2_source" {
  bucket = aws_s3_bucket.agent2_source.id
  key    = "agent2-code-${data.archive_file.agent2_source.output_md5}.zip"
  source = data.archive_file.agent2_source.output_path
  etag   = data.archive_file.agent2_source.output_md5

  tags = {
    Name  = "agent2-source-code"
    Agent = "Agent2-Specialist"
    MD5   = data.archive_file.agent2_source.output_md5
  }
}
