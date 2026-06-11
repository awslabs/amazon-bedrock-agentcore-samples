# Shared utilities for agents

from .logging_config import (
    setup_logging,
    generate_request_id,
    log_agent_invocation,
    log_tool_execution,
    log_error,
    log_a2a_communication,
)

from .a2a_error_handling import (
    A2ACommunicationError,
    A2ATimeoutError,
    A2AConnectionError,
    A2AInvalidResponseError,
    A2AAgentUnavailableError,
    handle_a2a_errors,
    safe_a2a_call,
)

from .config import (
    AgentSettings,
    DeploymentConfig,
)

__all__ = [
    # Logging
    "setup_logging",
    "generate_request_id",
    "log_agent_invocation",
    "log_tool_execution",
    "log_error",
    "log_a2a_communication",
    # A2A Error Handling
    "A2ACommunicationError",
    "A2ATimeoutError",
    "A2AConnectionError",
    "A2AInvalidResponseError",
    "A2AAgentUnavailableError",
    "handle_a2a_errors",
    "safe_a2a_call",
    # Configuration
    "AgentSettings",
    "DeploymentConfig",
]
