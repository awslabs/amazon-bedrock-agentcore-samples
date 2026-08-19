"""Domain service interface for agent operations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

from cx_agent_backend.domain.entities.conversation import Message


class AgentType(str, Enum):
    """Supported agent types."""

    CUSTOMER_SERVICE = "customer_service"
    RESEARCH = "research"
    GENERAL = "general"


@dataclass(frozen=True)
class AgentRequest:
    """Request for agent processing."""

    messages: list[Message]
    agent_type: AgentType
    user_id: str
    model: str
    session_id: str | None = None
    trace_id: str | None = None
    langfuse_tags: list[str] = field(default_factory=list)
    jwt_token: str | None = None


@dataclass(frozen=True)
class AgentResponse:
    ("""Response from agent processing.""",)
    content: str
    agent_type: AgentType
    tools_used: list[str]
    metadata: dict[str, str]
    trace_id: str | None = None


class AgentService(ABC):
    """Abstract service for agent operations."""

    @abstractmethod
    async def process_request(self, request: AgentRequest) -> AgentResponse:
        """Process request through agent."""
        pass

    @abstractmethod
    async def stream_response(self, request: AgentRequest):
        """Stream response from agent."""
        pass
