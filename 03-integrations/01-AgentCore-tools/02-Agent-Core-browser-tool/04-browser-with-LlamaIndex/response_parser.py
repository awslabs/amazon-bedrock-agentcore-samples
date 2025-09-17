"""
Response parsing utilities for AgentCore browser tool API responses.

This module provides utilities to convert AgentCore browser tool API responses
to LlamaIndex-compatible formats and handle response validation.
"""

import base64
import json
import logging
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from dataclasses import dataclass

from interfaces import IResponseParser, BrowserResponse, BrowserData
from exceptions import ParsingError, BrowserErrorType


logger = logging.getLogger(__name__)


@dataclass
class ParsedNavigationResponse:
    """Parsed navigation response data."""
    url: str
    title: Optional[str] = None
    status_code: Optional[int] = None
    load_time_ms: Optional[int] = None
    final_url: Optional[str] = None  # After redirects
    page_source_length: Optional[int] = None
    javascript_errors: List[str] = None
    
    def __post_init__(self):
        if self.javascript_errors is None:
            self.javascript_errors = []


@dataclass
class ParsedScreenshotResponse:
    """Parsed screenshot response data."""
    image_data: bytes
    format: str = "png"
    width: Optional[int] = None
    height: Optional[int] = None
    element_bounds: Optional[Dict[str, int]] = None
    full_page: bool = False
    timestamp: Optional[str] = None


@dataclass
class ParsedTextResponse:
    """Parsed text extraction response data."""
    text: str
    element_count: Optional[int] = None
    extraction_method: str = "full_page"
    selector_used: Optional[str] = None
    text_length: Optional[int] = None
    
    def __post_init__(self):
        if self.text_length is None:
            self.text_length = len(self.text)


@dataclass
class ParsedInteractionResponse:
    """Parsed element interaction response data."""
    success: bool
    element_found: bool
    action_performed: str
    element_selector: Optional[str] = None
    element_bounds: Optional[Dict[str, int]] = None
    page_changed: bool = False
    new_url: Optional[str] = None
    response_time_ms: Optional[int] = None


