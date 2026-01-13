variable "collection_name" {
  description = "Name of the OpenSearch Serverless collection"
  type        = string
}

variable "collection_tags" {
  description = "Tags for the OpenSearch collection"
  type = list(object({
    key   = string
    value = string
  }))
  default = []
}

variable "allow_public_access_network_policy" {
  description = "Whether to allow public access via network policy"
  type        = bool
  default     = true
}

variable "create_vector_index" {
  description = "Whether to create a vector index"
  type        = bool
  default     = true
}

variable "number_of_shards" {
  description = "Number of shards for the index"
  type        = number
  default     = 1
}

variable "number_of_replicas" {
  description = "Number of replicas for the index"
  type        = number
  default     = 0
}

variable "index_knn_algo_param_ef_search" {
  description = "KNN algorithm parameter ef_search"
  type        = number
  default     = 512
}

variable "vector_index_mappings" {
  description = "Mappings for the vector index"
  type        = string
  default     = ""
}

locals {
  default_mappings = jsonencode({
    properties = {
      "bedrock-knowledge-base-default-vector" = {
        type      = "knn_vector"
        dimension = 1024
        method = {
          name   = "hnsw"
          engine = "faiss"
          parameters = {
            m = 16
            ef_construction = 512
          }
          space_type = "l2"
        }
      }
      "AMAZON_BEDROCK_TEXT_CHUNK" = {
        type = "text"
      }
      "AMAZON_BEDROCK_METADATA" = {
        type = "text"
      }
    }
  })
}

variable "force_destroy_vector_index" {
  description = "Whether to force destroy the vector index"
  type        = bool
  default     = true
}

variable "analysis_analyzer" {
  description = "Analysis analyzer configuration"
  type        = string
  default     = ""
}

variable "analysis_char_filter" {
  description = "Analysis char filter configuration"
  type        = string
  default     = ""
}

variable "analysis_filter" {
  description = "Analysis filter configuration"
  type        = string
  default     = ""
}

variable "analysis_normalizer" {
  description = "Analysis normalizer configuration"
  type        = string
  default     = ""
}

variable "analysis_tokenizer" {
  description = "Analysis tokenizer configuration"
  type        = string
  default     = ""
}

variable "additional_principals" {
  description = "Additional principals to grant access to the collection"
  type        = list(string)
  default     = []
}