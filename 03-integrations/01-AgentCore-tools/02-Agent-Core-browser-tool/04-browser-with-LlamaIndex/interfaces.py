"""
Base interfaces and abstract classes for AgentCore browser tool integration.

This module defines the core interfaces that enable LlamaIndex tools to
interact with AgentCore's browser automation service.
"""

from abc import ABC, abstractmethod
from typing import Optional, Union, Any, Dict, List
from dataclasses import dataclass
from enum import Enum
import asyncio

# Python 3.12 compatible type aliases
BrowserData = Dict[str, Any]
ElementSelectorDict = Dict[str, Optional[str]]


class BrowserAction(Enum):
    """Enumeration of supported browser actions."""
    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    SCREENSHOT = "screenshot"
    EXTRACT_TEXT = "extract_text"
    WAIT_FOR_ELEMENT = "wait_for_element"
    SCROLL = "scroll"
    SUBMIT_FORM = "submit_form"
    SELECT_DROPDOWN = "select_dropdown"
    UPLOAD_FILE = "upload_file"


class SessionStatus(Enum):
    """Browser session status enumeration."""
    ACTIVE = "active"
    IDLE = "idle"
    CLOSED = "closed"
    ERROR = "error"
    CREATING = "creating"
    TERMINATING = "terminating"


@dataclass
class BrowserResponse:
    """Standardized response from AgentCore browser operations."""
    success: bool
    data: BrowserData
    error_message: Optional[str] = None
    session_id: Optional[str] = None
    timestamp: Optional[str] = None
    operation_id: Optional[str] = None
    
    def __post_init__(self):
        """Validate response data after initialization."""
        if not self.success and not self.error_message:
            raise ValueError("Failed responses must include an error message")


@dataclass
class ElementSelector:
    """Represents different ways to select web elements."""
    css_selector: Optional[str] = None
    xpath: Optional[str] = None
    text_content: Optional[str] = None
    element_id: Optional[str] = None
    class_name: Optional[str] = None
    tag_name: Optional[str] = None
    
    def __post_init__(self):
        """Validate that at least one selector is provided."""
        selectors = [
            self.css_selector, self.xpath, self.text_content,
            self.element_id, self.class_name, self.tag_name
        ]
        if not any(selectors):
            raise ValueError("At least one selector must be provided")


class IBrowserClient(ABC):
    """Abstract interface for browser client implementations."""
    
    @abstractmethod
    async def create_session(self, config: Optional[BrowserData] = None) -> str:
        """
        Create a new browser session in AgentCore.
        
        Args:
            config: Optional session configuration parameters
            
        Returns:
            Session ID string
            
        Raises:
            BrowserToolError: If session creation fails
        """
        pass
    
    @abstractmethod
    async def close_session(self, session_id: Optional[str] = None) -> BrowserResponse:
        """
        Close a browser session.
        
        Args:
            session_id: Session to close, defaults to current session
            
        Returns:
            BrowserResponse indicating success/failure
        """
        pass
    
    @abstractmethod
    async def navigate(self, 
                      url: str, 
                      wait_for_load: bool = True,
                      timeout: Optional[int] = None) -> BrowserResponse:
        """
        Navigate to a URL using AgentCore browser.
        
        Args:
            url: Target URL to navigate to
            wait_for_load: Whether to wait for page load completion
            timeout: Maximum wait time in seconds
            
        Returns:
            BrowserResponse with navigation results
        """
        pass
    
    @abstractmethod
    async def take_screenshot(self, 
                             element_selector: Optional[ElementSelector] = None,
                             full_page: bool = False) -> BrowserResponse:
        """
        Capture screenshot using AgentCore browser.
        
        Args:
            element_selector: Specific element to screenshot
            full_page: Whether to capture full page or viewport only
            
        Returns:
            BrowserResponse with screenshot data
        """
        pass
    
    @abstractmethod
    async def extract_text(self, 
                          element_selector: Optional[ElementSelector] = None) -> BrowserResponse:
        """
        Extract text content from page or specific element.
        
        Args:
            element_selector: Element to extract text from, None for full page
            
        Returns:
            BrowserResponse with extracted text
        """
        pass
    
    @abstractmethod
    async def click_element(self, 
                           element_selector: ElementSelector,
                           wait_for_response: bool = True,
                           timeout: Optional[int] = None) -> BrowserResponse:
        """
        Click an element using AgentCore browser.
        
        Args:
            element_selector: Element to click
            wait_for_response: Whether to wait for page response
            timeout: Maximum wait time in seconds
            
        Returns:
            BrowserResponse with click results
        """
        pass
    
    @abstractmethod
    async def type_text(self, 
                       element_selector: ElementSelector,
                       text: str,
                       clear_first: bool = True,
                       typing_delay: Optional[float] = None) -> BrowserResponse:
        """
        Type text into an element.
        
        Args:
            element_selector: Element to type into
            text: Text to type
            clear_first: Whether to clear existing text first
            typing_delay: Delay between keystrokes in seconds
            
        Returns:
            BrowserResponse with typing results
        """
        pass
    
    @abstractmethod
    async def wait_for_element(self, 
                              element_selector: ElementSelector,
                              timeout: int = 30,
                              visible: bool = True) -> BrowserResponse:
        """
        Wait for an element to appear or become visible.
        
        Args:
            element_selector: Element to wait for
            timeout: Maximum wait time in seconds
            visible: Whether element must be visible or just present
            
        Returns:
            BrowserResponse indicating if element was found
        """
        pass
    
    @abstractmethod
    async def get_page_info(self) -> BrowserResponse:
        """
        Get current page information (URL, title, etc.).
        
        Returns:
            BrowserResponse with page information
        """
        pass


