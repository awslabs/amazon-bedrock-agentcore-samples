"""FastAPI router for conversation endpoints."""

import logging
import time
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status

from cx_agent_backend.domain.entities.conversation import Conversation, Message
from cx_agent_backend.domain.services.conversation_service import ConversationService
from cx_agent_backend.infrastructure.config.container import Container
from cx_agent_backend.presentation.schemas.conversation_schemas import (
    ConversationSchema,
    CreateConversationRequest,
    HealthResponse,
    MessageSchema,
    SendMessageRequest,
    SendMessageResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["conversations"])


@router.get("/ping", response_model=HealthResponse)
async def ping() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(time_of_last_update=int(time.time()))


def _message_to_schema(message: Message) -> MessageSchema:
    """Convert domain message to schema."""
    return MessageSchema(
        id=message.id,
        content=message.content,
        role=message.role.value,
        timestamp=message.timestamp,
        metadata=message.metadata,
    )


def _conversation_to_schema(conversation: Conversation) -> ConversationSchema:
    """Convert domain conversation to schema."""
    return ConversationSchema(
        id=conversation.id,
        user_id=conversation.user_id,
        messages=[_message_to_schema(msg) for msg in conversation.messages],
        status=conversation.status.value,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        metadata=conversation.metadata,
    )


@router.post(
    "/", response_model=ConversationSchema, status_code=status.HTTP_201_CREATED
)
@inject
async def create_conversation(
    request: CreateConversationRequest,
    conversation_service: ConversationService = Depends(
        Provide[Container.conversation_service]
    ),
) -> ConversationSchema:
    """Create a new conversation."""
    try:
        conversation = await conversation_service.start_conversation(request.user_id)
        return _conversation_to_schema(conversation)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create conversation: {str(e)}",
        )


@router.get("/{conversation_id}", response_model=ConversationSchema)
@inject
async def get_conversation(
    conversation_id: UUID,
    conversation_service: ConversationService = Depends(
        Provide[Container.conversation_service]
    ),
) -> ConversationSchema:
    """Get conversation by ID."""
    conversation = await conversation_service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )
    return _conversation_to_schema(conversation)


@router.post("/send-message", response_model=SendMessageResponse)
@inject
async def send_message(
    request: SendMessageRequest,
    conversation_service: ConversationService = Depends(
        Provide[Container.conversation_service]
    ),
) -> SendMessageResponse:
    """Send a message to the agent."""
    try:
        # Process feedback if provided
        if request.feedback:
            feedback_score = 1 if request.feedback.score > 0.5 else 0
            user_id = request.user_id or "default_user"
            await conversation_service.log_feedback(
                user_id,
                request.feedback.session_id,
                request.feedback.run_id,
                feedback_score,
                request.feedback.comment,
            )

        # If no prompt, this is feedback-only request
        if not request.prompt:
            if not request.feedback:
                raise HTTPException(
                    status_code=400, detail="Either prompt or feedback must be provided"
                )
            return SendMessageResponse(response="Feedback received", tools_used=[])

        # Use existing conversation or create new one
        conversation_id = request.conversation_id
        user_id = request.user_id or "default_user"
        if not conversation_id:
            conversation = await conversation_service.start_conversation(user_id)
            conversation_id = conversation.id

        message, tools_used = await conversation_service.send_message(
            conversation_id=conversation_id,
            user_id=user_id,
            content=request.prompt,
            model=request.model,
            langfuse_tags=request.langfuse_tags,
        )

        return SendMessageResponse(
            response=message.content, tools_used=tools_used, metadata=message.metadata
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process request: {str(e)}",
        )


@router.get("/users/{user_id}", response_model=list[ConversationSchema])
@inject
async def get_user_conversations(
    user_id: str,
    conversation_service: ConversationService = Depends(
        Provide[Container.conversation_service]
    ),
) -> list[ConversationSchema]:
    """Get all conversations for a user."""
    conversations = await conversation_service.get_user_conversations(user_id)
    return [_conversation_to_schema(conv) for conv in conversations]
