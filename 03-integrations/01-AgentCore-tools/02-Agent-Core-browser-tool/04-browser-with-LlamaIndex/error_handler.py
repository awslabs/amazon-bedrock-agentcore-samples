"""
Error handling and retry mechanisms for AgentCore browser tool integration.

This module provides comprehensive error handling, retry logic, and recovery
strategies for different types of browser tool failures.
"""

import asyncio
import random
import logging
from typing import Dict, Any, Optional, Callable, List, Type
from datetime import datetime, timedelta
from functools import wraps
from dataclasses import dataclass

from interfaces import IErrorHandler, BrowserData
from exceptions import (
    AgentCoreBrowserError, BrowserErrorType, NavigationError, ElementNotFoundError,
    TimeoutError, SessionError, AuthenticationError, RateLimitError,
    SecurityViolationError, ConfigurationError, CaptchaError, ParsingError,
    ServiceUnavailableError, create_browser_error
)


logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_errors: List[BrowserErrorType] = None
    
    def __post_init__(self):
        if self.retryable_errors is None:
            self.retryable_errors = [
                BrowserErrorType.TIMEOUT,
                BrowserErrorType.NETWORK_ERROR,
                BrowserErrorType.RATE_LIMITED,
                BrowserErrorType.SERVICE_UNAVAILABLE,
                BrowserErrorType.SESSION_EXPIRED
            ]


@dataclass
class RecoveryStrategy:
    """Recovery strategy for specific error types."""
    error_type: BrowserErrorType
    strategy_func: Callable
    max_recovery_attempts: int = 1
    recovery_delay: float = 0.0
    requires_session_reset: bool = False


