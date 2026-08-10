"""AgentCore Memory session manager with graceful degradation.

Adapted from event-driven-claims-agent/app/claimsagent/memory/session.py.

SEMANTIC gives cross-session recall — a partner submitting a second POC gets
findings informed by their first. SUMMARIZATION compresses session history so a
long review does not overflow context.

If Memory is not deployed (local dev, pre-deploy, or evaluation without an AWS
account) this returns None and the agent runs without recall.
"""

from typing import Optional

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
