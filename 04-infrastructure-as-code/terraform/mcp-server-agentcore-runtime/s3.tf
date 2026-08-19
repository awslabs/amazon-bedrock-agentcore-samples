# ============================================================================
# S3 Bucket for MCP Server Source Code (CDK Asset Equivalent)
# ============================================================================

resource "aws_s3_bucket" "agent_source" {
  bucket_prefix = "${var.stack_name}-source-"
  force_destroy = true

  tags = {
    Name    = "${var.stack_name}-mcp-server-source"
    Purpose = "Store MCP server source code for CodeBuild"
  }
}

# Block public access
resource "aws_s3_bucket_public_access_block" "agent_source" {
  bucket = aws_s3_bucket.agent_source.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enable versioning for source code tracking
resource "aws_s3_bucket_versioning" "agent_source" {
  bucket = aws_s3_bucket.agent_source.id

  versioning_configuration {
    status = "Enabled"
  }
}

# ============================================================================
# Archive and Upload MCP Server Source Code
# ============================================================================

# Archive mcp-server-code/ directory
# This automatically detects ALL files including new ones
data "archive_file" "agent_source" {
  type        = "zip"
  source_dir  = "${path.module}/mcp-server-code"
  output_path = "${path.module}/.terraform/mcp-server-code.zip"
}

# Upload to S3 (re-uploads when MD5 changes)
resource "aws_s3_object" "agent_source" {
  bucket = aws_s3_bucket.agent_source.id
  key    = "mcp-server-code-${data.archive_file.agent_source.output_md5}.zip"
  source = data.archive_file.agent_source.output_path
  etag   = data.archive_file.agent_source.output_md5

  tags = {
    Name      = "mcp-server-source-code"
    MD5       = data.archive_file.agent_source.output_md5
    Timestamp = timestamp()
  }
}
