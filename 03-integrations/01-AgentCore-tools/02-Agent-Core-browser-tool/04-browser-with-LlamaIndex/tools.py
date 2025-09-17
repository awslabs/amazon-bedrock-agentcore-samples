"""
LlamaIndex tool implementations for AgentCore browser integration.

This module provides LlamaIndex BaseTool implementations that wrap AgentCore
browser functionality, enabling intelligent agents to perform web automation
tasks through the managed AgentCore browser service.
"""

import asyncio
import base64
import json
import logging
from typing import Dict, Any, Optional, List, Union
from datetime import datetime

# LlamaIndex imports
try:
    from llama_index.core.tools import BaseTool
    from llama_index.core.tools.types import ToolMetadata, ToolOutput
    from pydantic import BaseModel, Field
except ImportError as e:
    raise ImportError(
        "LlamaIndex is required for this integration. "
        "Install with: pip install llama-index-core"
    ) from e

# Local imports
from interfaces import IBrowserClient, BrowserResponse, ElementSelector
from exceptions import AgentCoreBrowserError, NavigationError, ElementNotFoundError


logger = logging.getLogger(__name__)


# Pydantic schemas for tool inputs
class NavigationSchema(BaseModel):
    """Schema for browser navigation tool input."""
    url: str = Field(description="URL to navigate to")
    wait_for_load: bool = Field(
        default=True, 
        description="Whether to wait for page load completion"
    )
    timeout: Optional[int] = Field(
        default=None,
        description="Maximum wait time in seconds"
    )


class TextExtractionSchema(BaseModel):
    """Schema for text extraction tool input."""
    css_selector: Optional[str] = Field(
        default=None,
        description="CSS selector for specific element"
    )
    xpath: Optional[str] = Field(
        default=None,
        description="XPath selector for specific element"
    )
    element_id: Optional[str] = Field(
        default=None,
        description="Element ID to extract text from"
    )
    text_content: Optional[str] = Field(
        default=None,
        description="Text content to match element by"
    )


class ScreenshotSchema(BaseModel):
    """Schema for screenshot tool input."""
    css_selector: Optional[str] = Field(
        default=None,
        description="CSS selector for specific element to screenshot"
    )
    xpath: Optional[str] = Field(
        default=None,
        description="XPath selector for specific element"
    )
    element_id: Optional[str] = Field(
        default=None,
        description="Element ID to screenshot"
    )
    full_page: bool = Field(
        default=False,
        description="Whether to capture full page or viewport only"
    )


class ElementClickSchema(BaseModel):
    """Schema for element click tool input."""
    css_selector: Optional[str] = Field(
        default=None,
        description="CSS selector for element to click"
    )
    xpath: Optional[str] = Field(
        default=None,
        description="XPath selector for element to click"
    )
    element_id: Optional[str] = Field(
        default=None,
        description="Element ID to click"
    )
    text_content: Optional[str] = Field(
        default=None,
        description="Text content to match element by"
    )
    wait_for_response: bool = Field(
        default=True,
        description="Whether to wait for page response after click"
    )
    timeout: Optional[int] = Field(
        default=None,
        description="Maximum wait time in seconds"
    )


class FormInteractionSchema(BaseModel):
    """Schema for form interaction tool input."""
    css_selector: Optional[str] = Field(
        default=None,
        description="CSS selector for form element"
    )
    xpath: Optional[str] = Field(
        default=None,
        description="XPath selector for form element"
    )
    element_id: Optional[str] = Field(
        default=None,
        description="Element ID for form field"
    )
    text: str = Field(description="Text to type into the form field")
    clear_first: bool = Field(
        default=True,
        description="Whether to clear existing text first"
    )
    typing_delay: Optional[float] = Field(
        default=None,
        description="Delay between keystrokes in seconds"
    )


class CaptchaDetectionSchema(BaseModel):
    """Schema for CAPTCHA detection tool input."""
    detection_strategy: str = Field(
        default="comprehensive",
        description="Detection strategy: 'dom', 'visual', or 'comprehensive'"
    )
    include_screenshot: bool = Field(
        default=True,
        description="Whether to include screenshot for visual analysis"
    )


# LlamaIndex Tool Implementations

