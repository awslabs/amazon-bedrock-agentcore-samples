"""Pydantic schemas for conversation API."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class MessageRoleSchema(str, Enum):
    """Message role schema."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageSchema(BaseModel):
    """Message schema."""

    id: UUID
    content: str
    role: MessageRoleSchema
    timestamp: datetime
    metadata: dict = Field(default_factory=dict)


class ConversationStatusSchema(str, Enum):
    """Conversation status schema."""

    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


class ConversationSchema(BaseModel):
    """Conversation schema."""

    id: UUID
    user_id: str
    messages: list[MessageSchema]
    status: ConversationStatusSchema
    created_at: datetime
    updated_at: datetime
    metadata: dict = Field(default_factory=dict)


class CreateConversationRequest(BaseModel):
    """Create conversation request."""

    user_id: str = Field(..., min_length=1, max_length=100)
    metadata: dict = Field(default_factory=dict)


class FeedbackRequest(BaseModel):
    """Feedback request."""

    run_id: str = Field(
        ..., min_length=1, description="Message ID to record feedback for"
    )
    session_id: str = Field(
        ..., min_length=1, description="Session ID for the conversation"
    )
    score: float = Field(
        ..., ge=0.0, le=1.0, description="Feedback score between 0.0 and 1.0"
    )
    comment: str = Field(
        default="", max_length=1000, description="Optional feedback comment"
    )


class SendMessageRequest(BaseModel):
    """Send message request."""

    prompt: str | None = Field(None, min_length=1, max_length=10000)
    conversation_id: UUID | None = None
    model: str = Field(default="gpt-4o-mini", min_length=1)
    user_id: str | None = Field(None, min_length=1, max_length=100)
    feedback: FeedbackRequest | None = None
    langfuse_tags: list[str] = Field(
        default_factory=list, description="Tags to add to Langfuse trace"
    )


class SendMessageResponse(BaseModel):
    """Send message response."""

    response: str | None = None
    status: str = "success"
    tools_used: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str = Field(default="Healthy")
    time_of_last_update: int = Field(..., description="Unix timestamp of last update")


class ErrorResponse(BaseModel):
    """Error response."""

    error: str
    detail: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)


class FeedbackResponse(BaseModel):
    """Feedback response."""

    status: str = "success"
    timestamp: datetime = Field(default_factory=datetime.now)
