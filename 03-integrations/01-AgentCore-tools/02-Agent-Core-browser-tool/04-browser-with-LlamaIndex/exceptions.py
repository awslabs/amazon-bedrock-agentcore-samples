"""
Custom exceptions for LlamaIndex-AgentCore browser tool integration.

This module defines exception classes for different error scenarios that can
occur during browser automation operations.
"""

from typing import Optional, Dict, Any
from enum import Enum


class BrowserErrorType(Enum):
    """Enumeration of browser error types."""
    NAVIGATION_FAILED = "navigation_failed"
    ELEMENT_NOT_FOUND = "element_not_found"
    TIMEOUT = "timeout"
    CAPTCHA_UNSOLVABLE = "captcha_unsolvable"
    SESSION_EXPIRED = "session_expired"
    SESSION_CREATION_FAILED = "session_creation_failed"
    AUTHENTICATION_FAILED = "authentication_failed"
    RATE_LIMITED = "rate_limited"
    NETWORK_ERROR = "network_error"
    JAVASCRIPT_ERROR = "javascript_error"
    SECURITY_VIOLATION = "security_violation"
    INVALID_SELECTOR = "invalid_selector"
    PERMISSION_DENIED = "permission_denied"
    SERVICE_UNAVAILABLE = "service_unavailable"
    CONFIGURATION_ERROR = "configuration_error"
    PARSING_ERROR = "parsing_error"
    UNKNOWN_ERROR = "unknown_error"


class AgentCoreBrowserError(Exception):
    """Base exception for all AgentCore browser tool errors."""
    
    def __init__(self, 
                 message: str,
                 error_type: Optional[BrowserErrorType] = None,
                 details: Optional[Dict[str, Any]] = None,
                 recoverable: bool = True,
                 operation: Optional[str] = None,
                 session_id: Optional[str] = None):
        """
        Initialize browser error.
        
        Args:
            message: Human-readable error message
            error_type: Type of error that occurred
            details: Additional error details and context
            recoverable: Whether the error is potentially recoverable
            operation: Name of the operation that failed
            session_id: Browser session ID if applicable
        """
        super().__init__(message)
        self.error_type = error_type or BrowserErrorType.UNKNOWN_ERROR
        self.details = details or {}
        self.recoverable = recoverable
        self.operation = operation
        self.session_id = session_id
    
    def __str__(self) -> str:
        """Return string representation of the error."""
        parts = [super().__str__()]
        
        if self.operation:
            parts.append(f"Operation: {self.operation}")
        
        if self.session_id:
            parts.append(f"Session: {self.session_id}")
        
        if self.error_type:
            parts.append(f"Type: {self.error_type.value}")
        
        if self.details:
            parts.append(f"Details: {self.details}")
        
        return " | ".join(parts)


class NavigationError(AgentCoreBrowserError):
    """Error during page navigation operations."""
    
    def __init__(self, 
                 message: str,
                 url: Optional[str] = None,
                 status_code: Optional[int] = None,
                 **kwargs):
        """
        Initialize navigation error.
        
        Args:
            message: Error message
            url: URL that failed to load
            status_code: HTTP status code if available
            **kwargs: Additional arguments for base class
        """
        details = kwargs.get('details', {})
        if url:
            details['url'] = url
        if status_code:
            details['status_code'] = status_code
        
        kwargs['details'] = details
        kwargs['error_type'] = BrowserErrorType.NAVIGATION_FAILED
        
        super().__init__(message, **kwargs)


class ElementNotFoundError(AgentCoreBrowserError):
    """Error when a web element cannot be found."""
    
    def __init__(self, 
                 message: str,
                 selector: Optional[str] = None,
                 selector_type: Optional[str] = None,
                 **kwargs):
        """
        Initialize element not found error.
        
        Args:
            message: Error message
            selector: Element selector that failed
            selector_type: Type of selector (css, xpath, etc.)
            **kwargs: Additional arguments for base class
        """
        details = kwargs.get('details', {})
        if selector:
            details['selector'] = selector
        if selector_type:
            details['selector_type'] = selector_type
        
        kwargs['details'] = details
        kwargs['error_type'] = BrowserErrorType.ELEMENT_NOT_FOUND
        
        super().__init__(message, **kwargs)


class TimeoutError(AgentCoreBrowserError):
    """Error when operations exceed timeout limits."""
    
    def __init__(self, 
                 message: str,
                 timeout_seconds: Optional[float] = None,
                 **kwargs):
        """
        Initialize timeout error.
        
        Args:
            message: Error message
            timeout_seconds: Timeout value that was exceeded
            **kwargs: Additional arguments for base class
        """
        details = kwargs.get('details', {})
        if timeout_seconds:
            details['timeout_seconds'] = timeout_seconds
        
        kwargs['details'] = details
        kwargs['error_type'] = BrowserErrorType.TIMEOUT
        kwargs['recoverable'] = True  # Timeouts are often recoverable
        
        super().__init__(message, **kwargs)


class SessionError(AgentCoreBrowserError):
    """Error related to browser session management."""
    
    def __init__(self, 
                 message: str,
                 session_status: Optional[str] = None,
                 **kwargs):
        """
        Initialize session error.
        
        Args:
            message: Error message
            session_status: Current session status
            **kwargs: Additional arguments for base class
        """
        details = kwargs.get('details', {})
        if session_status:
            details['session_status'] = session_status
        
        kwargs['details'] = details
        
        # Determine error type based on message content
        if 'expired' in message.lower():
            kwargs['error_type'] = BrowserErrorType.SESSION_EXPIRED
        elif 'creation' in message.lower() or 'create' in message.lower():
            kwargs['error_type'] = BrowserErrorType.SESSION_CREATION_FAILED
            kwargs['recoverable'] = False
        
        super().__init__(message, **kwargs)


