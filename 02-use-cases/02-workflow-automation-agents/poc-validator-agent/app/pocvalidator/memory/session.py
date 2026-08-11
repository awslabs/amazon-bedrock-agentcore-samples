"""AgentCore Memory session manager with graceful degradation.

Adapted from event-driven-claims-agent/app/claimsagent/memory/session.py.

Three strategies, split deliberately across the short-term/long-term boundary:

- **SUMMARIZATION — short-term.** Namespace `pocvalidator/{actorId}/{sessionId}`.
  Scoped to a single review session; compresses that session's own history so
  a long review does not overflow context. Does not carry meaning across
  sessions — a new session_id starts this strategy fresh.
- **SEMANTIC — long-term.** Namespace `pocvalidator/{actorId}/facts`. Persists
  across sessions for the same actor — a partner submitting a second POC gets
  findings informed by facts extracted from their first, with no session_id in
  the namespace at all.
- **USER_PREFERENCE — long-term.** Namespace `pocvalidator/{actorId}/preferences`.
  Also cross-session and durable — e.g. a partner who always reviews
  ap-south-1/FSI submissions gets that inferred over time rather than
  re-stated every call. See ADR 0009 for why this strategy specifically needed
  a real, stable actor_id (not a shared/placeholder one) to mean anything.

All three are meaningful only when the same actor_id is reused across calls
for the same real reviewer — see the caller for how actor_id is derived. The
short-term/long-term split is what actor_id vs. session_id encode: actor_id
alone scopes the long-term strategies, actor_id + session_id together scope
the short-term one.

If Memory is not deployed (local dev, pre-deploy, or evaluation without an AWS
account) this returns None and the agent runs without recall.
"""

from bedrock_agentcore.memory.integrations.strands.config import (
    AgentCoreMemoryConfig,
    RetrievalConfig,
)
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager,
)
from config import MEMORY_ID, MEMORY_RETRIEVAL_RELEVANCE, MEMORY_RETRIEVAL_TOP_K, REGION


def get_memory_session_manager(
    session_id: str, actor_id: str
) -> AgentCoreMemorySessionManager | None:
    """Create a session manager bound to a specific review session and partner.

    Namespaces match the `memories` block in agentcore/agentcore.json.
    """
    if not MEMORY_ID:
        return None

    retrieval_config = {
        f"pocvalidator/{actor_id}/facts": RetrievalConfig(
            top_k=MEMORY_RETRIEVAL_TOP_K, relevance_score=MEMORY_RETRIEVAL_RELEVANCE
        ),
        f"pocvalidator/{actor_id}/{session_id}": RetrievalConfig(
            top_k=max(MEMORY_RETRIEVAL_TOP_K - 2, 1),
            relevance_score=MEMORY_RETRIEVAL_RELEVANCE,
        ),
        f"pocvalidator/{actor_id}/preferences": RetrievalConfig(
            top_k=max(MEMORY_RETRIEVAL_TOP_K - 2, 1),
            relevance_score=MEMORY_RETRIEVAL_RELEVANCE,
        ),
    }

    return AgentCoreMemorySessionManager(
        AgentCoreMemoryConfig(
            memory_id=MEMORY_ID,
            session_id=session_id,
            actor_id=actor_id,
            retrieval_config=retrieval_config,
        ),
        REGION,
    )