class BrowserNavigationTool(BaseTool):
    """LlamaIndex tool for AgentCore browser navigation."""
    
    metadata = ToolMetadata(
        name="navigate_browser",
        description=(
            "Navigate to a URL using AgentCore browser tool. "
            "This tool handles page loading, redirects, and provides "
            "page information after successful navigation."
        ),
        fn_schema=NavigationSchema
    )
    
    def __init__(self, browser_client: IBrowserClient):
        """
        Initialize navigation tool.
        
        Args:
            browser_client: AgentCore browser client instance
        """
        self.browser_client = browser_client
        super().__init__()
    
    def __call__(self, input: Any) -> ToolOutput:
        """
        Main tool execution method required by LlamaIndex BaseTool.
        
        Args:
            input: Tool input (can be dict or other format)
            
        Returns:
            ToolOutput with navigation results
        """
        # Handle different input formats
        if isinstance(input, dict):
            kwargs = input
        elif isinstance(input, str):
            # Assume string input is a URL
            kwargs = {"url": input}
        else:
            kwargs = {"url": str(input)}
        
        try:
            result = asyncio.run(self.acall(**kwargs))
            
            if result.get("success", False):
                content = f"Successfully navigated to {result.get('url', 'unknown URL')}. Page title: {result.get('title', 'N/A')}"
                return ToolOutput(
                    tool_name=self.metadata.name,
                    content=content,
                    raw_input=kwargs,
                    raw_output=result,
                    is_error=False
                )
            else:
                error_msg = result.get("error", "Navigation failed")
                return ToolOutput(
                    tool_name=self.metadata.name,
                    content=f"Navigation failed: {error_msg}",
                    raw_input=kwargs,
                    raw_output=result,
                    is_error=True
                )
                
        except Exception as e:
            return ToolOutput(
                tool_name=self.metadata.name,
                content=f"Navigation error: {str(e)}",
                raw_input=kwargs,
                raw_output={"error": str(e)},
                is_error=True
            )
    
    def call(self, **kwargs) -> Dict[str, Any]:
        """
        Synchronous wrapper for navigation.
        
        Args:
            **kwargs: Navigation parameters
            
        Returns:
            Navigation results dictionary
        """
        return asyncio.run(self.acall(**kwargs))
    
    async def acall(self, **kwargs) -> Dict[str, Any]:
        """
        Navigate to URL and return page information.
        
        Args:
            **kwargs: Navigation parameters from NavigationSchema
            
        Returns:
            Dictionary containing navigation results
        """
        try:
            # Validate input using schema
            params = NavigationSchema(**kwargs)
            
            logger.info(f"Navigating to URL: {params.url}")
            
            # Call AgentCore browser tool navigation API
            response = await self.browser_client.navigate(
                url=params.url,
                wait_for_load=params.wait_for_load,
                timeout=params.timeout
            )
            
            if not response.success:
                raise NavigationError(
                    f"Navigation failed: {response.error_message}",
                    url=params.url
                )
            
            # Parse and return navigation results
            result = {
                "success": True,
                "url": response.data.get("current_url", params.url),
                "title": response.data.get("page_title", ""),
                "status_code": response.data.get("status_code"),
                "load_time": response.data.get("load_time_ms"),
                "page_ready": response.data.get("page_ready", True),
                "session_id": response.session_id,
                "timestamp": response.timestamp,
                "operation_id": response.operation_id
            }
            
            # Add page state information if available
            if "page_state" in response.data:
                result["page_state"] = response.data["page_state"]
            
            # Add redirect information if available
            if "redirects" in response.data:
                result["redirects"] = response.data["redirects"]
            
            logger.info(f"Successfully navigated to {result['url']}")
            return result
            
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "url": kwargs.get("url", "unknown")
            }


