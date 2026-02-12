"""In-memory implementation of conversation repository."""

from uuid import UUID

from cx_agent_backend.domain.entities.conversation import Conversation
from cx_agent_backend.domain.repositories.conversation_repository import (
    ConversationRepository,
)


class MemoryConversationRepository(ConversationRepository):
    """In-memory conversation repository for development."""

    def __init__(self):
        self._conversations: dict[UUID, Conversation] = {}

    async def save(self, conversation: Conversation) -> None:
        """Save conversation to memory."""
        self._conversations[conversation.id] = conversation

    async def get_by_id(self, conversation_id: UUID) -> Conversation | None:
        """Get conversation by ID."""
        return self._conversations.get(conversation_id)

    async def get_by_user_id(self, user_id: str) -> list[Conversation]:
        """Get conversations by user ID."""
        return [
            conv for conv in self._conversations.values() if conv.user_id == user_id
        ]

    async def delete(self, conversation_id: UUID) -> None:
        """Delete conversation."""
        self._conversations.pop(conversation_id, None)