class IToolWrapper(ABC):
    """Abstract interface for LlamaIndex tool wrappers."""
    
    def __init__(self, browser_client: IBrowserClient):
        """
        Initialize tool wrapper with browser client.
        
        Args:
            browser_client: Browser client implementation
        """
        self.browser_client = browser_client
    
    @abstractmethod
    def get_tool_metadata(self) -> BrowserData:
        """
        Get LlamaIndex tool metadata.
        
        Returns:
            Tool metadata dictionary
        """
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> BrowserData:
        """
        Execute the tool operation.
        
        Args:
            **kwargs: Tool-specific parameters
            
        Returns:
            Tool execution results
        """
        pass


class IConfigurationManager(ABC):
    """Abstract interface for configuration management."""
    
    @abstractmethod
    def load_config(self, config_path: Optional[str] = None) -> BrowserData:
        """
        Load configuration from file or environment.
        
        Args:
            config_path: Optional path to configuration file
            
        Returns:
            Configuration dictionary
        """
        pass
    
    @abstractmethod
    def validate_config(self, config: BrowserData) -> bool:
        """
        Validate configuration parameters.
        
        Args:
            config: Configuration to validate
            
        Returns:
            True if valid, raises exception if invalid
        """
        pass
    
    @abstractmethod
    def get_aws_credentials(self) -> Dict[str, str]:
        """
        Get AWS credentials for AgentCore access.
        
        Returns:
            AWS credentials dictionary
        """
        pass
    
    @abstractmethod
    def get_browser_config(self) -> BrowserData:
        """
        Get browser configuration parameters.
        
        Returns:
            Browser configuration dictionary
        """
        pass


class IErrorHandler(ABC):
    """Abstract interface for error handling."""
    
    @abstractmethod
    async def handle_error(self, 
                          error: Exception,
                          operation: str,
                          context: BrowserData) -> Optional[Any]:
        """
        Handle errors from browser operations.
        
        Args:
            error: The exception that occurred
            operation: Name of the operation that failed
            context: Additional context about the operation
            
        Returns:
            Recovery result or None if unrecoverable
        """
        pass
    
    @abstractmethod
    def is_recoverable(self, error: Exception) -> bool:
        """
        Determine if an error is recoverable.
        
        Args:
            error: The exception to check
            
        Returns:
            True if error is recoverable
        """
        pass


class IResponseParser(ABC):
    """Abstract interface for parsing AgentCore responses."""
    
    @abstractmethod
    def parse_navigation_response(self, response: BrowserData) -> BrowserData:
        """Parse navigation operation response."""
        pass
    
    @abstractmethod
    def parse_screenshot_response(self, response: BrowserData) -> BrowserData:
        """Parse screenshot operation response."""
        pass
    
    @abstractmethod
    def parse_text_extraction_response(self, response: BrowserData) -> BrowserData:
        """Parse text extraction response."""
        pass
    
    @abstractmethod
    def parse_interaction_response(self, response: BrowserData) -> BrowserData:
        """Parse element interaction response."""
        pass


# Type aliases for better code readability
BrowserClientType = Union[IBrowserClient]
ToolWrapperType = Union[IToolWrapper]
ConfigManagerType = Union[IConfigurationManager]
ErrorHandlerType = Union[IErrorHandler]
ResponseParserType = Union[IResponseParser]