class TextExtractionTool(BaseTool):
    """LlamaIndex tool for extracting text content using AgentCore browser tool."""
    
    metadata = ToolMetadata(
        name="extract_text",
        description=(
            "Extract clean text content from web pages or specific elements "
            "using AgentCore browser tool. Supports CSS selectors, XPath, "
            "and element IDs for precise targeting."
        ),
        fn_schema=TextExtractionSchema
    )
    
    def __init__(self, browser_client: IBrowserClient):
        """
        Initialize text extraction tool.
        
        Args:
            browser_client: AgentCore browser client instance
        """
        self.browser_client = browser_client
        super().__init__()
    
    def __call__(self, input: Any) -> ToolOutput:
        """
        Main tool execution method required by LlamaIndex BaseTool.
        
        Args:
            input: Tool input (can be dict or other format)
            
        Returns:
            ToolOutput with text extraction results
        """
        # Handle different input formats
        if isinstance(input, dict):
            kwargs = input
        else:
            kwargs = {}
        
        try:
            result = asyncio.run(self.acall(**kwargs))
            
            if result.get("success", False):
                text = result.get("text", "")
                content = f"Extracted {len(text)} characters of text content"
                return ToolOutput(
                    tool_name=self.metadata.name,
                    content=content,
                    raw_input=kwargs,
                    raw_output=result,
                    is_error=False
                )
            else:
                error_msg = result.get("error", "Text extraction failed")
                return ToolOutput(
                    tool_name=self.metadata.name,
                    content=f"Text extraction failed: {error_msg}",
                    raw_input=kwargs,
                    raw_output=result,
                    is_error=True
                )
                
        except Exception as e:
            return ToolOutput(
                tool_name=self.metadata.name,
                content=f"Text extraction error: {str(e)}",
                raw_input=kwargs,
                raw_output={"error": str(e)},
                is_error=True
            )
    
    def call(self, **kwargs) -> Dict[str, Any]:
        """
        Synchronous wrapper for text extraction.
        
        Args:
            **kwargs: Text extraction parameters
            
        Returns:
            Text extraction results dictionary
        """
        return asyncio.run(self.acall(**kwargs))
    
    async def acall(self, **kwargs) -> Dict[str, Any]:
        """
        Extract text content from page or element.
        
        Args:
            **kwargs: Text extraction parameters from TextExtractionSchema
            
        Returns:
            Dictionary containing extracted text and metadata
        """
        try:
            # Validate input using schema
            params = TextExtractionSchema(**kwargs)
            
            # Create element selector if any selector is provided
            element_selector = None
            if any([params.css_selector, params.xpath, params.element_id, params.text_content]):
                element_selector = ElementSelector(
                    css_selector=params.css_selector,
                    xpath=params.xpath,
                    element_id=params.element_id,
                    text_content=params.text_content
                )
                logger.info(f"Extracting text from element: {element_selector}")
            else:
                logger.info("Extracting text from entire page")
            
            # Call AgentCore browser tool text extraction API
            response = await self.browser_client.extract_text(
                element_selector=element_selector
            )
            
            if not response.success:
                raise AgentCoreBrowserError(
                    f"Text extraction failed: {response.error_message}"
                )
            
            # Parse and return extraction results
            result = {
                "success": True,
                "text": response.data.get("text", ""),
                "text_length": len(response.data.get("text", "")),
                "element_found": response.data.get("element_found", True),
                "element_count": response.data.get("element_count", 1),
                "extraction_method": response.data.get("extraction_method", "full_page"),
                "session_id": response.session_id,
                "timestamp": response.timestamp,
                "operation_id": response.operation_id
            }
            
            # Add element information if available
            if "element_info" in response.data:
                result["element_info"] = response.data["element_info"]
            
            # Add page information if available
            if "page_info" in response.data:
                result["page_info"] = response.data["page_info"]
            
            logger.info(f"Successfully extracted {result['text_length']} characters")
            return result
            
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "text": "",
                "text_length": 0
            }


