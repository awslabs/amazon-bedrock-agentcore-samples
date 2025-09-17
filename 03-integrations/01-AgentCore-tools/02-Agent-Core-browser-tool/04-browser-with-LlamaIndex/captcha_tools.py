"""
Advanced CAPTCHA tools for LlamaIndex integration with AgentCore browser tool and Bedrock vision models.

This module provides LlamaIndex BaseTool implementations that combine AgentCore
browser functionality with Bedrock vision models for intelligent CAPTCHA detection,
analysis, and solving.
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
from interfaces import IBrowserClient, ElementSelector
from vision_models import BedrockVisionClient, CaptchaType, CaptchaAnalysisResult
from captcha_workflows import CaptchaWorkflowEngine, WorkflowConfig, WorkflowResult
from exceptions import AgentCoreBrowserError


logger = logging.getLogger(__name__)


# Pydantic schemas for CAPTCHA tool inputs
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
    preprocess_image: bool = Field(
        default=True,
        description="Whether to preprocess screenshot for better analysis"
    )


class CaptchaSolvingSchema(BaseModel):
    """Schema for CAPTCHA solving tool input."""
    page_url: Optional[str] = Field(
        default=None,
        description="Optional URL to navigate to before solving"
    )
    max_attempts: int = Field(
        default=3,
        description="Maximum number of solving attempts"
    )
    confidence_threshold: float = Field(
        default=0.7,
        description="Minimum confidence threshold for solutions"
    )
    timeout_seconds: int = Field(
        default=120,
        description="Maximum time to spend solving CAPTCHA"
    )
    solving_strategy: str = Field(
        default="automatic",
        description="Solving strategy: 'automatic', 'vision_only', or 'hybrid'"
    )


class TextCaptchaSolvingSchema(BaseModel):
    """Schema for text-based CAPTCHA solving tool input."""
    css_selector: Optional[str] = Field(
        default=None,
        description="CSS selector for CAPTCHA image element"
    )
    xpath: Optional[str] = Field(
        default=None,
        description="XPath selector for CAPTCHA image element"
    )
    element_id: Optional[str] = Field(
        default=None,
        description="Element ID for CAPTCHA image"
    )
    input_selector: Optional[str] = Field(
        default=None,
        description="CSS selector for text input field"
    )
    submit_selector: Optional[str] = Field(
        default=None,
        description="CSS selector for submit button"
    )
    preprocess_image: bool = Field(
        default=True,
        description="Whether to preprocess image for better OCR"
    )


# Advanced CAPTCHA Tool Implementations

class AdvancedCaptchaDetectionTool(BaseTool):
    """Advanced CAPTCHA detection tool using vision models and DOM analysis."""
    
    metadata = ToolMetadata(
        name="detect_captcha_advanced",
        description=(
            "Detect CAPTCHAs on web pages using advanced vision models and DOM analysis. "
            "Combines multiple detection strategies for comprehensive CAPTCHA identification "
            "including reCAPTCHA, hCaptcha, text CAPTCHAs, and custom implementations."
        ),
        fn_schema=CaptchaDetectionSchema
    )
    
    def __init__(self, 
                 browser_client: IBrowserClient,
                 vision_client: Optional[BedrockVisionClient] = None):
        """
        Initialize advanced CAPTCHA detection tool.
        
        Args:
            browser_client: AgentCore browser client instance
            vision_client: Bedrock vision client for analysis
        """
        self.browser_client = browser_client
        self.vision_client = vision_client or BedrockVisionClient()
        super().__init__()
    
    def __call__(self, input: Any) -> ToolOutput:
        """Main tool execution method required by LlamaIndex BaseTool."""
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
                    content = "No CAPTCHA detected on current page"
                
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
    
    async def acall(self, **kwargs) -> Dict[str, Any]:
        """
        Detect CAPTCHAs using advanced vision models and DOM analysis.
        
        Args:
            **kwargs: Detection parameters from CaptchaDetectionSchema
            
        Returns:
            Dictionary containing detection results
        """
        try:
            # Validate input using schema
            params = CaptchaDetectionSchema(**kwargs)
            
            logger.info(f"Starting advanced CAPTCHA detection with strategy: {params.detection_strategy}")
            
            result = {
                "success": False,
                "captcha_detected": False,
                "captcha_types": [],
                "confidence_score": 0.0,
                "detection_method": params.detection_strategy,
                "analysis_results": {},
                "screenshot_data": "",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # DOM-based detection
            if params.detection_strategy in ["dom", "comprehensive"]:
                dom_result = await self._detect_captcha_dom()
                result["analysis_results"]["dom"] = dom_result
                
                if dom_result.get("dom_captcha_detected", False):
                    result["captcha_detected"] = True
                    result["captcha_types"].extend(dom_result.get("dom_captcha_types", []))
            
            # Visual detection using vision models
            if params.detection_strategy in ["visual", "comprehensive"] and params.include_screenshot:
                visual_result = await self._detect_captcha_visual(params.preprocess_image)
                result["analysis_results"]["visual"] = visual_result
                
                if visual_result.get("captcha_detected", False):
                    result["captcha_detected"] = True
                    result["captcha_types"].append(visual_result.get("captcha_type", "unknown"))
                    result["confidence_score"] = max(
                        result["confidence_score"], 
                        visual_result.get("confidence_score", 0.0)
                    )
                
                result["screenshot_data"] = visual_result.get("screenshot_data", "")
            
            # Remove duplicates from captcha_types
            result["captcha_types"] = list(set(result["captcha_types"]))
            
            # Set overall confidence if not set by visual analysis
            if result["confidence_score"] == 0.0 and result["captcha_detected"]:
                result["confidence_score"] = 0.8  # High confidence for DOM detection
            
            result["success"] = True
            
            logger.info(f"CAPTCHA detection completed: detected={result['captcha_detected']}, "
                       f"types={result['captcha_types']}, confidence={result['confidence_score']}")
            
            return result
            
        except Exception as e:
            logger.error(f"Advanced CAPTCHA detection failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "captcha_detected": False,
                "captcha_types": [],
                "confidence_score": 0.0
            }
    
    async def _detect_captcha_dom(self) -> Dict[str, Any]:
        """Detect CAPTCHAs using DOM analysis."""
        try:
            # Common CAPTCHA selectors
            captcha_selectors = [
                "[class*='captcha']",
                "[id*='captcha']",
                "[class*='recaptcha']",
                "[id*='recaptcha']",
                "[class*='h-captcha']",
                "[id*='h-captcha']",
                "[class*='funcaptcha']",
                "iframe[src*='captcha']",
                "iframe[src*='recaptcha']",
                "iframe[src*='hcaptcha']",
                ".g-recaptcha",
                "#g-recaptcha"
            ]
            
            dom_elements = []
            captcha_types = []
            
            for selector in captcha_selectors:
                try:
                    element_selector = ElementSelector(css_selector=selector)
                    
                    # Check if element exists
                    response = await self.browser_client.extract_text(element_selector)
                    
                    if response.success and response.data.get("element_found"):
                        element_info = {
                            "selector": selector,
                            "text": response.data.get("text", ""),
                            "element_count": response.data.get("element_count", 0)
                        }
                        dom_elements.append(element_info)
                        
                        # Classify CAPTCHA type based on selector
                        if "recaptcha" in selector.lower():
                            captcha_types.append("recaptcha")
                        elif "h-captcha" in selector.lower() or "hcaptcha" in selector.lower():
                            captcha_types.append("hcaptcha")
                        elif "funcaptcha" in selector.lower():
                            captcha_types.append("funcaptcha")
                        else:
                            captcha_types.append("generic")
                
                except Exception as e:
                    logger.debug(f"DOM selector {selector} failed: {e}")
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
    
    async def _detect_captcha_visual(self, preprocess: bool = True) -> Dict[str, Any]:
        """Detect CAPTCHAs using vision model analysis."""
        try:
            # Take screenshot for visual analysis
            screenshot_response = await self.browser_client.take_screenshot(full_page=False)
            
            if not screenshot_response.success:
                return {
                    "captcha_detected": False,
                    "screenshot_data": "",
                    "error": "Failed to capture screenshot"
                }
            
            screenshot_data = screenshot_response.data.get("screenshot_data", "")
            if not screenshot_data:
                return {
                    "captcha_detected": False,
                    "screenshot_data": "",
                    "error": "No screenshot data available"
                }
            
            # Decode base64 screenshot data for vision analysis
            try:
                image_bytes = base64.b64decode(screenshot_data)
            except Exception as e:
                logger.error(f"Failed to decode screenshot data: {e}")
                return {
                    "captcha_detected": False,
                    "screenshot_data": screenshot_data,
                    "error": "Failed to decode screenshot data"
                }
            
            # Analyze with vision model
            analysis_result = await self.vision_client.analyze_captcha(
                image_data=image_bytes,
                preprocess=preprocess
            )
            
            return {
                "captcha_detected": analysis_result.captcha_detected,
                "captcha_type": analysis_result.captcha_type.value if analysis_result.captcha_type else "unknown",
                "confidence_score": analysis_result.confidence_score,
                "solution": analysis_result.solution,
                "challenge_text": analysis_result.challenge_text,
                "visual_elements": analysis_result.visual_elements or [],
                "processing_time_ms": analysis_result.processing_time_ms,
                "model_used": analysis_result.model_used,
                "screenshot_data": screenshot_data,
                "error": analysis_result.error_message
            }
            
        except Exception as e:
            logger.error(f"Visual CAPTCHA detection failed: {e}")
            return {
                "captcha_detected": False,
                "screenshot_data": "",
                "error": str(e)
            }


class CaptchaSolvingTool(BaseTool):
    """Comprehensive CAPTCHA solving tool using workflows and vision models."""
    
    metadata = ToolMetadata(
        name="solve_captcha",
        description=(
            "Solve CAPTCHAs automatically using advanced vision models and browser automation. "
            "Supports text CAPTCHAs, image selection challenges, reCAPTCHA, hCaptcha, and more. "
            "Uses intelligent workflows with retry logic and validation."
        ),
        fn_schema=CaptchaSolvingSchema
    )
    
    def __init__(self, 
                 browser_client: IBrowserClient,
                 vision_client: Optional[BedrockVisionClient] = None):
        """
        Initialize CAPTCHA solving tool.
        
        Args:
            browser_client: AgentCore browser client instance
            vision_client: Bedrock vision client for analysis
        """
        self.browser_client = browser_client
        self.vision_client = vision_client or BedrockVisionClient()
        self.workflow_engine = None
        super().__init__()
    
    def __call__(self, input: Any) -> ToolOutput:
        """Main tool execution method required by LlamaIndex BaseTool."""
        if isinstance(input, dict):
            kwargs = input
        else:
            kwargs = {}
        
        try:
            result = asyncio.run(self.acall(**kwargs))
            
            if result.get("success", False):
                captcha_type = result.get("captcha_type", "unknown")
                solution = result.get("solution", "")
                attempts = result.get("attempts_made", 0)
                time_ms = result.get("total_time_ms", 0)
                
                content = (f"CAPTCHA solved successfully! Type: {captcha_type}, "
                          f"Solution: '{solution}', Attempts: {attempts}, Time: {time_ms}ms")
                
                return ToolOutput(
                    tool_name=self.metadata.name,
                    content=content,
                    raw_input=kwargs,
                    raw_output=result,
                    is_error=False
                )
            else:
                error_msg = result.get("error_message", "CAPTCHA solving failed")
                status = result.get("status", "unknown")
                attempts = result.get("attempts_made", 0)
                
                content = f"CAPTCHA solving failed: {error_msg} (Status: {status}, Attempts: {attempts})"
                
                return ToolOutput(
                    tool_name=self.metadata.name,
                    content=content,
                    raw_input=kwargs,
                    raw_output=result,
                    is_error=True
                )
                
        except Exception as e:
            return ToolOutput(
                tool_name=self.metadata.name,
                content=f"CAPTCHA solving error: {str(e)}",
                raw_input=kwargs,
                raw_output={"error": str(e)},
                is_error=True
            )
    
    async def acall(self, **kwargs) -> Dict[str, Any]:
        """
        Solve CAPTCHAs using intelligent workflows.
        
        Args:
            **kwargs: Solving parameters from CaptchaSolvingSchema
            
        Returns:
            Dictionary containing solving results
        """
        try:
            # Validate input using schema
            params = CaptchaSolvingSchema(**kwargs)
            
            logger.info(f"Starting CAPTCHA solving with strategy: {params.solving_strategy}")
            
            # Create workflow configuration
            from captcha_workflows import SolvingStrategy
            strategy_map = {
                "automatic": SolvingStrategy.AUTOMATIC,
                "vision_only": SolvingStrategy.VISION_ONLY,
                "hybrid": SolvingStrategy.HYBRID
            }
            
            workflow_config = WorkflowConfig(
                max_attempts=params.max_attempts,
                timeout_seconds=params.timeout_seconds,
                confidence_threshold=params.confidence_threshold,
                solving_strategy=strategy_map.get(params.solving_strategy, SolvingStrategy.AUTOMATIC)
            )
            
            # Initialize workflow engine
            self.workflow_engine = CaptchaWorkflowEngine(
                browser_client=self.browser_client,
                vision_client=self.vision_client,
                config=workflow_config
            )
            
            # Execute solving workflow
            workflow_result = await self.workflow_engine.detect_and_solve_captcha(
                page_url=params.page_url
            )
            
            # Convert workflow result to tool result
            result = {
                "success": workflow_result.success,
                "captcha_type": workflow_result.captcha_type.value if workflow_result.captcha_type else None,
                "solution": workflow_result.solution,
                "confidence_score": workflow_result.confidence_score,
                "attempts_made": workflow_result.attempts_made,
                "total_time_ms": workflow_result.total_time_ms,
                "status": workflow_result.status.value,
                "error_message": workflow_result.error_message,
                "analysis_results": [
                    {
                        "captcha_detected": ar.captcha_detected,
                        "captcha_type": ar.captcha_type.value if ar.captcha_type else None,
                        "confidence_score": ar.confidence_score,
                        "solution": ar.solution,
                        "processing_time_ms": ar.processing_time_ms,
                        "model_used": ar.model_used
                    }
                    for ar in workflow_result.analysis_results
                ],
                "validation_results": workflow_result.validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"CAPTCHA solving completed: success={result['success']}, "
                       f"type={result['captcha_type']}, attempts={result['attempts_made']}")
            
            return result
            
        except Exception as e:
            logger.error(f"CAPTCHA solving failed: {e}")
            return {
                "success": False,
                "error_message": str(e),
                "error_type": type(e).__name__,
                "captcha_type": None,
                "solution": None,
                "confidence_score": 0.0,
                "attempts_made": 0,
                "total_time_ms": 0,
                "status": "failed"
            }


class TextCaptchaSolvingTool(BaseTool):
    """Specialized tool for solving text-based CAPTCHAs using vision models."""
    
    metadata = ToolMetadata(
        name="solve_text_captcha",
        description=(
            "Solve text-based CAPTCHAs using advanced OCR and vision models. "
            "Handles distorted text, noise reduction, and automatic form submission. "
            "Optimized for text recognition accuracy."
        ),
        fn_schema=TextCaptchaSolvingSchema
    )
    
    def __init__(self, 
                 browser_client: IBrowserClient,
                 vision_client: Optional[BedrockVisionClient] = None):
        """
        Initialize text CAPTCHA solving tool.
        
        Args:
            browser_client: AgentCore browser client instance
            vision_client: Bedrock vision client for analysis
        """
        self.browser_client = browser_client
        self.vision_client = vision_client or BedrockVisionClient()
        super().__init__()
    
    def __call__(self, input: Any) -> ToolOutput:
        """Main tool execution method required by LlamaIndex BaseTool."""
        if isinstance(input, dict):
            kwargs = input
        else:
            kwargs = {}
        
        try:
            result = asyncio.run(self.acall(**kwargs))
            
            if result.get("success", False):
                solution = result.get("solution", "")
                confidence = result.get("confidence_score", 0.0)
                submitted = result.get("submitted", False)
                
                content = (f"Text CAPTCHA solved: '{solution}' (confidence: {confidence:.2f}). "
                          f"{'Submitted successfully' if submitted else 'Solution ready for submission'}")
                
                return ToolOutput(
                    tool_name=self.metadata.name,
                    content=content,
                    raw_input=kwargs,
                    raw_output=result,
                    is_error=False
                )
            else:
                error_msg = result.get("error", "Text CAPTCHA solving failed")
                return ToolOutput(
                    tool_name=self.metadata.name,
                    content=f"Text CAPTCHA solving failed: {error_msg}",
                    raw_input=kwargs,
                    raw_output=result,
                    is_error=True
                )
                
        except Exception as e:
            return ToolOutput(
                tool_name=self.metadata.name,
                content=f"Text CAPTCHA solving error: {str(e)}",
                raw_input=kwargs,
                raw_output={"error": str(e)},
                is_error=True
            )
    
    async def acall(self, **kwargs) -> Dict[str, Any]:
        """
        Solve text-based CAPTCHAs using specialized vision analysis.
        
        Args:
            **kwargs: Solving parameters from TextCaptchaSolvingSchema
            
        Returns:
            Dictionary containing solving results
        """
        try:
            # Validate input using schema
            params = TextCaptchaSolvingSchema(**kwargs)
            
            logger.info("Starting text CAPTCHA solving")
            
            # Take screenshot of CAPTCHA image
            element_selector = None
            if any([params.css_selector, params.xpath, params.element_id]):
                element_selector = ElementSelector(
                    css_selector=params.css_selector,
                    xpath=params.xpath,
                    element_id=params.element_id
                )
            
            screenshot_response = await self.browser_client.take_screenshot(
                element_selector=element_selector,
                full_page=False
            )
            
            if not screenshot_response.success:
                return {
                    "success": False,
                    "error": "Failed to capture CAPTCHA screenshot",
                    "solution": None,
                    "confidence_score": 0.0
                }
            
            screenshot_data = screenshot_response.data.get("screenshot_data", "")
            if not screenshot_data:
                return {
                    "success": False,
                    "error": "No screenshot data available",
                    "solution": None,
                    "confidence_score": 0.0
                }
            
            # Decode screenshot data
            try:
                image_bytes = base64.b64decode(screenshot_data)
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to decode screenshot: {str(e)}",
                    "solution": None,
                    "confidence_score": 0.0
                }
            
            # Solve text CAPTCHA using specialized vision analysis
            text_result = await self.vision_client.solve_text_captcha(image_bytes)
            
            if not text_result.solution:
                return {
                    "success": False,
                    "error": text_result.error_message or "No solution found",
                    "solution": None,
                    "confidence_score": text_result.confidence_score,
                    "processing_time_ms": text_result.processing_time_ms
                }
            
            result = {
                "success": True,
                "solution": text_result.solution,
                "confidence_score": text_result.confidence_score,
                "processing_time_ms": text_result.processing_time_ms,
                "model_used": text_result.model_used,
                "submitted": False,
                "screenshot_data": screenshot_data
            }
            
            # Attempt to submit solution if selectors provided
            if params.input_selector:
                try:
                    # Type solution into input field
                    input_element = ElementSelector(css_selector=params.input_selector)
                    type_response = await self.browser_client.type_text(
                        element_selector=input_element,
                        text=text_result.solution,
                        clear_first=True
                    )
                    
                    if type_response.success:
                        result["input_filled"] = True
                        
                        # Submit if submit selector provided
                        if params.submit_selector:
                            submit_element = ElementSelector(css_selector=params.submit_selector)
                            submit_response = await self.browser_client.click_element(submit_element)
                            
                            if submit_response.success:
                                result["submitted"] = True
                                
                                # Wait a moment and check for success/failure indicators
                                await asyncio.sleep(2)
                                
                                # Extract page text to check for validation
                                page_response = await self.browser_client.extract_text()
                                if page_response.success:
                                    page_text = page_response.data.get("text", "").lower()
                                    
                                    # Check for success indicators
                                    success_indicators = ["success", "correct", "verified", "passed"]
                                    error_indicators = ["incorrect", "wrong", "invalid", "failed", "error"]
                                    
                                    for indicator in success_indicators:
                                        if indicator in page_text:
                                            result["validation_result"] = "success"
                                            break
                                    else:
                                        for indicator in error_indicators:
                                            if indicator in page_text:
                                                result["validation_result"] = "failed"
                                                break
                                        else:
                                            result["validation_result"] = "unknown"
                            else:
                                result["submit_error"] = submit_response.error_message
                    else:
                        result["input_error"] = type_response.error_message
                        
                except Exception as e:
                    result["submission_error"] = str(e)
            
            logger.info(f"Text CAPTCHA solved: '{result['solution']}' "
                       f"(confidence: {result['confidence_score']:.2f})")
            
            return result
            
        except Exception as e:
            logger.error(f"Text CAPTCHA solving failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "solution": None,
                "confidence_score": 0.0,
                "submitted": False
            }


# Tool factory function for easy integration
def create_captcha_tools(browser_client: IBrowserClient,
                        vision_client: Optional[BedrockVisionClient] = None) -> List[BaseTool]:
    """
    Create all CAPTCHA-related tools for LlamaIndex integration.
    
    Args:
        browser_client: AgentCore browser client instance
        vision_client: Optional Bedrock vision client
        
    Returns:
        List of CAPTCHA tools ready for use with LlamaIndex agents
    """
    vision_client = vision_client or BedrockVisionClient()
    
    return [
        AdvancedCaptchaDetectionTool(browser_client, vision_client),
        CaptchaSolvingTool(browser_client, vision_client),
        TextCaptchaSolvingTool(browser_client, vision_client)
    ]