"""AgentCore Memory session manager with graceful degradation.

The session manager attaches to the Strands Agent and automatically records
each conversation turn to AgentCore Memory. The SEMANTIC strategy enables
cross-session recall (e.g., prior claims for repeat claimants), while
SUMMARIZATION compresses session history to prevent context overflow.

If Memory is not deployed or unavailable (local dev, pre-deploy), the agent
continues working without memory — it just won't recall prior interactions.
"""

from typing import Optional

from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager,
)
from config import MEMORY_ID, REGION


def get_memory_session_manager(session_id: str, actor_id: str) -> Optional[AgentCoreMemorySessionManager]:
    """Create a session manager bound to a specific session and actor.

    Args:
        session_id: Unique session identifier (e.g., claim-{policy_number}-{timestamp}).
        actor_id: The claimant or user who initiated the interaction.

    Returns:
        AgentCoreMemorySessionManager if MEMORY_ID is configured, else None.
    """
    if not MEMORY_ID:
        return None

    return AgentCoreMemorySessionManager(
        AgentCoreMemoryConfig(
            memory_id=MEMORY_ID,
            session_id=session_id,
            actor_id=actor_id,
        ),
        REGION,
    )