class ScreenshotCaptureTool(BaseTool):
    """LlamaIndex tool for capturing screenshots using AgentCore browser tool."""
    
    metadata = ToolMetadata(
        name="capture_screenshot",
        description=(
            "Capture screenshots of web pages or specific elements "
            "using AgentCore browser tool. Returns base64-encoded image data "
            "suitable for vision model analysis."
        ),
        fn_schema=ScreenshotSchema
    )
    
    def __init__(self, browser_client: IBrowserClient):
        """
        Initialize screenshot tool.
        
        Args:
            browser_client: AgentCore browser client instance
        """
        self.browser_client = browser_client
        super().__init__()
    
    def __call__(self, input: Any) -> ToolOutput:
        """
        Main tool execution method required by LlamaIndex BaseTool.
        
        Args:
            input: Tool input (can be dict or other format)
            
        Returns:
            ToolOutput with screenshot results
        """
        # Handle different input formats
        if isinstance(input, dict):
            kwargs = input
        else:
            kwargs = {}
        
        try:
            result = asyncio.run(self.acall(**kwargs))
            
            if result.get("success", False):
                screenshot_data = result.get("screenshot_data", "")
                data_size = len(screenshot_data) if screenshot_data else 0
                content = f"Captured screenshot ({data_size} bytes) in {result.get('screenshot_format', 'unknown')} format"
                return ToolOutput(
                    tool_name=self.metadata.name,
                    content=content,
                    raw_input=kwargs,
                    raw_output=result,
                    is_error=False
                )
            else:
                error_msg = result.get("error", "Screenshot capture failed")
                return ToolOutput(
                    tool_name=self.metadata.name,
                    content=f"Screenshot capture failed: {error_msg}",
                    raw_input=kwargs,
                    raw_output=result,
                    is_error=True
                )
                
        except Exception as e:
            return ToolOutput(
                tool_name=self.metadata.name,
                content=f"Screenshot capture error: {str(e)}",
                raw_input=kwargs,
                raw_output={"error": str(e)},
                is_error=True
            )
    
    def call(self, **kwargs) -> Dict[str, Any]:
        """
        Synchronous wrapper for screenshot capture.
        
        Args:
            **kwargs: Screenshot parameters
            
        Returns:
            Screenshot results dictionary
        """
        return asyncio.run(self.acall(**kwargs))
    
    async def acall(self, **kwargs) -> Dict[str, Any]:
        """
        Capture screenshot of page or element.
        
        Args:
            **kwargs: Screenshot parameters from ScreenshotSchema
            
        Returns:
            Dictionary containing screenshot data and metadata
        """
        try:
            # Validate input using schema
            params = ScreenshotSchema(**kwargs)
            
            # Create element selector if any selector is provided
            element_selector = None
            if any([params.css_selector, params.xpath, params.element_id]):
                element_selector = ElementSelector(
                    css_selector=params.css_selector,
                    xpath=params.xpath,
                    element_id=params.element_id
                )
                logger.info(f"Capturing screenshot of element: {element_selector}")
            else:
                logger.info(f"Capturing {'full page' if params.full_page else 'viewport'} screenshot")
            
            # Call AgentCore browser tool screenshot API
            response = await self.browser_client.take_screenshot(
                element_selector=element_selector,
                full_page=params.full_page
            )
            
            if not response.success:
                raise AgentCoreBrowserError(
                    f"Screenshot capture failed: {response.error_message}"
                )
            
            # Parse and return screenshot results
            screenshot_data = response.data.get("screenshot_data", "")
            
            result = {
                "success": True,
                "screenshot_data": screenshot_data,
                "screenshot_format": response.data.get("format", "png"),
                "screenshot_size": response.data.get("size", {}),
                "element_found": response.data.get("element_found", True),
                "capture_type": "element" if element_selector else ("full_page" if params.full_page else "viewport"),
                "session_id": response.session_id,
                "timestamp": response.timestamp,
                "operation_id": response.operation_id
            }
            
            # Add element information if available
            if "element_info" in response.data:
                result["element_info"] = response.data["element_info"]
            
            # Add page information if available
            if "page_info" in response.data:
                result["page_info"] = response.data["page_info"]
            
            # Calculate data size for logging
            data_size = len(screenshot_data) if screenshot_data else 0
            logger.info(f"Successfully captured screenshot ({data_size} bytes)")
            
            return result
            
        except Exception as e:
            logger.error(f"Screenshot capture failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "screenshot_data": "",
                "screenshot_format": "unknown"
            }