class AuthenticationError(AgentCoreBrowserError):
    """Error during authentication with AgentCore services."""
    
    def __init__(self, message: str, **kwargs):
        """Initialize authentication error."""
        kwargs['error_type'] = BrowserErrorType.AUTHENTICATION_FAILED
        kwargs['recoverable'] = False  # Auth errors usually require manual intervention
        super().__init__(message, **kwargs)


class RateLimitError(AgentCoreBrowserError):
    """Error when rate limits are exceeded."""
    
    def __init__(self, 
                 message: str,
                 retry_after: Optional[int] = None,
                 **kwargs):
        """
        Initialize rate limit error.
        
        Args:
            message: Error message
            retry_after: Seconds to wait before retrying
            **kwargs: Additional arguments for base class
        """
        details = kwargs.get('details', {})
        if retry_after:
            details['retry_after'] = retry_after
        
        kwargs['details'] = details
        kwargs['error_type'] = BrowserErrorType.RATE_LIMITED
        kwargs['recoverable'] = True
        
        super().__init__(message, **kwargs)


class SecurityViolationError(AgentCoreBrowserError):
    """Error when security policies are violated."""
    
    def __init__(self, message: str, **kwargs):
        """Initialize security violation error."""
        kwargs['error_type'] = BrowserErrorType.SECURITY_VIOLATION
        kwargs['recoverable'] = False  # Security violations are not recoverable
        super().__init__(message, **kwargs)


class ConfigurationError(AgentCoreBrowserError):
    """Error in configuration or setup."""
    
    def __init__(self, 
                 message: str,
                 config_key: Optional[str] = None,
                 **kwargs):
        """
        Initialize configuration error.
        
        Args:
            message: Error message
            config_key: Configuration key that caused the error
            **kwargs: Additional arguments for base class
        """
        details = kwargs.get('details', {})
        if config_key:
            details['config_key'] = config_key
        
        kwargs['details'] = details
        kwargs['error_type'] = BrowserErrorType.CONFIGURATION_ERROR
        kwargs['recoverable'] = False  # Config errors require manual fix
        
        super().__init__(message, **kwargs)


class CaptchaError(AgentCoreBrowserError):
    """Error related to CAPTCHA detection or solving."""
    
    def __init__(self, 
                 message: str,
                 captcha_type: Optional[str] = None,
                 **kwargs):
        """
        Initialize CAPTCHA error.
        
        Args:
            message: Error message
            captcha_type: Type of CAPTCHA that caused the error
            **kwargs: Additional arguments for base class
        """
        details = kwargs.get('details', {})
        if captcha_type:
            details['captcha_type'] = captcha_type
        
        kwargs['details'] = details
        kwargs['error_type'] = BrowserErrorType.CAPTCHA_UNSOLVABLE
        
        super().__init__(message, **kwargs)


class ParsingError(AgentCoreBrowserError):
    """Error when parsing responses from AgentCore."""
    
    def __init__(self, 
                 message: str,
                 response_data: Optional[Dict[str, Any]] = None,
                 **kwargs):
        """
        Initialize parsing error.
        
        Args:
            message: Error message
            response_data: Raw response data that failed to parse
            **kwargs: Additional arguments for base class
        """
        details = kwargs.get('details', {})
        if response_data:
            details['response_data'] = response_data
        
        kwargs['details'] = details
        kwargs['error_type'] = BrowserErrorType.PARSING_ERROR
        kwargs['recoverable'] = False
        
        super().__init__(message, **kwargs)


class ServiceUnavailableError(AgentCoreBrowserError):
    """Error when AgentCore services are unavailable."""
    
    def __init__(self, 
                 message: str,
                 service_name: Optional[str] = None,
                 **kwargs):
        """
        Initialize service unavailable error.
        
        Args:
            message: Error message
            service_name: Name of the unavailable service
            **kwargs: Additional arguments for base class
        """
        details = kwargs.get('details', {})
        if service_name:
            details['service_name'] = service_name
        
        kwargs['details'] = details
        kwargs['error_type'] = BrowserErrorType.SERVICE_UNAVAILABLE
        kwargs['recoverable'] = True
        
        super().__init__(message, **kwargs)


# Convenience function for creating appropriate error types
def create_browser_error(error_type: BrowserErrorType, 
                        message: str,
                        **kwargs) -> AgentCoreBrowserError:
    """
    Create appropriate browser error instance based on error type.
    
    Args:
        error_type: Type of error to create
        message: Error message
        **kwargs: Additional arguments for error constructor
        
    Returns:
        Appropriate error instance
    """
    error_classes = {
        BrowserErrorType.NAVIGATION_FAILED: NavigationError,
        BrowserErrorType.ELEMENT_NOT_FOUND: ElementNotFoundError,
        BrowserErrorType.TIMEOUT: TimeoutError,
        BrowserErrorType.SESSION_EXPIRED: SessionError,
        BrowserErrorType.SESSION_CREATION_FAILED: SessionError,
        BrowserErrorType.AUTHENTICATION_FAILED: AuthenticationError,
        BrowserErrorType.RATE_LIMITED: RateLimitError,
        BrowserErrorType.SECURITY_VIOLATION: SecurityViolationError,
        BrowserErrorType.CONFIGURATION_ERROR: ConfigurationError,
        BrowserErrorType.CAPTCHA_UNSOLVABLE: CaptchaError,
        BrowserErrorType.PARSING_ERROR: ParsingError,
        BrowserErrorType.SERVICE_UNAVAILABLE: ServiceUnavailableError,
    }
    
    error_class = error_classes.get(error_type, AgentCoreBrowserError)
    return error_class(message, error_type=error_type, **kwargs)