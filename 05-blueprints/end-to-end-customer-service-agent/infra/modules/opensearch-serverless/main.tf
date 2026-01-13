data "aws_caller_identity" "current" {}
data "aws_iam_session_context" "current" {
  arn = data.aws_caller_identity.current.arn
}

# – OpenSearch Serverless –

# Create a Collection
resource "awscc_opensearchserverless_collection" "os_collection" {
  name        = "os-collection-${var.collection_name}"
  type        = "VECTORSEARCH"
  description = "OpenSearch collection created by Terraform."
  depends_on = [
    aws_opensearchserverless_security_policy.security_policy,
    aws_opensearchserverless_security_policy.nw_policy[0]
  ]
  tags = var.collection_tags
}

# Encryption Security Policy
resource "aws_opensearchserverless_security_policy" "security_policy" {
  name  = "security-policy-${var.collection_name}"
  type  = "encryption"
  policy = jsonencode({
    Rules = [
      {
        Resource     = ["collection/os-collection-${var.collection_name}"]
        ResourceType = "collection"
      }
    ],
    AWSOwnedKey = true
  })
}

# Network policy
resource "aws_opensearchserverless_security_policy" "nw_policy" {
  count = var.allow_public_access_network_policy ? 1 : 0
  name  = "nw-policy-${var.collection_name}"
  type  = "network"
  policy = jsonencode([
    {
      Rules = [
        {
          ResourceType = "collection"
          Resource     = ["collection/os-collection-${var.collection_name}"]
        },
      ]
      AllowFromPublic = true,
    },
    {
      Description = "Public access for dashboards",
      Rules = [
        {
          ResourceType = "dashboard"
          Resource = [
            "collection/os-collection-${var.collection_name}"
          ]
        }
      ],
      AllowFromPublic = true
    }

  ])
}


# Data policy
resource "aws_opensearchserverless_access_policy" "data_policy" {
  name  = "os-access-policy-${var.collection_name}"
  type  = "data"
  policy = jsonencode([
    {
      Rules = [
        {
          ResourceType = "index"
          Resource = [
            "index/${awscc_opensearchserverless_collection.os_collection.name}/*"
          ]
          Permission = [
            "aoss:UpdateIndex",
            "aoss:DeleteIndex",
            "aoss:DescribeIndex",
            "aoss:ReadDocument",
            "aoss:WriteDocument",
            "aoss:CreateIndex"
          ]
        },
        {
          ResourceType = "collection"
          Resource = [
            "collection/${awscc_opensearchserverless_collection.os_collection.name}"
          ]
          Permission = [
            "aoss:DescribeCollectionItems",
            "aoss:DeleteCollectionItems",
            "aoss:CreateCollectionItems",
            "aoss:UpdateCollectionItems"
          ]
        }
      ],
      Principal = concat([
        data.aws_caller_identity.current.arn,
        data.aws_iam_session_context.current.issuer_arn
      ], var.additional_principals)
    }
  ])
}

# OpenSearch index

resource "time_sleep" "wait_before_index_creation" {
  count           = var.create_vector_index ? 1 : 0
  depends_on      = [aws_opensearchserverless_access_policy.data_policy]
  create_duration = "60s" # Wait for 60 seconds before creating the index
}

resource "opensearch_index" "vector_index" {
  count                          = var.create_vector_index ? 1 : 0
  name                           = "os-vector-index-${var.collection_name}"
  number_of_shards               = var.number_of_shards
  number_of_replicas             = var.number_of_replicas
  index_knn                      = true
  index_knn_algo_param_ef_search = var.index_knn_algo_param_ef_search
  mappings                       = var.vector_index_mappings != "" ? var.vector_index_mappings : local.default_mappings
  force_destroy                  = var.force_destroy_vector_index
  analysis_analyzer              = var.analysis_analyzer
  analysis_char_filter           = var.analysis_char_filter
  analysis_filter                = var.analysis_filter 
  analysis_normalizer            = var.analysis_normalizer
  analysis_tokenizer             = var.analysis_tokenizer   
  depends_on                     = [time_sleep.wait_before_index_creation[0], aws_opensearchserverless_access_policy.data_policy]
  lifecycle {
    ignore_changes = [
      number_of_shards,
      number_of_replicas
    ]
  }
}