class ElementClickTool(BaseTool):
    """LlamaIndex tool for clicking web elements using AgentCore browser tool."""
    
    metadata = ToolMetadata(
        name="click_element",
        description=(
            "Click web elements (buttons, links, etc.) using AgentCore browser tool. "
            "Supports various element selection methods and handles page responses."
        ),
        fn_schema=ElementClickSchema
    )
    
    def __init__(self, browser_client: IBrowserClient):
        """
        Initialize element click tool.
        
        Args:
            browser_client: AgentCore browser client instance
        """
        self.browser_client = browser_client
        super().__init__()
    
    def __call__(self, input: Any) -> ToolOutput:
        """
        Main tool execution method required by LlamaIndex BaseTool.
        
        Args:
            input: Tool input (can be dict or other format)
            
        Returns:
            ToolOutput with click results
        """
        # Handle different input formats
        if isinstance(input, dict):
            kwargs = input
        elif isinstance(input, str):
            # Assume string input is a CSS selector
            kwargs = {"css_selector": input}
        else:
            kwargs = {"css_selector": str(input)}
        
        try:
            result = asyncio.run(self.acall(**kwargs))
            
            if result.get("success", False):
                page_changed = result.get("page_changed", False)
                content = f"Successfully clicked element. Page changed: {page_changed}"
                if result.get("new_url"):
                    content += f". New URL: {result['new_url']}"
                return ToolOutput(
                    tool_name=self.metadata.name,
                    content=content,
                    raw_input=kwargs,
                    raw_output=result,
                    is_error=False
                )
            else:
                error_msg = result.get("error", "Element click failed")
                return ToolOutput(
                    tool_name=self.metadata.name,
                    content=f"Element click failed: {error_msg}",
                    raw_input=kwargs,
                    raw_output=result,
                    is_error=True
                )
                
        except Exception as e:
            return ToolOutput(
                tool_name=self.metadata.name,
                content=f"Element click error: {str(e)}",
                raw_input=kwargs,
                raw_output={"error": str(e)},
                is_error=True
            )
    
    def call(self, **kwargs) -> Dict[str, Any]:
        """
        Synchronous wrapper for element clicking.
        
        Args:
            **kwargs: Click parameters
            
        Returns:
            Click results dictionary
        """
        return asyncio.run(self.acall(**kwargs))
    
    async def acall(self, **kwargs) -> Dict[str, Any]:
        """
        Click an element on the page.
        
        Args:
            **kwargs: Click parameters from ElementClickSchema
            
        Returns:
            Dictionary containing click results and page response
        """
        try:
            # Validate input using schema
            params = ElementClickSchema(**kwargs)
            
            # Create element selector
            element_selector = ElementSelector(
                css_selector=params.css_selector,
                xpath=params.xpath,
                element_id=params.element_id,
                text_content=params.text_content
            )
            
            logger.info(f"Clicking element: {element_selector}")
            
            # Call AgentCore browser tool click API
            response = await self.browser_client.click_element(
                element_selector=element_selector,
                wait_for_response=params.wait_for_response,
                timeout=params.timeout
            )
            
            if not response.success:
                raise ElementNotFoundError(
                    f"Element click failed: {response.error_message}",
                    selector=str(element_selector)
                )
            
            # Parse and return click results
            result = {
                "success": True,
                "element_found": response.data.get("element_found", True),
                "click_successful": response.data.get("click_successful", True),
                "page_changed": response.data.get("page_changed", False),
                "new_url": response.data.get("new_url"),
                "response_time": response.data.get("response_time_ms"),
                "session_id": response.session_id,
                "timestamp": response.timestamp,
                "operation_id": response.operation_id
            }
            
            # Add element information if available
            if "element_info" in response.data:
                result["element_info"] = response.data["element_info"]
            
            # Add page response information if available
            if "page_response" in response.data:
                result["page_response"] = response.data["page_response"]
            
            logger.info(f"Successfully clicked element, page changed: {result['page_changed']}")
            return result
            
        except Exception as e:
            logger.error(f"Element click failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "element_found": False,
                "click_successful": False
            }


