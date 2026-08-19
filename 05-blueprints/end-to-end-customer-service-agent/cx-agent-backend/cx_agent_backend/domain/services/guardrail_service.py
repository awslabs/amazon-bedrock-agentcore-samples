"""Domain service interface for guardrail operations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from cx_agent_backend.domain.entities.conversation import Message


class GuardrailAssessment(str, Enum):
    """Guardrail assessment result."""

    ALLOWED = "allowed"
    BLOCKED = "blocked"
    ERROR = "error"


@dataclass(frozen=True)
class GuardrailResult:
    """Result from guardrail assessment."""

    assessment: GuardrailAssessment
    blocked_categories: list[str]
    message: str


class GuardrailService(ABC):
    """Abstract service for content guardrails."""

    @abstractmethod
    async def check_input(self, message: Message) -> GuardrailResult:
        """Check user input against guardrails."""
        pass

    @abstractmethod
    async def check_output(self, message: Message) -> GuardrailResult:
        """Check AI output against guardrails."""
        pass
