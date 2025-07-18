from .agent import CustomerSupport
from contextvars import ContextVar
from typing import Optional
import asyncio

# Context variables for application state
google_token_ctx: ContextVar[Optional[str]] = ContextVar("google_token", default=None)
gateway_token_ctx: ContextVar[Optional[str]] = ContextVar("gateway_token", default=None)
response_queue_ctx: ContextVar[Optional[asyncio.Queue]] = ContextVar(
    "response_queue", default=None
)
agent_ctx: ContextVar[Optional[CustomerSupport]] = ContextVar("agent", default=None)


# Helper functions
def get_google_token_ctx() -> Optional[str]:
    return google_token_ctx.get()


def set_google_token_ctx(token: str) -> None:
    google_token_ctx.set(token)


def get_response_queue_ctx() -> Optional[asyncio.Queue]:
    return response_queue_ctx.get()


def set_response_queue_ctx(queue: asyncio.Queue) -> None:
    response_queue_ctx.set(queue)


def get_gateway_token_ctx() -> Optional[str]:
    return gateway_token_ctx.get()


def set_gateway_token_ctx(token: str) -> None:
    gateway_token_ctx.set(token)


def get_agent_ctx() -> Optional[CustomerSupport]:
    return agent_ctx.get()


def set_agent_ctx(agent: CustomerSupport) -> None:
    agent_ctx.set(agent)
