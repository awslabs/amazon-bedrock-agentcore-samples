"""Repository interfaces for conversation management."""

from abc import ABC, abstractmethod
from uuid import UUID

from cx_agent_backend.domain.entities.conversation import Conversation


class ConversationRepository(ABC):
    """Abstract repository for conversation persistence."""

    @abstractmethod
    async def save(self, conversation: Conversation) -> None:
        """Save a conversation."""
        pass

    @abstractmethod
    async def get_by_id(self, conversation_id: UUID) -> Conversation | None:
        """Get conversation by ID."""
        pass

    @abstractmethod
    async def get_by_user_id(self, user_id: str) -> list[Conversation]:
        """Get conversations by user ID."""
        pass

    @abstractmethod
    async def delete(self, conversation_id: UUID) -> None:
        """Delete a conversation."""
        pass
