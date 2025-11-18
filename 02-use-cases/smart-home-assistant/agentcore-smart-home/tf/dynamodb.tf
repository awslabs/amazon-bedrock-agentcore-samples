resource "aws_dynamodb_table" "sessions" {
  name           = "camera-sessions"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "prompt_id"
  range_key      = "timestamp"

  attribute {
    name = "prompt_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "N"
  }

  tags = {
    Name        = "camera-sessions"
    Environment = "dev"
  }
}