class FormInteractionTool(BaseTool):
    """LlamaIndex tool for interacting with form elements using AgentCore browser tool."""
    
    metadata = ToolMetadata(
        name="interact_with_form",
        description=(
            "Type text into form fields, handle dropdowns, checkboxes, and other "
            "form elements using AgentCore browser tool."
        ),
        fn_schema=FormInteractionSchema
    )
    
    def __init__(self, browser_client: IBrowserClient):
        """
        Initialize form interaction tool.
        
        Args:
            browser_client: AgentCore browser client instance
        """
        self.browser_client = browser_client
        super().__init__()
    
    def __call__(self, input: Any) -> ToolOutput:
        """
        Main tool execution method required by LlamaIndex BaseTool.
        
        Args:
            input: Tool input (can be dict or other format)
            
        Returns:
            ToolOutput with form interaction results
        """
        # Handle different input formats
        if isinstance(input, dict):
            kwargs = input
        else:
            # Need at least text parameter
            kwargs = {"text": str(input)}
        
        try:
            result = asyncio.run(self.acall(**kwargs))
            
            if result.get("success", False):
                text_entered = result.get("text_entered", "")
                element_type = result.get("element_type", "form field")
                content = f"Successfully entered '{text_entered}' into {element_type}"
                return ToolOutput(
                    tool_name=self.metadata.name,
                    content=content,
                    raw_input=kwargs,
                    raw_output=result,
                    is_error=False
                )
            else:
                error_msg = result.get("error", "Form interaction failed")
                return ToolOutput(
                    tool_name=self.metadata.name,
                    content=f"Form interaction failed: {error_msg}",
                    raw_input=kwargs,
                    raw_output=result,
                    is_error=True
                )
                
        except Exception as e:
            return ToolOutput(
                tool_name=self.metadata.name,
                content=f"Form interaction error: {str(e)}",
                raw_input=kwargs,
                raw_output={"error": str(e)},
                is_error=True
            )
    
    def call(self, **kwargs) -> Dict[str, Any]:
        """
        Synchronous wrapper for form interaction.
        
        Args:
            **kwargs: Form interaction parameters
            
        Returns:
            Form interaction results dictionary
        """
        return asyncio.run(self.acall(**kwargs))
    
    async def acall(self, **kwargs) -> Dict[str, Any]:
        """
        Interact with form elements.
        
        Args:
            **kwargs: Form interaction parameters from FormInteractionSchema
            
        Returns:
            Dictionary containing interaction results
        """
        try:
            # Validate input using schema
            params = FormInteractionSchema(**kwargs)
            
            # Create element selector
            element_selector = ElementSelector(
                css_selector=params.css_selector,
                xpath=params.xpath,
                element_id=params.element_id
            )
            
            logger.info(f"Typing text into form element: {element_selector}")
            
            # Call AgentCore browser tool type text API
            response = await self.browser_client.type_text(
                element_selector=element_selector,
                text=params.text,
                clear_first=params.clear_first,
                typing_delay=params.typing_delay
            )
            
            if not response.success:
                raise ElementNotFoundError(
                    f"Form interaction failed: {response.error_message}",
                    selector=str(element_selector)
                )
            
            # Parse and return interaction results
            result = {
                "success": True,
                "element_found": response.data.get("element_found", True),
                "text_entered": response.data.get("text_entered", params.text),
                "field_cleared": response.data.get("field_cleared", params.clear_first),
                "element_type": response.data.get("element_type", "input"),
                "typing_time": response.data.get("typing_time_ms"),
                "session_id": response.session_id,
                "timestamp": response.timestamp,
                "operation_id": response.operation_id
            }
            
            # Add element information if available
            if "element_info" in response.data:
                result["element_info"] = response.data["element_info"]
            
            # Add validation information if available
            if "validation_result" in response.data:
                result["validation_result"] = response.data["validation_result"]
            
            logger.info(f"Successfully entered text into form field")
            return result
            
        except Exception as e:
            logger.error(f"Form interaction failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "element_found": False,
                "text_entered": ""
            }


