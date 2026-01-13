"""OpenAI implementation of LLM service."""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from cx_agent_backend.domain.entities.conversation import MessageRole
from cx_agent_backend.domain.services.llm_service import (
    LLMRequest,
    LLMResponse,
    LLMService,
)


class OpenAILLMService(LLMService):
    """OpenAI implementation of LLM service."""

    def __init__(self, api_key: str, model: str, base_url: str | None = None):
        self.api_key = api_key
        self.base_url = base_url
        self.model = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=0.7,
            streaming=True,
        )

    async def generate_response(self, request: LLMRequest) -> LLMResponse:
        """Generate response using OpenAI."""
        # Convert domain messages to LangChain format
        lc_messages = []
        for msg in request.messages:
            if msg.role == MessageRole.USER:
                lc_messages.append(HumanMessage(content=msg.content))
            elif msg.role == MessageRole.ASSISTANT:
                lc_messages.append(AIMessage(content=msg.content))
            elif msg.role == MessageRole.SYSTEM:
                lc_messages.append(SystemMessage(content=msg.content))

        # Generate response
        response = await self._client.ainvoke(lc_messages)

        return LLMResponse(
            content=response.content,
            model=request.model,
            usage_tokens=response.response_metadata.get("token_usage", {}).get(
                "total_tokens", 0
            ),
            metadata=response.response_metadata,
        )

    async def stream_response(self, request: LLMRequest):
        """Stream response using OpenAI."""
        # Convert domain messages to LangChain format
        lc_messages = []
        for msg in request.messages:
            if msg.role == MessageRole.USER:
                lc_messages.append(HumanMessage(content=msg.content))
            elif msg.role == MessageRole.ASSISTANT:
                lc_messages.append(AIMessage(content=msg.content))
            elif msg.role == MessageRole.SYSTEM:
                lc_messages.append(SystemMessage(content=msg.content))

        # Stream response
        async for chunk in self._client.astream(lc_messages):
            if chunk.content:
                yield chunk.content
