"""Domain entities for conversation management."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class MessageRole(str, Enum):
    """Message role enumeration."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ConversationStatus(str, Enum):
    """Conversation status enumeration."""

    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class Message:
    """Immutable message entity."""

    id: UUID
    content: str
    role: MessageRole
    timestamp: datetime
    metadata: dict[str, Any]

    @classmethod
    def create_user_message(
        cls, content: str, metadata: dict[str, Any] | None = None
    ) -> "Message":
        """Create a user message."""
        return cls(
            id=uuid4(),
            content=content,
            role=MessageRole.USER,
            timestamp=datetime.utcnow(),
            metadata=metadata or {},
        )

    @classmethod
    def create_assistant_message(
        cls, content: str, metadata: dict[str, Any] | None = None
    ) -> "Message":
        """Create an assistant message."""
        return cls(
            id=uuid4(),
            content=content,
            role=MessageRole.ASSISTANT,
            timestamp=datetime.utcnow(),
            metadata=metadata or {},
        )


@dataclass
class Conversation:
    """Mutable conversation aggregate."""

    id: UUID
    user_id: str
    messages: list[Message]
    status: ConversationStatus
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]

    @classmethod
    def create(
        cls,
        user_id: str,
        metadata: dict[str, Any] | None = None,
        conversation_id: UUID | None = None,
    ) -> "Conversation":
        """Create a new conversation."""
        now = datetime.utcnow()
        return cls(
            id=conversation_id or uuid4(),
            user_id=user_id,
            messages=[],
            status=ConversationStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )

    def add_message(self, message: Message) -> None:
        """Add a message to the conversation."""
        self.messages.append(message)
        self.updated_at = datetime.utcnow()

    def complete(self) -> None:
        """Mark conversation as completed."""
        self.status = ConversationStatus.COMPLETED
        self.updated_at = datetime.utcnow()

    def fail(self) -> None:
        """Mark conversation as failed."""
        self.status = ConversationStatus.FAILED
        self.updated_at = datetime.utcnow()
