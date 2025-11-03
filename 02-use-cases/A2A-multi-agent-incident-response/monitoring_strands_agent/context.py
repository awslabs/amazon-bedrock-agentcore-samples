from contextvars import ContextVar
from strands import Agent
from strands.tools.mcp.mcp_client import MCPClient
from strands.multiagent.a2a import A2AServer
from memory_hook import MonitoringMemoryHooks
from typing import Optional


class MonitoringAgentContext:
    """Context Manager for Monitoring Agent"""

    # Global state that persists across agent calls
    _session_id: Optional[str] = None
    _agent_identity_token: Optional[str] = None
    _gateway_url: Optional[str] = None
    _agent: Optional[Agent] = None
    _gateway_client: Optional[MCPClient] = None
    _a2a_server: Optional[A2AServer] = None
    _monitoring_hooks: Optional[MonitoringMemoryHooks] = None

    # Context variables for request-scoped state
    _session_id_ctx: ContextVar[Optional[str]] = ContextVar("session_id", default=None)
    _agent_identity_token_ctx: ContextVar[Optional[str]] = ContextVar(
        "agent_identity_token", default=None
    )
    _gateway_url_ctx: ContextVar[Optional[str]] = ContextVar(
        "gateway_url", default=None
    )
    _agent_ctx: ContextVar[Optional[Agent]] = ContextVar("agent", default=None)
    _gateway_client_ctx: ContextVar[Optional[MCPClient]] = ContextVar(
        "gateway_client", default=None
    )
    _a2a_server_ctx: ContextVar[Optional[A2AServer]] = ContextVar(
        "a2a_server", default=None
    )
    _monitoring_hooks_ctx: ContextVar[Optional[MonitoringMemoryHooks]] = ContextVar(
        "monitoring_hooks", default=None
    )

    # Session ID management
    @classmethod
    def get_session_id(cls) -> Optional[str]:
        """Get session ID from global state or context."""
        if cls._session_id:
            return cls._session_id
        try:
            return cls._session_id_ctx.get()
        except LookupError:
            return None

    @classmethod
    def set_session_id(cls, session_id: str) -> None:
        """Set session ID in both global state and context."""
        cls._session_id = session_id
        cls._session_id_ctx.set(session_id)

    # Agent identity token management
    @classmethod
    def get_agent_identity_token(cls) -> Optional[str]:
        """Get agent identity token from global state or context."""
        if cls._agent_identity_token:
            return cls._agent_identity_token
        try:
            return cls._agent_identity_token_ctx.get()
        except LookupError:
            return None

    @classmethod
    def set_agent_identity_token(cls, token: str) -> None:
        """Set agent identity token in both global state and context."""
        cls._agent_identity_token = token
        cls._agent_identity_token_ctx.set(token)

    # Gateway URL management
    @classmethod
    def get_gateway_url(cls) -> Optional[str]:
        """Get gateway URL from global state or context."""
        if cls._gateway_url:
            return cls._gateway_url
        try:
            return cls._gateway_url_ctx.get()
        except LookupError:
            return None

    @classmethod
    def set_gateway_url(cls, url: str) -> None:
        """Set gateway URL in both global state and context."""
        cls._gateway_url = url
        cls._gateway_url_ctx.set(url)

    # Agent management
    @classmethod
    def get_agent(cls) -> Optional[Agent]:
        """Get agent from global state or context."""
        if cls._agent:
            return cls._agent
        try:
            return cls._agent_ctx.get()
        except LookupError:
            return None

    @classmethod
    def set_agent(cls, agent: Agent) -> None:
        """Set agent in both global state and context."""
        cls._agent = agent
        cls._agent_ctx.set(agent)

    # Gateway client management
    @classmethod
    def get_gateway_client(cls) -> Optional[MCPClient]:
        """Get gateway client from global state or context."""
        if cls._gateway_client:
            return cls._gateway_client
        try:
            return cls._gateway_client_ctx.get()
        except LookupError:
            return None

    @classmethod
    def set_gateway_client(cls, client: MCPClient) -> None:
        """Set gateway client in both global state and context."""
        cls._gateway_client = client
        cls._gateway_client_ctx.set(client)

    # A2A server management
    @classmethod
    def get_a2a_server(cls) -> Optional[A2AServer]:
        """Get A2A server from global state or context."""
        if cls._a2a_server:
            return cls._a2a_server
        try:
            return cls._a2a_server_ctx.get()
        except LookupError:
            return None

    @classmethod
    def set_a2a_server(cls, server: A2AServer) -> None:
        """Set A2A server in both global state and context."""
        cls._a2a_server = server
        cls._a2a_server_ctx.set(server)

    # Monitoring hooks management
    @classmethod
    def get_monitoring_hooks(cls) -> Optional[MonitoringMemoryHooks]:
        """Get monitoring hooks from global state or context."""
        if cls._monitoring_hooks:
            return cls._monitoring_hooks
        try:
            return cls._monitoring_hooks_ctx.get()
        except LookupError:
            return None

    @classmethod
    def set_monitoring_hooks(cls, hooks: MonitoringMemoryHooks) -> None:
        """Set monitoring hooks in both global state and context."""
        cls._monitoring_hooks = hooks
        cls._monitoring_hooks_ctx.set(hooks)

    @classmethod
    def reset_state(cls) -> None:
        """Reset all state (used on initialization failure)."""
        cls._session_id = None
        cls._monitoring_hooks = None
        cls._agent = None
        cls._a2a_server = None
        # Note: Don't reset gateway_client, agent_identity_token, or gateway_url
        # as they may still be valid