class CaptchaDetectionTool(BaseTool):
    """LlamaIndex tool for detecting and analyzing CAPTCHAs using AgentCore browser tool."""
    
    metadata = ToolMetadata(
        name="detect_captcha",
        description=(
            "Detect and analyze CAPTCHAs on web pages using AgentCore browser tool. "
            "Combines DOM analysis and visual detection to identify different CAPTCHA types."
        ),
        fn_schema=CaptchaDetectionSchema
    )
    
    def __init__(self, browser_client: IBrowserClient):
        """
        Initialize CAPTCHA detection tool.
        
        Args:
            browser_client: AgentCore browser client instance
        """
        self.browser_client = browser_client
        super().__init__()
    
    def __call__(self, input: Any) -> ToolOutput:
        """
        Main tool execution method required by LlamaIndex BaseTool.
        
        Args:
            input: Tool input (can be dict or other format)
            
        Returns:
            ToolOutput with CAPTCHA detection results
        """
        # Handle different input formats
        if isinstance(input, dict):
            kwargs = input
        else:
            kwargs = {}
        
        try:
            result = asyncio.run(self.acall(**kwargs))
            
            if result.get("success", False):
                captcha_detected = result.get("captcha_detected", False)
                captcha_types = result.get("captcha_types", [])
                confidence = result.get("confidence_score", 0.0)
                
                if captcha_detected:
                    content = f"CAPTCHA detected! Types: {', '.join(captcha_types)}. Confidence: {confidence:.2f}"
                else:
                    content = "No CAPTCHA detected on the current page"
                
                return ToolOutput(
                    tool_name=self.metadata.name,
                    content=content,
                    raw_input=kwargs,
                    raw_output=result,
                    is_error=False
                )
            else:
                error_msg = result.get("error", "CAPTCHA detection failed")
                return ToolOutput(
                    tool_name=self.metadata.name,
                    content=f"CAPTCHA detection failed: {error_msg}",
                    raw_input=kwargs,
                    raw_output=result,
                    is_error=True
                )
                
        except Exception as e:
            return ToolOutput(
                tool_name=self.metadata.name,
                content=f"CAPTCHA detection error: {str(e)}",
                raw_input=kwargs,
                raw_output={"error": str(e)},
                is_error=True
            )
    
    def call(self, **kwargs) -> Dict[str, Any]:
        """
        Synchronous wrapper for CAPTCHA detection.
        
        Args:
            **kwargs: CAPTCHA detection parameters
            
        Returns:
            CAPTCHA detection results dictionary
        """
        return asyncio.run(self.acall(**kwargs))
    
    async def acall(self, **kwargs) -> Dict[str, Any]:
        """
        Detect and analyze CAPTCHAs on the current page.
        
        Args:
            **kwargs: CAPTCHA detection parameters from CaptchaDetectionSchema
            
        Returns:
            Dictionary containing CAPTCHA analysis results
        """
        try:
            # Validate input using schema
            params = CaptchaDetectionSchema(**kwargs)
            
            logger.info(f"Detecting CAPTCHAs using strategy: {params.detection_strategy}")
            
            # Initialize results
            result = {
                "success": True,
                "captcha_detected": False,
                "captcha_types": [],
                "captcha_elements": [],
                "detection_strategy": params.detection_strategy,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # DOM-based CAPTCHA detection
            if params.detection_strategy in ["dom", "comprehensive"]:
                dom_result = await self._detect_captcha_dom()
                result.update(dom_result)
            
            # Visual CAPTCHA detection
            if params.detection_strategy in ["visual", "comprehensive"] and params.include_screenshot:
                visual_result = await self._detect_captcha_visual()
                result.update(visual_result)
            
            # Combine results for comprehensive detection
            if params.detection_strategy == "comprehensive":
                result = self._combine_detection_results(result)
            
            logger.info(f"CAPTCHA detection complete: {result['captcha_detected']}")
            return result
            
        except Exception as e:
            logger.error(f"CAPTCHA detection failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "captcha_detected": False,
                "captcha_types": []
            }
    
    async def _detect_captcha_dom(self) -> Dict[str, Any]:
        """
        Detect CAPTCHAs using DOM analysis.
        
        Returns:
            DOM-based detection results
        """
        try:
            # Common CAPTCHA selectors
            captcha_selectors = [
                # reCAPTCHA
                ElementSelector(css_selector=".g-recaptcha"),
                ElementSelector(css_selector="[data-sitekey]"),
                ElementSelector(css_selector="#recaptcha"),
                # hCaptcha
                ElementSelector(css_selector=".h-captcha"),
                ElementSelector(css_selector="[data-hcaptcha-sitekey]"),
                # FunCaptcha
                ElementSelector(css_selector=".funcaptcha"),
                ElementSelector(css_selector="#funcaptcha"),
                # Generic CAPTCHA indicators
                ElementSelector(css_selector="[id*='captcha']"),
                ElementSelector(css_selector="[class*='captcha']"),
                ElementSelector(text_content="captcha"),
                ElementSelector(text_content="CAPTCHA")
            ]
            
            dom_elements = []
            captcha_types = []
            
            for selector in captcha_selectors:
                try:
                    # Extract text to check if element exists
                    response = await self.browser_client.extract_text(
                        element_selector=selector
                    )
                    
                    if response.success and response.data.get("element_found"):
                        element_info = {
                            "selector": str(selector),
                            "text": response.data.get("text", ""),
                            "element_count": response.data.get("element_count", 0)
                        }
                        dom_elements.append(element_info)
                        
                        # Classify CAPTCHA type based on selector
                        if selector.css_selector and "recaptcha" in selector.css_selector:
                            captcha_types.append("recaptcha")
                        elif selector.css_selector and "h-captcha" in selector.css_selector:
                            captcha_types.append("hcaptcha")
                        elif selector.css_selector and "funcaptcha" in selector.css_selector:
                            captcha_types.append("funcaptcha")
                        else:
                            captcha_types.append("generic")
                
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue
            
            return {
                "dom_captcha_detected": len(dom_elements) > 0,
                "dom_captcha_elements": dom_elements,
                "dom_captcha_types": list(set(captcha_types))
            }
            
        except Exception as e:
            logger.warning(f"DOM CAPTCHA detection failed: {e}")
            return {
                "dom_captcha_detected": False,
                "dom_captcha_elements": [],
                "dom_captcha_types": []
            }
    
    async def _detect_captcha_visual(self) -> Dict[str, Any]:
        """
        Detect CAPTCHAs using visual analysis.
        
        Returns:
            Visual-based detection results
        """
        try:
            # Take screenshot for visual analysis
            screenshot_response = await self.browser_client.take_screenshot(
                full_page=False  # Use viewport for faster processing
            )
            
            if not screenshot_response.success:
                return {
                    "visual_captcha_detected": False,
                    "screenshot_data": "",
                    "visual_analysis": {}
                }
            
            screenshot_data = screenshot_response.data.get("screenshot_data", "")
            
            # Basic visual indicators (this would be enhanced with actual image analysis)
            visual_analysis = {
                "screenshot_captured": bool(screenshot_data),
                "screenshot_size": screenshot_response.data.get("size", {}),
                "requires_ai_analysis": True,  # Flag for vision model processing
                "confidence_score": 0.5  # Placeholder confidence
            }
            
            return {
                "visual_captcha_detected": False,  # Would be determined by AI analysis
                "screenshot_data": screenshot_data,
                "visual_analysis": visual_analysis
            }
            
        except Exception as e:
            logger.warning(f"Visual CAPTCHA detection failed: {e}")
            return {
                "visual_captcha_detected": False,
                "screenshot_data": "",
                "visual_analysis": {}
            }
    
    def _combine_detection_results(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Combine DOM and visual detection results.
        
        Args:
            result: Current detection results
            
        Returns:
            Combined detection results
        """
        # Combine CAPTCHA detection flags
        dom_detected = result.get("dom_captcha_detected", False)
        visual_detected = result.get("visual_captcha_detected", False)
        
        result["captcha_detected"] = dom_detected or visual_detected
        
        # Combine CAPTCHA types
        dom_types = result.get("dom_captcha_types", [])
        visual_types = result.get("visual_captcha_types", [])
        result["captcha_types"] = list(set(dom_types + visual_types))
        
        # Combine element information
        dom_elements = result.get("dom_captcha_elements", [])
        visual_elements = result.get("visual_captcha_elements", [])
        result["captcha_elements"] = dom_elements + visual_elements
        
        # Calculate overall confidence
        confidence_scores = []
        if dom_detected:
            confidence_scores.append(0.9)  # High confidence for DOM detection
        if visual_detected:
            visual_confidence = result.get("visual_analysis", {}).get("confidence_score", 0.5)
            confidence_scores.append(visual_confidence)
        
        result["confidence_score"] = max(confidence_scores) if confidence_scores else 0.0
        
        return result