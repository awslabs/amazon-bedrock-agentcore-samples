"""Structured logging configuration for agents."""

import logging
import json
import uuid
from datetime import datetime
from typing import Any, Optional


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields if present
        if hasattr(record, "agent_name"):
            log_data["agent_name"] = record.agent_name
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "event"):
            log_data["event"] = record.event
        if hasattr(record, "tool_name"):
            log_data["tool_name"] = record.tool_name
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        if hasattr(record, "error_type"):
            log_data["error_type"] = record.error_type
            
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_data)


def setup_logging(agent_name: str, level: str = "INFO", use_json: bool = True) -> logging.Logger:
    """
    Set up structured logging for an agent.
    
    Args:
        agent_name: Name of the agent
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        use_json: Whether to use JSON formatting (default: True)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(agent_name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Create console handler
    handler = logging.StreamHandler()
    
    if use_json:
        handler.setFormatter(JSONFormatter())
    else:
        # Use standard formatter for local development
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    
    return logger


def generate_request_id() -> str:
    """
    Generate a unique request ID for tracing.
    
    Returns:
        UUID string for request tracking
    """
    return str(uuid.uuid4())


def log_agent_invocation(
    logger: logging.Logger,
    agent_name: str,
    prompt: str,
    response: str,
    request_id: Optional[str] = None,
    duration_ms: Optional[float] = None
) -> None:
    """
    Log an agent invocation with structured data.
    
    Args:
        logger: Logger instance
        agent_name: Name of the agent
        prompt: User prompt
        response: Agent response
        request_id: Optional request ID for tracing
        duration_ms: Optional duration in milliseconds
    """
    extra = {
        "event": "agent_invocation",
        "agent_name": agent_name,
        "prompt_length": len(prompt),
        "response_length": len(response),
    }
    
    if request_id:
        extra["request_id"] = request_id
    
    if duration_ms is not None:
        extra["duration_ms"] = duration_ms
        
    logger.info("Agent invocation completed", extra=extra)


def log_tool_execution(
    logger: logging.Logger,
    tool_name: str,
    agent_name: str,
    request_id: Optional[str] = None,
    duration_ms: Optional[float] = None,
    success: bool = True,
    error: Optional[str] = None
) -> None:
    """
    Log a tool execution with structured data.
    
    Args:
        logger: Logger instance
        tool_name: Name of the tool executed
        agent_name: Name of the agent executing the tool
        request_id: Optional request ID for tracing
        duration_ms: Optional duration in milliseconds
        success: Whether the tool execution succeeded
        error: Optional error message if execution failed
    """
    extra = {
        "event": "tool_execution",
        "tool_name": tool_name,
        "agent_name": agent_name,
        "success": success,
    }
    
    if request_id:
        extra["request_id"] = request_id
    
    if duration_ms is not None:
        extra["duration_ms"] = duration_ms
    
    if error:
        extra["error"] = error
        extra["error_type"] = type(error).__name__ if isinstance(error, Exception) else "unknown"
    
    if success:
        logger.info(f"Tool execution completed: {tool_name}", extra=extra)
    else:
        logger.error(f"Tool execution failed: {tool_name}", extra=extra)


def log_error(
    logger: logging.Logger,
    error: Exception,
    context: str,
    agent_name: str,
    request_id: Optional[str] = None,
    **kwargs
) -> None:
    """
    Log an error with structured data and context.
    
    Args:
        logger: Logger instance
        error: The exception that occurred
        context: Context description (e.g., "tool_execution", "agent_invocation")
        agent_name: Name of the agent
        request_id: Optional request ID for tracing
        **kwargs: Additional context fields
    """
    extra = {
        "event": "error",
        "error_type": type(error).__name__,
        "error_message": str(error),
        "context": context,
        "agent_name": agent_name,
    }
    
    if request_id:
        extra["request_id"] = request_id
    
    # Add any additional context
    extra.update(kwargs)
    
    logger.error(f"Error in {context}: {str(error)}", extra=extra, exc_info=True)


def log_a2a_communication(
    logger: logging.Logger,
    event_type: str,
    agent_name: str,
    remote_agent_url: str,
    request_id: Optional[str] = None,
    success: bool = True,
    error: Optional[str] = None,
    duration_ms: Optional[float] = None,
    **kwargs
) -> None:
    """
    Log A2A communication events with structured data.
    
    Args:
        logger: Logger instance
        event_type: Type of A2A event (e.g., "message_sent", "message_received")
        agent_name: Name of the local agent
        remote_agent_url: URL of the remote agent
        request_id: Optional request ID for tracing
        success: Whether the communication succeeded
        error: Optional error message if communication failed
        duration_ms: Optional duration in milliseconds
        **kwargs: Additional context fields
    """
    extra = {
        "event": f"a2a_{event_type}",
        "agent_name": agent_name,
        "remote_agent_url": remote_agent_url,
        "success": success,
    }
    
    if request_id:
        extra["request_id"] = request_id
    
    if duration_ms is not None:
        extra["duration_ms"] = duration_ms
    
    if error:
        extra["error"] = error
        extra["error_type"] = type(error).__name__ if isinstance(error, Exception) else "unknown"
    
    # Add any additional context
    extra.update(kwargs)
    
    if success:
        logger.info(f"A2A communication {event_type}: {remote_agent_url}", extra=extra)
    else:
        logger.error(f"A2A communication {event_type} failed: {remote_agent_url}", extra=extra)
