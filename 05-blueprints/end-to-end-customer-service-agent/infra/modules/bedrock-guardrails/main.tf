resource "aws_bedrock_guardrail" "guardrail" {
  name                      = var.guardrail_name
  blocked_input_messaging   = var.blocked_input_messaging
  blocked_outputs_messaging = var.blocked_outputs_messaging
  description               = var.description

  content_policy_config {
    filters_config {
      input_strength  = "MEDIUM"
      output_strength = "MEDIUM"
      type            = "HATE"
    }
  }

  sensitive_information_policy_config {
    pii_entities_config {
      action         = "ANONYMIZE"
      type           = "US_BANK_ROUTING_NUMBER"
    }

    pii_entities_config {
      action         = "ANONYMIZE"
      type           = "US_SOCIAL_SECURITY_NUMBER"
    }
  }

  topic_policy_config {
    topics_config {
      name       = "investment_topic"
      examples   = ["Where should I invest my money ?"]
      type       = "DENY"
      definition = "Investment advice refers to inquiries, guidance, or recommendations regarding the management or allocation of funds or assets with the goal of generating returns ."
    }
  }

  word_policy_config {
    managed_word_lists_config {
      type = "PROFANITY"
    }
    words_config {
      text = "HATE"
    }
  }
}