class ResponseParser(IResponseParser):
    """Concrete implementation of response parser for AgentCore browser tool."""
    
    def __init__(self):
        """Initialize response parser."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def parse_navigation_response(self, response: BrowserData) -> BrowserData:
        """
        Parse navigation operation response.
        
        Args:
            response: Raw response from AgentCore browser tool
            
        Returns:
            Parsed navigation response data
            
        Raises:
            ParsingError: If response cannot be parsed
        """
        try:
            # Validate required fields
            if 'url' not in response:
                raise ParsingError("Navigation response missing required 'url' field")
            
            parsed = ParsedNavigationResponse(
                url=response['url'],
                title=response.get('title'),
                status_code=response.get('status_code'),
                load_time_ms=response.get('load_time_ms'),
                final_url=response.get('final_url'),
                page_source_length=response.get('page_source_length'),
                javascript_errors=response.get('javascript_errors', [])
            )
            
            # Convert to dictionary for LlamaIndex compatibility
            result = {
                'navigation_result': {
                    'url': parsed.url,
                    'title': parsed.title,
                    'status_code': parsed.status_code,
                    'load_time_ms': parsed.load_time_ms,
                    'final_url': parsed.final_url,
                    'page_source_length': parsed.page_source_length,
                    'javascript_errors': parsed.javascript_errors,
                    'success': parsed.status_code is None or 200 <= parsed.status_code < 400
                },
                'metadata': {
                    'operation': 'navigate',
                    'timestamp': response.get('timestamp', datetime.utcnow().isoformat()),
                    'session_id': response.get('session_id')
                }
            }
            
            self.logger.debug(f"Parsed navigation response for URL: {parsed.url}")
            return result
            
        except Exception as e:
            if isinstance(e, ParsingError):
                raise
            raise ParsingError(
                f"Failed to parse navigation response: {str(e)}",
                response_data=response
            )
    
    def parse_screenshot_response(self, response: BrowserData) -> BrowserData:
        """
        Parse screenshot operation response.
        
        Args:
            response: Raw response from AgentCore browser tool
            
        Returns:
            Parsed screenshot response data
            
        Raises:
            ParsingError: If response cannot be parsed
        """
        try:
            # Validate required fields
            if 'image_data' not in response:
                raise ParsingError("Screenshot response missing required 'image_data' field")
            
            # Handle base64 encoded image data
            image_data = response['image_data']
            if isinstance(image_data, str):
                try:
                    image_data = base64.b64decode(image_data)
                except Exception as e:
                    raise ParsingError(f"Failed to decode base64 image data: {str(e)}")
            
            parsed = ParsedScreenshotResponse(
                image_data=image_data,
                format=response.get('format', 'png'),
                width=response.get('width'),
                height=response.get('height'),
                element_bounds=response.get('element_bounds'),
                full_page=response.get('full_page', False),
                timestamp=response.get('timestamp')
            )
            
            # Convert to dictionary for LlamaIndex compatibility
            result = {
                'screenshot_result': {
                    'image_data': parsed.image_data,
                    'format': parsed.format,
                    'width': parsed.width,
                    'height': parsed.height,
                    'element_bounds': parsed.element_bounds,
                    'full_page': parsed.full_page,
                    'image_size_bytes': len(parsed.image_data),
                    'success': True
                },
                'metadata': {
                    'operation': 'screenshot',
                    'timestamp': parsed.timestamp or datetime.utcnow().isoformat(),
                    'session_id': response.get('session_id')
                }
            }
            
            self.logger.debug(f"Parsed screenshot response: {parsed.format} {parsed.width}x{parsed.height}")
            return result
            
        except Exception as e:
            if isinstance(e, ParsingError):
                raise
            raise ParsingError(
                f"Failed to parse screenshot response: {str(e)}",
                response_data=response
            )
    
    def parse_text_extraction_response(self, response: BrowserData) -> BrowserData:
        """
        Parse text extraction response.
        
        Args:
            response: Raw response from AgentCore browser tool
            
        Returns:
            Parsed text extraction response data
            
        Raises:
            ParsingError: If response cannot be parsed
        """
        try:
            # Validate required fields
            if 'text' not in response:
                raise ParsingError("Text extraction response missing required 'text' field")
            
            text = response['text']
            if not isinstance(text, str):
                text = str(text)
            
            parsed = ParsedTextResponse(
                text=text,
                element_count=response.get('element_count'),
                extraction_method=response.get('extraction_method', 'full_page'),
                selector_used=response.get('selector_used'),
                text_length=len(text)
            )
            
            # Convert to dictionary for LlamaIndex compatibility
            result = {
                'text_extraction_result': {
                    'text': parsed.text,
                    'text_length': parsed.text_length,
                    'element_count': parsed.element_count,
                    'extraction_method': parsed.extraction_method,
                    'selector_used': parsed.selector_used,
                    'success': True,
                    'has_content': len(parsed.text.strip()) > 0
                },
                'metadata': {
                    'operation': 'extract_text',
                    'timestamp': response.get('timestamp', datetime.utcnow().isoformat()),
                    'session_id': response.get('session_id')
                }
            }
            
            self.logger.debug(f"Parsed text extraction response: {parsed.text_length} characters")
            return result
            
        except Exception as e:
            if isinstance(e, ParsingError):
                raise
            raise ParsingError(
                f"Failed to parse text extraction response: {str(e)}",
                response_data=response
            )
    
    def parse_interaction_response(self, response: BrowserData) -> BrowserData:
        """
        Parse element interaction response.
        
        Args:
            response: Raw response from AgentCore browser tool
            
        Returns:
            Parsed interaction response data
            
        Raises:
            ParsingError: If response cannot be parsed
        """
        try:
            # Determine success from response
            success = response.get('success', True)
            element_found = response.get('element_found', success)
            
            parsed = ParsedInteractionResponse(
                success=success,
                element_found=element_found,
                action_performed=response.get('action_performed', 'unknown'),
                element_selector=response.get('element_selector'),
                element_bounds=response.get('element_bounds'),
                page_changed=response.get('page_changed', False),
                new_url=response.get('new_url'),
                response_time_ms=response.get('response_time_ms')
            )
            
            # Convert to dictionary for LlamaIndex compatibility
            result = {
                'interaction_result': {
                    'success': parsed.success,
                    'element_found': parsed.element_found,
                    'action_performed': parsed.action_performed,
                    'element_selector': parsed.element_selector,
                    'element_bounds': parsed.element_bounds,
                    'page_changed': parsed.page_changed,
                    'new_url': parsed.new_url,
                    'response_time_ms': parsed.response_time_ms
                },
                'metadata': {
                    'operation': parsed.action_performed,
                    'timestamp': response.get('timestamp', datetime.utcnow().isoformat()),
                    'session_id': response.get('session_id')
                }
            }
            
            self.logger.debug(f"Parsed interaction response: {parsed.action_performed} success={parsed.success}")
            return result
            
        except Exception as e:
            if isinstance(e, ParsingError):
                raise
            raise ParsingError(
                f"Failed to parse interaction response: {str(e)}",
                response_data=response
            )
    
    def parse_session_response(self, response: BrowserData) -> BrowserData:
        """
        Parse session management response.
        
        Args:
            response: Raw response from AgentCore browser tool
            
        Returns:
            Parsed session response data
            
        Raises:
            ParsingError: If response cannot be parsed
        """
        try:
            result = {
                'session_result': {
                    'session_id': response.get('session_id'),
                    'status': response.get('status'),
                    'created_at': response.get('created_at'),
                    'last_activity': response.get('last_activity'),
                    'config': response.get('config', {}),
                    'success': response.get('success', True)
                },
                'metadata': {
                    'operation': 'session_management',
                    'timestamp': response.get('timestamp', datetime.utcnow().isoformat())
                }
            }
            
            self.logger.debug(f"Parsed session response: {response.get('session_id')}")
            return result
            
        except Exception as e:
            raise ParsingError(
                f"Failed to parse session response: {str(e)}",
                response_data=response
            )
    
    def parse_error_response(self, response: BrowserData) -> BrowserData:
        """
        Parse error response from AgentCore browser tool.
        
        Args:
            response: Raw error response
            
        Returns:
            Parsed error response data
        """
        try:
            result = {
                'error_result': {
                    'error_type': response.get('error_type', 'unknown_error'),
                    'message': response.get('message', 'Unknown error occurred'),
                    'details': response.get('details', {}),
                    'recoverable': response.get('recoverable', True),
                    'retry_after': response.get('retry_after'),
                    'operation': response.get('operation'),
                    'session_id': response.get('session_id')
                },
                'metadata': {
                    'operation': 'error_handling',
                    'timestamp': response.get('timestamp', datetime.utcnow().isoformat())
                }
            }
            
            self.logger.debug(f"Parsed error response: {response.get('error_type')}")
            return result
            
        except Exception as e:
            # If we can't parse the error response, create a minimal one
            return {
                'error_result': {
                    'error_type': 'parsing_error',
                    'message': f'Failed to parse error response: {str(e)}',
                    'details': {'original_response': response},
                    'recoverable': False
                },
                'metadata': {
                    'operation': 'error_handling',
                    'timestamp': datetime.utcnow().isoformat()
                }
            }
    
    def validate_response_structure(self, response: BrowserData, required_fields: List[str]) -> bool:
        """
        Validate that response contains required fields.
        
        Args:
            response: Response to validate
            required_fields: List of required field names
            
        Returns:
            True if valid
            
        Raises:
            ParsingError: If validation fails
        """
        missing_fields = []
        for field in required_fields:
            if field not in response:
                missing_fields.append(field)
        
        if missing_fields:
            raise ParsingError(
                f"Response missing required fields: {missing_fields}",
                response_data=response
            )
        
        return True
    
    def sanitize_response_data(self, response: BrowserData) -> BrowserData:
        """
        Sanitize response data to remove sensitive information.
        
        Args:
            response: Response to sanitize
            
        Returns:
            Sanitized response data
        """
        # Create a copy to avoid modifying original
        sanitized = response.copy()
        
        # Remove or mask sensitive fields
        sensitive_fields = ['credentials', 'tokens', 'passwords', 'api_keys']
        for field in sensitive_fields:
            if field in sanitized:
                sanitized[field] = '[REDACTED]'
        
        # Truncate very long text fields
        if 'text' in sanitized and isinstance(sanitized['text'], str):
            if len(sanitized['text']) > 10000:  # 10KB limit
                sanitized['text'] = sanitized['text'][:10000] + '... [TRUNCATED]'
                sanitized['text_truncated'] = True
        
        return sanitized