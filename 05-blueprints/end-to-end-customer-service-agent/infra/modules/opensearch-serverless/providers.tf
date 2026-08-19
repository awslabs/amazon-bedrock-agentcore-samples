provider "opensearch" {
  url               = "${awscc_opensearchserverless_collection.os_collection.collection_endpoint}"
  aws_region        = data.aws_region.current.name
  sign_aws_requests = true
  healthcheck       = false
}

data "aws_region" "current" {}
