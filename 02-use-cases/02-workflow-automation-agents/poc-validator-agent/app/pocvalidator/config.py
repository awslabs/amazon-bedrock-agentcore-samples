"""Centralised configuration. ALL env var reads live here — nowhere else.

This mirrors ADR 0011 in the event-driven-claims-agent sample. A test asserts
that no other module in the package calls os.getenv, because scattered config
reads are how a sample becomes undeployable six months later.

Environment variables are injected by the AgentCore CLI at deploy time. The L3
construct auto-generates names like AGENTCORE_GATEWAY_<NAME>_URL and
MEMORY_<NAME>_ID, so we read both the auto-generated and explicit forms.
"""

import os

# ─── Model ──────────────────────────────────────────────────────────────────
# Sonnet handles diagram extraction (vision + structured reasoning).
AGENT_MODEL_ID = os.getenv("AGENT_MODEL_ID", "global.anthropic.claude-sonnet-4-6")
# Haiku handles SOW criterion classification — a banding task, not a reasoning
# task. Same cost-routing rationale as ADR 0013 in the claims agent.
FAST_MODEL_ID = os.getenv("FAST_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")

# ─── AWS Region ─────────────────────────────────────────────────────────────
REGION = os.getenv("AWS_REGION", "us-west-2")

# ─── Gateway (AWS Documentation MCP target) ─────────────────────────────────
GATEWAY_URL = os.getenv(
    "AGENTCORE_GATEWAY_URL",
    os.getenv("AGENTCORE_GATEWAY_POCVALIDATORGATEWAY_URL", ""),
)
GATEWAY_OAUTH_SCOPES = os.getenv("AGENTCORE_GATEWAY_OAUTH_SCOPES", "agentcore/invoke")
GATEWAY_CREDENTIAL_PROVIDER = os.getenv(
    "AGENTCORE_GATEWAY_CREDENTIAL_PROVIDER", "cognito-gateway-m2m"
)

# ─── Memory ─────────────────────────────────────────────────────────────────
MEMORY_ID = os.getenv(
    "MEMORY_POCVALIDATORMEMORY_ID",
    os.getenv("AGENTCORE_MEMORY_ID", ""),
)
MEMORY_RETRIEVAL_TOP_K = int(os.getenv("MEMORY_RETRIEVAL_TOP_K", "5"))
MEMORY_RETRIEVAL_RELEVANCE = float(os.getenv("MEMORY_RETRIEVAL_RELEVANCE", "0.5"))

# ─── Knowledge Base (shared FAQ — see docs/decisions/0011) ─────────────────
# Unlike Memory and Gateway, the CDK L3 construct does not auto-inject an
# env var for a knowledgeBases[] resource — confirmed by inspecting the
# deployed runtime's actual environment, not assumed from the other two
# resources' pattern. Set explicitly in agentcore.json's runtime envVars by
# scripts/grant_faq_knowledge_base_access.sh after the knowledge base exists.
FAQ_KNOWLEDGE_BASE_ID = os.getenv("FAQ_KNOWLEDGE_BASE_ID", "")

# ─── Behaviour ──────────────────────────────────────────────────────────────
# When true, the agent will not run validation on a diagram-derived design graph
# until the caller has echoed the extraction back with confirmed=true. This is a
# correctness gate, not a UX preference — see docs/decisions/0002.
REQUIRE_EXTRACTION_CONFIRMATION = (
    os.getenv("REQUIRE_EXTRACTION_CONFIRMATION", "true").lower() == "true"
)

# ─── Logging ────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
