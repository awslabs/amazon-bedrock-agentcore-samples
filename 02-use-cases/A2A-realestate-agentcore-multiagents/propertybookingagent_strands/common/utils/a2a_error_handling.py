"""A2A communication error handling utilities."""

import httpx
from typing import Any, Optional, Callable
import logging
from functools import wraps
import time

from .logging_config import log_error, log_a2a_communication, generate_request_id


class A2ACommunicationError(Exception):
    """Base exception for A2A communication errors."""
    pass


class A2ATimeoutError(A2ACommunicationError):
    """Exception raised when A2A communication times out."""
    pass


class A2AConnectionError(A2ACommunicationError):
    """Exception raised when connection to remote agent fails."""
    pass


class A2AInvalidResponseError(A2ACommunicationError):
    """Exception raised when remote agent returns invalid response."""
    pass


class A2AAgentUnavailableError(A2ACommunicationError):
    """Exception raised when remote agent is unavailable."""
    pass


def handle_a2a_errors(
    logger: logging.Logger,
    agent_name: str,
    remote_agent_url: str,
    request_id: Optional[str] = None
):
    """
    Decorator to handle A2A communication errors with proper logging.
    
    Args:
        logger: Logger instance
        agent_name: Name of the local agent
        remote_agent_url: URL of the remote agent
        request_id: Optional request ID for tracing
    
    Returns:
        Decorated function with error handling
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            req_id = request_id or generate_request_id()
            
            try:
                log_a2a_communication(
                    logger,
                    event_type="request_start",
                    agent_name=agent_name,
                    remote_agent_url=remote_agent_url,
                    request_id=req_id
                )
                
                result = await func(*args, **kwargs)
                
                duration_ms = (time.time() - start_time) * 1000
                log_a2a_communication(
                    logger,
                    event_type="request_complete",
                    agent_name=agent_name,
                    remote_agent_url=remote_agent_url,
                    request_id=req_id,
                    duration_ms=duration_ms,
                    success=True
                )
                
                return result
                
            except httpx.TimeoutException as e:
                duration_ms = (time.time() - start_time) * 1000
                log_error(
                    logger,
                    error=e,
                    context="a2a_communication",
                    agent_name=agent_name,
                    request_id=req_id,
                    remote_agent_url=remote_agent_url,
                    error_type="timeout",
                    duration_ms=duration_ms
                )
                raise A2ATimeoutError(
                    f"Timeout communicating with agent at {remote_agent_url}"
                ) from e
                
            except httpx.ConnectError as e:
                duration_ms = (time.time() - start_time) * 1000
                log_error(
                    logger,
                    error=e,
                    context="a2a_communication",
                    agent_name=agent_name,
                    request_id=req_id,
                    remote_agent_url=remote_agent_url,
                    error_type="connection_error",
                    duration_ms=duration_ms
                )
                raise A2AConnectionError(
                    f"Failed to connect to agent at {remote_agent_url}"
                ) from e
                
            except httpx.HTTPStatusError as e:
                duration_ms = (time.time() - start_time) * 1000
                status_code = e.response.status_code
                
                log_error(
                    logger,
                    error=e,
                    context="a2a_communication",
                    agent_name=agent_name,
                    request_id=req_id,
                    remote_agent_url=remote_agent_url,
                    error_type="http_error",
                    status_code=status_code,
                    duration_ms=duration_ms
                )
                
                if status_code >= 500:
                    raise A2AAgentUnavailableError(
                        f"Agent at {remote_agent_url} is unavailable (HTTP {status_code})"
                    ) from e
                else:
                    raise A2AInvalidResponseError(
                        f"Invalid response from agent at {remote_agent_url} (HTTP {status_code})"
                    ) from e
                    
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                log_error(
                    logger,
                    error=e,
                    context="a2a_communication",
                    agent_name=agent_name,
                    request_id=req_id,
                    remote_agent_url=remote_agent_url,
                    duration_ms=duration_ms
                )
                raise A2ACommunicationError(
                    f"Error communicating with agent at {remote_agent_url}: {str(e)}"
                ) from e
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            req_id = request_id or generate_request_id()
            
            try:
                log_a2a_communication(
                    logger,
                    event_type="request_start",
                    agent_name=agent_name,
                    remote_agent_url=remote_agent_url,
                    request_id=req_id
                )
                
                result = func(*args, **kwargs)
                
                duration_ms = (time.time() - start_time) * 1000
                log_a2a_communication(
                    logger,
                    event_type="request_complete",
                    agent_name=agent_name,
                    remote_agent_url=remote_agent_url,
                    request_id=req_id,
                    duration_ms=duration_ms,
                    success=True
                )
                
                return result
                
            except httpx.TimeoutException as e:
                duration_ms = (time.time() - start_time) * 1000
                log_error(
                    logger,
                    error=e,
                    context="a2a_communication",
                    agent_name=agent_name,
                    request_id=req_id,
                    remote_agent_url=remote_agent_url,
                    error_type="timeout",
                    duration_ms=duration_ms
                )
                raise A2ATimeoutError(
                    f"Timeout communicating with agent at {remote_agent_url}"
                ) from e
                
            except httpx.ConnectError as e:
                duration_ms = (time.time() - start_time) * 1000
                log_error(
                    logger,
                    error=e,
                    context="a2a_communication",
                    agent_name=agent_name,
                    request_id=req_id,
                    remote_agent_url=remote_agent_url,
                    error_type="connection_error",
                    duration_ms=duration_ms
                )
                raise A2AConnectionError(
                    f"Failed to connect to agent at {remote_agent_url}"
                ) from e
                
            except httpx.HTTPStatusError as e:
                duration_ms = (time.time() - start_time) * 1000
                status_code = e.response.status_code
                
                log_error(
                    logger,
                    error=e,
                    context="a2a_communication",
                    agent_name=agent_name,
                    request_id=req_id,
                    remote_agent_url=remote_agent_url,
                    error_type="http_error",
                    status_code=status_code,
                    duration_ms=duration_ms
                )
                
                if status_code >= 500:
                    raise A2AAgentUnavailableError(
                        f"Agent at {remote_agent_url} is unavailable (HTTP {status_code})"
                    ) from e
                else:
                    raise A2AInvalidResponseError(
                        f"Invalid response from agent at {remote_agent_url} (HTTP {status_code})"
                    ) from e
                    
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                log_error(
                    logger,
                    error=e,
                    context="a2a_communication",
                    agent_name=agent_name,
                    request_id=req_id,
                    remote_agent_url=remote_agent_url,
                    duration_ms=duration_ms
                )
                raise A2ACommunicationError(
                    f"Error communicating with agent at {remote_agent_url}: {str(e)}"
                ) from e
        
        # Return appropriate wrapper based on function type
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def safe_a2a_call(
    func: Callable,
    logger: logging.Logger,
    agent_name: str,
    remote_agent_url: str,
    fallback_message: str = "The remote agent is currently unavailable. Please try again later.",
    request_id: Optional[str] = None,
    *args,
    **kwargs
) -> Any:
    """
    Safely execute an A2A call with error handling and fallback.
    
    Args:
        func: Function to execute
        logger: Logger instance
        agent_name: Name of the local agent
        remote_agent_url: URL of the remote agent
        fallback_message: Message to return on error
        request_id: Optional request ID for tracing
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func
    
    Returns:
        Result from func or fallback message on error
    """
    start_time = time.time()
    req_id = request_id or generate_request_id()
    
    try:
        log_a2a_communication(
            logger,
            event_type="request_start",
            agent_name=agent_name,
            remote_agent_url=remote_agent_url,
            request_id=req_id
        )
        
        result = func(*args, **kwargs)
        
        duration_ms = (time.time() - start_time) * 1000
        log_a2a_communication(
            logger,
            event_type="request_complete",
            agent_name=agent_name,
            remote_agent_url=remote_agent_url,
            request_id=req_id,
            duration_ms=duration_ms,
            success=True
        )
        
        return result
        
    except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as e:
        duration_ms = (time.time() - start_time) * 1000
        
        error_type = "timeout" if isinstance(e, httpx.TimeoutException) else \
                     "connection_error" if isinstance(e, httpx.ConnectError) else \
                     "http_error"
        
        log_error(
            logger,
            error=e,
            context="a2a_communication",
            agent_name=agent_name,
            request_id=req_id,
            remote_agent_url=remote_agent_url,
            error_type=error_type,
            duration_ms=duration_ms
        )
        
        return fallback_message
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(
            logger,
            error=e,
            context="a2a_communication",
            agent_name=agent_name,
            request_id=req_id,
            remote_agent_url=remote_agent_url,
            duration_ms=duration_ms
        )
        
        return fallback_message
