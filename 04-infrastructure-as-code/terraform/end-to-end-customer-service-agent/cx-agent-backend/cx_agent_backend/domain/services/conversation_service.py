"""Domain service for conversation business logic."""

import logging
from uuid import UUID

from cx_agent_backend.domain.entities.conversation import Conversation, Message
from cx_agent_backend.domain.repositories.conversation_repository import (
    ConversationRepository,
)
from cx_agent_backend.domain.services.agent_service import (
    AgentRequest,
    AgentService,
    AgentType,
)
from cx_agent_backend.domain.services.guardrail_service import (
    GuardrailAssessment,
    GuardrailService,
)

logger = logging.getLogger(__name__)


class ConversationService:
    """Service for conversation business logic."""

    def __init__(
        self,
        conversation_repo: ConversationRepository,
        agent_service: AgentService,
        guardrail_service: GuardrailService | None = None,
    ):
        self._conversation_repo = conversation_repo
        self._agent_service = agent_service
        self._guardrail_service = guardrail_service

    async def start_conversation(self, user_id: str) -> Conversation:
        """Start a new conversation."""
        conversation = Conversation.create(user_id)
        await self._conversation_repo.save(conversation)
        return conversation

    async def send_message(
        self,
        conversation_id: UUID,
        user_id: str,
        content: str,
        model: str,
        langfuse_tags: list[str] = None,
        jwt_token: str = None,
    ) -> tuple[Message, list[str]]:
        """Send a message and get AI response."""
        # Get or create conversation
        conversation = await self._conversation_repo.get_by_id(conversation_id)
        if not conversation:
            conversation = Conversation.create(user_id, conversation_id=conversation_id)
            await self._conversation_repo.save(conversation)

        # Add user message
        user_message = Message.create_user_message(content)

        # Check input guardrails
        if self._guardrail_service:
            guardrail_result = await self._guardrail_service.check_input(user_message)
            if guardrail_result.assessment == GuardrailAssessment.BLOCKED:
                blocked_message = Message.create_assistant_message(
                    content=guardrail_result.message,
                    metadata={
                        "blocked_categories": ",".join(
                            guardrail_result.blocked_categories
                        )
                    },
                )
                conversation.add_message(user_message)
                conversation.add_message(blocked_message)
                await self._conversation_repo.save(conversation)
                return blocked_message, []

        conversation.add_message(user_message)

        # Generate AI response through agent
        agent_request = AgentRequest(
            messages=conversation.messages,
            agent_type=AgentType.CUSTOMER_SERVICE,
            user_id=user_id,
            model=model,
            session_id=str(conversation.id),
            trace_id=None,  # Can be set from FastAPI layer
            langfuse_tags=langfuse_tags or [],
            jwt_token=jwt_token,
        )
        agent_response = await self._agent_service.process_request(agent_request)

        # Create AI message with citations
        ai_metadata = {
            "agent_type": agent_response.agent_type.value,
            "tools_used": ",".join(agent_response.tools_used),
        }

        # Add citations if available
        if "citations" in agent_response.metadata:
            import json

            ai_metadata["citations"] = (
                json.dumps(agent_response.metadata["citations"])
                if isinstance(agent_response.metadata["citations"], list)
                else agent_response.metadata["citations"]
            )
        if "knowledge_base_id" in agent_response.metadata:
            ai_metadata["knowledge_base_id"] = agent_response.metadata[
                "knowledge_base_id"
            ]
        if agent_response.trace_id:
            ai_metadata["trace_id"] = agent_response.trace_id

        logger.info("AI metadata: %s", ai_metadata)

        ai_message = Message.create_assistant_message(
            content=agent_response.content,
            metadata=ai_metadata,
        )

        # Check output guardrails
        if self._guardrail_service:
            guardrail_result = await self._guardrail_service.check_output(ai_message)
            if guardrail_result.assessment == GuardrailAssessment.BLOCKED:
                ai_message = Message.create_assistant_message(
                    content=guardrail_result.message,
                    metadata={
                        "blocked_categories": ",".join(
                            guardrail_result.blocked_categories
                        )
                    },
                )

        conversation.add_message(ai_message)

        # Save conversation
        await self._conversation_repo.save(conversation)

        return ai_message, agent_response.tools_used

    async def get_conversation(self, conversation_id: UUID) -> Conversation | None:
        """Get conversation by ID."""
        return await self._conversation_repo.get_by_id(conversation_id)

    async def get_user_conversations(self, user_id: str) -> list[Conversation]:
        """Get all conversations for a user."""
        return await self._conversation_repo.get_by_user_id(user_id)

    async def log_feedback(
        self,
        user_id: str,
        session_id: str,
        message_id: str,
        score: int,
        comment: str = "",
    ) -> None:
        """Log user feedback."""
        logger.info(
            f"[FEEDBACK] Received feedback - user_id: {user_id}, session_id: {session_id}, message_id: {message_id}, score: {score}, comment: {comment}"
        )