class ErrorHandler(IErrorHandler):
    """Comprehensive error handler for AgentCore browser tool operations."""
    
    def __init__(self, retry_config: Optional[RetryConfig] = None):
        """
        Initialize error handler.
        
        Args:
            retry_config: Configuration for retry behavior
        """
        self.retry_config = retry_config or RetryConfig()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Initialize recovery strategies
        self._recovery_strategies = self._initialize_recovery_strategies()
        
        # Track error statistics
        self._error_stats: Dict[str, int] = {}
        self._recovery_stats: Dict[str, int] = {}
    
    def _initialize_recovery_strategies(self) -> Dict[BrowserErrorType, RecoveryStrategy]:
        """Initialize recovery strategies for different error types."""
        return {
            BrowserErrorType.TIMEOUT: RecoveryStrategy(
                error_type=BrowserErrorType.TIMEOUT,
                strategy_func=self._recover_from_timeout,
                max_recovery_attempts=2,
                recovery_delay=1.0
            ),
            BrowserErrorType.ELEMENT_NOT_FOUND: RecoveryStrategy(
                error_type=BrowserErrorType.ELEMENT_NOT_FOUND,
                strategy_func=self._recover_from_element_not_found,
                max_recovery_attempts=3,
                recovery_delay=0.5
            ),
            BrowserErrorType.SESSION_EXPIRED: RecoveryStrategy(
                error_type=BrowserErrorType.SESSION_EXPIRED,
                strategy_func=self._recover_from_session_expired,
                max_recovery_attempts=1,
                recovery_delay=0.0,
                requires_session_reset=True
            ),
            BrowserErrorType.RATE_LIMITED: RecoveryStrategy(
                error_type=BrowserErrorType.RATE_LIMITED,
                strategy_func=self._recover_from_rate_limit,
                max_recovery_attempts=1,
                recovery_delay=0.0
            ),
            BrowserErrorType.NAVIGATION_FAILED: RecoveryStrategy(
                error_type=BrowserErrorType.NAVIGATION_FAILED,
                strategy_func=self._recover_from_navigation_failed,
                max_recovery_attempts=2,
                recovery_delay=1.0
            ),
            BrowserErrorType.NETWORK_ERROR: RecoveryStrategy(
                error_type=BrowserErrorType.NETWORK_ERROR,
                strategy_func=self._recover_from_network_error,
                max_recovery_attempts=3,
                recovery_delay=2.0
            ),
            BrowserErrorType.SERVICE_UNAVAILABLE: RecoveryStrategy(
                error_type=BrowserErrorType.SERVICE_UNAVAILABLE,
                strategy_func=self._recover_from_service_unavailable,
                max_recovery_attempts=2,
                recovery_delay=5.0
            )
        }
    
    async def handle_error(self, 
                          error: Exception,
                          operation: str,
                          context: BrowserData) -> Optional[Any]:
        """
        Handle errors from browser operations with appropriate recovery strategies.
        
        Args:
            error: The exception that occurred
            operation: Name of the operation that failed
            context: Additional context about the operation
            
        Returns:
            Recovery result or None if unrecoverable
            
        Raises:
            AgentCoreBrowserError: If error cannot be recovered
        """
        # Track error statistics
        error_type = self._get_error_type(error)
        self._error_stats[error_type.value] = self._error_stats.get(error_type.value, 0) + 1
        
        self.logger.warning(f"Handling error in operation '{operation}': {error}")
        
        # Check if error is recoverable
        if not self.is_recoverable(error):
            self.logger.error(f"Error is not recoverable: {error}")
            raise error
        
        # Get recovery strategy
        strategy = self._recovery_strategies.get(error_type)
        if not strategy:
            self.logger.warning(f"No recovery strategy for error type: {error_type}")
            raise error
        
        # Attempt recovery
        try:
            recovery_result = await self._attempt_recovery(error, strategy, operation, context)
            
            # Track successful recovery
            self._recovery_stats[error_type.value] = self._recovery_stats.get(error_type.value, 0) + 1
            
            self.logger.info(f"Successfully recovered from {error_type.value} in operation '{operation}'")
            return recovery_result
            
        except Exception as recovery_error:
            self.logger.error(f"Recovery failed for {error_type.value}: {recovery_error}")
            # Re-raise original error if recovery fails
            raise error
    
    def is_recoverable(self, error: Exception) -> bool:
        """
        Determine if an error is recoverable.
        
        Args:
            error: The exception to check
            
        Returns:
            True if error is recoverable
        """
        if isinstance(error, AgentCoreBrowserError):
            return error.recoverable
        
        # Non-browser errors are generally not recoverable
        return False
    
    async def _attempt_recovery(self, 
                               error: Exception,
                               strategy: RecoveryStrategy,
                               operation: str,
                               context: BrowserData) -> Optional[Any]:
        """Attempt recovery using the specified strategy."""
        for attempt in range(strategy.max_recovery_attempts):
            try:
                if strategy.recovery_delay > 0:
                    await asyncio.sleep(strategy.recovery_delay)
                
                self.logger.debug(f"Recovery attempt {attempt + 1}/{strategy.max_recovery_attempts} for {strategy.error_type.value}")
                
                result = await strategy.strategy_func(error, operation, context)
                return result
                
            except Exception as e:
                if attempt == strategy.max_recovery_attempts - 1:
                    raise e
                
                self.logger.warning(f"Recovery attempt {attempt + 1} failed: {e}")
                continue
        
        return None
    
    def _get_error_type(self, error: Exception) -> BrowserErrorType:
        """Get error type from exception."""
        if isinstance(error, AgentCoreBrowserError):
            return error.error_type
        
        # Map standard exceptions to browser error types
        if isinstance(error, TimeoutError):
            return BrowserErrorType.TIMEOUT
        elif isinstance(error, ConnectionError):
            return BrowserErrorType.NETWORK_ERROR
        else:
            return BrowserErrorType.UNKNOWN_ERROR
    
    # Recovery strategy implementations
    
    async def _recover_from_timeout(self, 
                                   error: Exception,
                                   operation: str,
                                   context: BrowserData) -> Optional[Any]:
        """Recover from timeout errors by extending timeout and retrying."""
        self.logger.debug("Attempting timeout recovery")
        
        # Extend timeout for next attempt
        if 'timeout' in context:
            context['timeout'] = min(context['timeout'] * 1.5, 120)  # Max 2 minutes
        
        # Wait a bit before retry
        await asyncio.sleep(2.0)
        
        return {'recovery_action': 'timeout_extended', 'new_timeout': context.get('timeout')}
    
    async def _recover_from_element_not_found(self, 
                                            error: Exception,
                                            operation: str,
                                            context: BrowserData) -> Optional[Any]:
        """Recover from element not found errors by waiting and retrying."""
        self.logger.debug("Attempting element not found recovery")
        
        # Wait for page to stabilize
        await asyncio.sleep(1.0)
        
        # Try alternative selectors if available
        if 'alternative_selectors' in context:
            return {'recovery_action': 'try_alternative_selectors'}
        
        return {'recovery_action': 'wait_and_retry'}
    
    async def _recover_from_session_expired(self, 
                                          error: Exception,
                                          operation: str,
                                          context: BrowserData) -> Optional[Any]:
        """Recover from session expired errors by creating new session."""
        self.logger.debug("Attempting session expired recovery")
        
        return {
            'recovery_action': 'create_new_session',
            'requires_session_reset': True
        }
    
    async def _recover_from_rate_limit(self, 
                                     error: Exception,
                                     operation: str,
                                     context: BrowserData) -> Optional[Any]:
        """Recover from rate limit errors by waiting."""
        self.logger.debug("Attempting rate limit recovery")
        
        # Extract retry_after from error if available
        retry_after = 60  # Default 1 minute
        if isinstance(error, RateLimitError) and 'retry_after' in error.details:
            retry_after = error.details['retry_after']
        
        self.logger.info(f"Rate limited, waiting {retry_after} seconds")
        await asyncio.sleep(retry_after)
        
        return {'recovery_action': 'rate_limit_wait', 'waited_seconds': retry_after}
    
    async def _recover_from_navigation_failed(self, 
                                            error: Exception,
                                            operation: str,
                                            context: BrowserData) -> Optional[Any]:
        """Recover from navigation failures."""
        self.logger.debug("Attempting navigation failure recovery")
        
        # Wait before retry
        await asyncio.sleep(2.0)
        
        # Try with different wait conditions
        return {
            'recovery_action': 'retry_navigation',
            'modified_params': {'wait_for_load': True, 'timeout': 60}
        }
    
    async def _recover_from_network_error(self, 
                                        error: Exception,
                                        operation: str,
                                        context: BrowserData) -> Optional[Any]:
        """Recover from network errors."""
        self.logger.debug("Attempting network error recovery")
        
        # Exponential backoff for network issues
        delay = min(2.0 ** context.get('retry_attempt', 1), 30.0)
        await asyncio.sleep(delay)
        
        return {'recovery_action': 'network_retry', 'delay_seconds': delay}
    
    async def _recover_from_service_unavailable(self, 
                                              error: Exception,
                                              operation: str,
                                              context: BrowserData) -> Optional[Any]:
        """Recover from service unavailable errors."""
        self.logger.debug("Attempting service unavailable recovery")
        
        # Wait longer for service to recover
        await asyncio.sleep(10.0)
        
        return {'recovery_action': 'service_retry', 'delay_seconds': 10.0}
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error and recovery statistics."""
        return {
            'error_counts': self._error_stats.copy(),
            'recovery_counts': self._recovery_stats.copy(),
            'total_errors': sum(self._error_stats.values()),
            'total_recoveries': sum(self._recovery_stats.values()),
            'recovery_rate': (
                sum(self._recovery_stats.values()) / sum(self._error_stats.values())
                if sum(self._error_stats.values()) > 0 else 0.0
            )
        }
    
    def reset_statistics(self):
        """Reset error and recovery statistics."""
        self._error_stats.clear()
        self._recovery_stats.clear()


def retry_browser_operation(retry_config: Optional[RetryConfig] = None):
    """
    Decorator for retrying browser operations with exponential backoff.
    
    Args:
        retry_config: Configuration for retry behavior
        
    Returns:
        Decorated function with retry logic
    """
    config = retry_config or RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                    
                except Exception as e:
                    last_exception = e
                    
                    # Check if error is retryable
                    if isinstance(e, AgentCoreBrowserError):
                        if e.error_type not in config.retryable_errors:
                            raise e
                        if not e.recoverable:
                            raise e
                    else:
                        # Non-browser errors are generally not retryable
                        raise e
                    
                    # Don't retry on last attempt
                    if attempt == config.max_attempts - 1:
                        raise e
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        config.base_delay * (config.exponential_base ** attempt),
                        config.max_delay
                    )
                    
                    # Add jitter to prevent thundering herd
                    if config.jitter:
                        delay *= (0.5 + random.random() * 0.5)
                    
                    logger.debug(f"Retrying {func.__name__} in {delay:.2f}s (attempt {attempt + 1}/{config.max_attempts})")
                    await asyncio.sleep(delay)
            
            # This should never be reached, but just in case
            raise last_exception
        
        return wrapper
    return decorator


class CircuitBreaker:
    """Circuit breaker pattern for preventing cascading failures."""
    
    def __init__(self, 
                 failure_threshold: int = 5,
                 recovery_timeout: float = 60.0,
                 expected_exception: Type[Exception] = AgentCoreBrowserError):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time to wait before attempting recovery
            expected_exception: Exception type to monitor
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = 'closed'  # closed, open, half-open
        
        self.logger = logging.getLogger(f"{__name__}.CircuitBreaker")
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Call function through circuit breaker.
        
        Args:
            func: Function to call
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If circuit is open or function fails
        """
        if self.state == 'open':
            if self._should_attempt_reset():
                self.state = 'half-open'
                self.logger.info("Circuit breaker moving to half-open state")
            else:
                raise ServiceUnavailableError(
                    "Circuit breaker is open - service unavailable",
                    service_name="browser_tool"
                )
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if not self.last_failure_time:
            return True
        
        return (datetime.utcnow() - self.last_failure_time).total_seconds() >= self.recovery_timeout
    
    def _on_success(self):
        """Handle successful operation."""
        if self.state == 'half-open':
            self.state = 'closed'
            self.failure_count = 0
            self.logger.info("Circuit breaker reset to closed state")
    
    def _on_failure(self):
        """Handle failed operation."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'open'
            self.logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state."""
        return {
            'state': self.state,
            'failure_count': self.failure_count,
            'failure_threshold': self.failure_threshold,
            'last_failure_time': self.last_failure_time.isoformat() if self.last_failure_time else None,
            'recovery_timeout': self.recovery_timeout
        }