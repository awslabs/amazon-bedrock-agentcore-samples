data "aws_region" "current" {}

resource "aws_iam_role_policy" "bedrock_kb_sample_kb_model" {
  name = "AmazonBedrockOSSPolicyForKnowledgeBase_${var.kb_name}"
  role = var.bedrock_role_name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # We'd like to scope this down further, but many of the individual AOSS IAM actions don't
        # support resource-level permissions, so currently using this all-inclusive one (as
        # recommended by Bedrock User Guide). See:
        # - https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazonopensearchserverless.html
        # - https://docs.aws.amazon.com/bedrock/latest/userguide/kb-permissions.html#kb-permissions-oss
        Action   = [
          "aoss:APIAccessAll",
        ]
        Effect   = "Allow"
        Resource = [var.opensearch_arn]
      },
      {
        Action   = ["bedrock:InvokeModel"]
        Effect   = "Allow"
        Resource = [
          "arn:aws:bedrock:${data.aws_region.current.name}::foundation-model/amazon.titan-embed-*"
        ]
      },
      {
        Action   = ["s3:ListBucket", "s3:GetObject"]
        Effect   = "Allow"
        Resource = [var.s3_arn, "${var.s3_arn}/*"]
      }
    ]
  })
}

resource "time_sleep" "iam_consistency_delay" {
  create_duration = "240s"
  depends_on      = [aws_iam_role_policy.bedrock_kb_sample_kb_model]
}


resource "aws_bedrockagent_knowledge_base" "sample_kb" {
  name     = var.kb_name
  role_arn = var.bedrock_role_arn
  knowledge_base_configuration {
    vector_knowledge_base_configuration {
      embedding_model_arn = "arn:aws:bedrock:${data.aws_region.current.name}::foundation-model/amazon.titan-embed-text-v2:0"
    }
    type = "VECTOR"
  }
  storage_configuration {
    type = "OPENSEARCH_SERVERLESS"
    opensearch_serverless_configuration {
      collection_arn    = var.opensearch_arn
      vector_index_name = var.opensearch_index_name
      field_mapping {
        vector_field   = "bedrock-knowledge-base-default-vector"
        text_field     = "AMAZON_BEDROCK_TEXT_CHUNK"
        metadata_field = "AMAZON_BEDROCK_METADATA"
      }
    }
  }
  depends_on = [time_sleep.iam_consistency_delay, aws_iam_role_policy.bedrock_kb_sample_kb_model]
}

resource "aws_bedrockagent_data_source" "sample_kb" {
  knowledge_base_id = aws_bedrockagent_knowledge_base.sample_kb.id
  name              = "${var.kb_name}DataSource"
  data_source_configuration {
    type = "S3"
    s3_configuration {
      bucket_arn = var.s3_arn
    }
  }
}