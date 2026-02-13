"""Domain service interfaces for LLM operations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from cx_agent_backend.domain.entities.conversation import Message


class ModelProvider(str, Enum):
    """Supported model providers."""

    BEDROCK = "bedrock"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


@dataclass(frozen=True)
class LLMRequest:
    """Request for LLM processing."""

    messages: list[Message]
    model: str
    temperature: float = 0.7
    max_tokens: int = 1000


@dataclass(frozen=True)
class LLMResponse:
    """Response from LLM processing."""

    content: str
    model: str
    usage_tokens: int
    metadata: dict[str, str]


class LLMService(ABC):
    """Abstract service for LLM operations."""

    @abstractmethod
    async def generate_response(self, request: LLMRequest) -> LLMResponse:
        """Generate response from LLM."""
        pass

    @abstractmethod
    async def stream_response(self, request: LLMRequest):
        """Stream response from LLM."""
        pass
