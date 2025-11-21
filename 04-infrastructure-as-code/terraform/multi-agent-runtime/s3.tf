# ============================================================================
# S3 Buckets for Agent Source Code (CDK Asset Equivalent)
# ============================================================================

# Orchestrator Agent Source Bucket
resource "aws_s3_bucket" "orchestrator_source" {
  bucket_prefix = "acma-orch-src-" # Shortened to fit 37 char limit
  force_destroy = true

  tags = {
    Name    = "${var.stack_name}-orchestrator-source"
    Purpose = "Store Orchestrator agent source code for CodeBuild"
  }
}

# Specialist Agent Source Bucket
resource "aws_s3_bucket" "specialist_source" {
  bucket_prefix = "acma-spec-src-" # Shortened to fit 37 char limit
  force_destroy = true

  tags = {
    Name    = "${var.stack_name}-specialist-source"
    Purpose = "Store Specialist agent source code for CodeBuild"
  }
}

# Block public access - Orchestrator
resource "aws_s3_bucket_public_access_block" "orchestrator_source" {
  bucket = aws_s3_bucket.orchestrator_source.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Block public access - Specialist
resource "aws_s3_bucket_public_access_block" "specialist_source" {
  bucket = aws_s3_bucket.specialist_source.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enable versioning - Orchestrator
resource "aws_s3_bucket_versioning" "orchestrator_source" {
  bucket = aws_s3_bucket.orchestrator_source.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Enable versioning - Specialist
resource "aws_s3_bucket_versioning" "specialist_source" {
  bucket = aws_s3_bucket.specialist_source.id

  versioning_configuration {
    status = "Enabled"
  }
}

# ============================================================================
# Archive and Upload Agent Source Code
# ============================================================================

# Archive agent-orchestrator-code/ directory
data "archive_file" "orchestrator_source" {
  type        = "zip"
  source_dir  = "${path.module}/agent-orchestrator-code"
  output_path = "${path.module}/.terraform/agent-orchestrator-code.zip"
}

# Archive agent-specialist-code/ directory
data "archive_file" "specialist_source" {
  type        = "zip"
  source_dir  = "${path.module}/agent-specialist-code"
  output_path = "${path.module}/.terraform/agent-specialist-code.zip"
}

# Upload Orchestrator source to S3
resource "aws_s3_object" "orchestrator_source" {
  bucket = aws_s3_bucket.orchestrator_source.id
  key    = "agent-orchestrator-code-${data.archive_file.orchestrator_source.output_md5}.zip"
  source = data.archive_file.orchestrator_source.output_path
  etag   = data.archive_file.orchestrator_source.output_md5

  tags = {
    Name  = "agent-orchestrator-source-code"
    Agent = "Orchestrator"
    MD5   = data.archive_file.orchestrator_source.output_md5
  }
}

# Upload Specialist source to S3
resource "aws_s3_object" "specialist_source" {
  bucket = aws_s3_bucket.specialist_source.id
  key    = "agent-specialist-code-${data.archive_file.specialist_source.output_md5}.zip"
  source = data.archive_file.specialist_source.output_path
  etag   = data.archive_file.specialist_source.output_md5

  tags = {
    Name  = "agent-specialist-source-code"
    Agent = "Specialist"
    MD5   = data.archive_file.specialist_source.output_md5
  }
}
