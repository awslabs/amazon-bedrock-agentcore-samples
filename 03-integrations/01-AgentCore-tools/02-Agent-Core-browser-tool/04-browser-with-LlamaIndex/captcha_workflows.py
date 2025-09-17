"""
CAPTCHA solving workflows using AgentCore browser tool and Bedrock vision models.

This module implements intelligent CAPTCHA analysis and solving workflows that
combine AgentCore browser tool capabilities with Bedrock vision models for
comprehensive CAPTCHA handling.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field

from interfaces import IBrowserClient, ElementSelector
from vision_models import (
    BedrockVisionClient, CaptchaType, CaptchaAnalysisResult, 
    CaptchaSolutionValidator, ConfidenceLevel
)
from exceptions import AgentCoreBrowserError, BrowserErrorType, TimeoutError


logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """Status of CAPTCHA solving workflow."""
    PENDING = "pending"
    DETECTING = "detecting"
    ANALYZING = "analyzing"
    SOLVING = "solving"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class SolvingStrategy(Enum):
    """Strategies for CAPTCHA solving."""
    AUTOMATIC = "automatic"
    VISION_ONLY = "vision_only"
    HYBRID = "hybrid"
    MANUAL_FALLBACK = "manual_fallback"


@dataclass
class WorkflowConfig:
    """Configuration for CAPTCHA solving workflows."""
    max_attempts: int = 3
    timeout_seconds: int = 120
    confidence_threshold: float = 0.7
    retry_delay_seconds: float = 2.0
    enable_preprocessing: bool = True
    fallback_to_manual: bool = False
    solving_strategy: SolvingStrategy = SolvingStrategy.AUTOMATIC
    detection_selectors: List[str] = field(default_factory=lambda: [
        "[class*='captcha']",
        "[id*='captcha']",
        "[class*='recaptcha']",
        "[id*='recaptcha']",
        "[class*='hcaptcha']",
        "[id*='hcaptcha']",
        "iframe[src*='captcha']",
        "iframe[src*='recaptcha']",
        "iframe[src*='hcaptcha']"
    ])


@dataclass
class WorkflowResult:
    """Result of CAPTCHA solving workflow."""
    success: bool
    captcha_type: Optional[CaptchaType] = None
    solution: Optional[str] = None
    confidence_score: float = 0.0
    attempts_made: int = 0
    total_time_ms: int = 0
    status: WorkflowStatus = WorkflowStatus.PENDING
    error_message: Optional[str] = None
    analysis_results: List[CaptchaAnalysisResult] = field(default_factory=list)
    validation_results: List[Dict[str, Any]] = field(default_factory=list)


class CaptchaWorkflowEngine:
    """Engine for executing CAPTCHA solving workflows."""
    
    def __init__(self, 
                 browser_client: IBrowserClient,
                 vision_client: Optional[BedrockVisionClient] = None,
                 config: Optional[WorkflowConfig] = None):
        """
        Initialize CAPTCHA workflow engine.
        
        Args:
            browser_client: AgentCore browser client
            vision_client: Bedrock vision client for analysis
            config: Workflow configuration
        """
        self.browser_client = browser_client
        self.vision_client = vision_client or BedrockVisionClient()
        self.config = config or WorkflowConfig()
        self.solution_validator = CaptchaSolutionValidator(browser_client)
        
        # Workflow state
        self.active_workflows: Dict[str, WorkflowResult] = {}
        self.workflow_history: List[WorkflowResult] = []
    
    async def detect_and_solve_captcha(self, 
                                     page_url: Optional[str] = None,
                                     workflow_id: Optional[str] = None) -> WorkflowResult:
        """
        Main workflow method to detect and solve CAPTCHAs on current page.
        
        Args:
            page_url: Optional URL to navigate to first
            workflow_id: Optional workflow identifier for tracking
            
        Returns:
            WorkflowResult with solving outcome
        """
        workflow_id = workflow_id or f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        start_time = datetime.now()
        
        # Initialize workflow result
        result = WorkflowResult(
            success=False,
            status=WorkflowStatus.PENDING
        )
        
        self.active_workflows[workflow_id] = result
        
        try:
            logger.info(f"Starting CAPTCHA workflow {workflow_id}")
            
            # Navigate to page if URL provided
            if page_url:
                await self.browser_client.navigate(page_url)
                await asyncio.sleep(1)  # Allow page to load
            
            # Step 1: Detect CAPTCHA presence
            result.status = WorkflowStatus.DETECTING
            captcha_detected, captcha_elements = await self._detect_captcha_presence()
            
            if not captcha_detected:
                result.success = True
                result.status = WorkflowStatus.COMPLETED
                result.error_message = "No CAPTCHA detected on page"
                logger.info(f"Workflow {workflow_id}: No CAPTCHA found")
                return result
            
            logger.info(f"Workflow {workflow_id}: CAPTCHA detected, {len(captcha_elements)} elements found")
            
            # Step 2: Analyze CAPTCHA type and content
            result.status = WorkflowStatus.ANALYZING
            analysis_result = await self._analyze_captcha(captcha_elements)
            result.analysis_results.append(analysis_result)
            result.captcha_type = analysis_result.captcha_type
            
            if analysis_result.error_message:
                result.status = WorkflowStatus.FAILED
                result.error_message = f"Analysis failed: {analysis_result.error_message}"
                logger.error(f"Workflow {workflow_id}: {result.error_message}")
                return result
            
            # Step 3: Solve CAPTCHA based on type and strategy
            result.status = WorkflowStatus.SOLVING
            solving_success = await self._solve_captcha_with_retries(
                analysis_result, result, workflow_id
            )
            
            if not solving_success:
                result.status = WorkflowStatus.FAILED
                result.error_message = "Failed to solve CAPTCHA after all attempts"
                logger.error(f"Workflow {workflow_id}: {result.error_message}")
                return result
            
            # Step 4: Validate solution
            result.status = WorkflowStatus.VALIDATING
            validation_result = await self._validate_solution(result.solution, result.captcha_type)
            result.validation_results.append(validation_result)
            
            if validation_result.get("valid", False):
                result.success = True
                result.status = WorkflowStatus.COMPLETED
                logger.info(f"Workflow {workflow_id}: Successfully solved CAPTCHA")
            else:
                result.status = WorkflowStatus.FAILED
                result.error_message = f"Solution validation failed: {validation_result.get('error', 'Unknown error')}"
                logger.error(f"Workflow {workflow_id}: {result.error_message}")
            
            return result
            
        except asyncio.TimeoutError:
            result.status = WorkflowStatus.TIMEOUT
            result.error_message = f"Workflow timeout after {self.config.timeout_seconds} seconds"
            logger.error(f"Workflow {workflow_id}: {result.error_message}")
            return result
            
        except Exception as e:
            result.status = WorkflowStatus.FAILED
            result.error_message = f"Workflow error: {str(e)}"
            logger.error(f"Workflow {workflow_id}: {result.error_message}")
            return result
            
        finally:
            # Calculate total time and cleanup
            total_time = int((datetime.now() - start_time).total_seconds() * 1000)
            result.total_time_ms = total_time
            
            # Move to history and cleanup
            if workflow_id in self.active_workflows:
                del self.active_workflows[workflow_id]
            self.workflow_history.append(result)
            
            # Keep only recent history (last 50 workflows)
            if len(self.workflow_history) > 50:
                self.workflow_history = self.workflow_history[-50:]
    
    async def _detect_captcha_presence(self) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Detect CAPTCHA presence on current page using DOM analysis.
        
        Returns:
            Tuple of (captcha_detected, captcha_elements)
        """
        captcha_elements = []
        
        try:
            # Check each detection selector
            for selector in self.config.detection_selectors:
                try:
                    element_selector = ElementSelector(css_selector=selector)
                    
                    # Try to extract text to see if element exists
                    response = await self.browser_client.extract_text(element_selector)
                    
                    if response.success and response.data.get("text"):
                        captcha_elements.append({
                            "selector": selector,
                            "text": response.data.get("text", ""),
                            "element_type": "text_element"
                        })
                        
                except Exception as e:
                    logger.debug(f"Selector {selector} not found or error: {e}")
                    continue
            
            # Take screenshot to analyze visually
            screenshot_response = await self.browser_client.take_screenshot(full_page=False)
            
            if screenshot_response.success:
                screenshot_data = screenshot_response.data.get("screenshot_data")
                if screenshot_data:
                    # Use vision model to detect CAPTCHA in screenshot
                    vision_analysis = await self.vision_client.analyze_captcha(
                        screenshot_data, 
                        preprocess=True
                    )
                    
                    if vision_analysis.captcha_detected:
                        captcha_elements.append({
                            "selector": "visual_detection",
                            "analysis": vision_analysis,
                            "element_type": "visual_captcha"
                        })
            
            captcha_detected = len(captcha_elements) > 0
            logger.info(f"CAPTCHA detection: {captcha_detected}, elements found: {len(captcha_elements)}")
            
            return captcha_detected, captcha_elements
            
        except Exception as e:
            logger.error(f"CAPTCHA detection failed: {e}")
            return False, []
    
    async def _analyze_captcha(self, captcha_elements: List[Dict[str, Any]]) -> CaptchaAnalysisResult:
        """
        Analyze detected CAPTCHA elements to determine type and solution approach.
        
        Args:
            captcha_elements: List of detected CAPTCHA elements
            
        Returns:
            CaptchaAnalysisResult with analysis details
        """
        try:
            # Prioritize visual analysis if available
            visual_element = None
            for element in captcha_elements:
                if element.get("element_type") == "visual_captcha":
                    visual_element = element
                    break
            
            if visual_element and "analysis" in visual_element:
                # Use existing visual analysis
                return visual_element["analysis"]
            
            # Take fresh screenshot for analysis
            screenshot_response = await self.browser_client.take_screenshot(full_page=False)
            
            if not screenshot_response.success:
                return CaptchaAnalysisResult(
                    captcha_detected=False,
                    captcha_type=CaptchaType.UNKNOWN,
                    confidence_score=0.0,
                    error_message="Failed to capture screenshot for analysis"
                )
            
            screenshot_data = screenshot_response.data.get("screenshot_data")
            if not screenshot_data:
                return CaptchaAnalysisResult(
                    captcha_detected=False,
                    captcha_type=CaptchaType.UNKNOWN,
                    confidence_score=0.0,
                    error_message="No screenshot data available"
                )
            
            # Analyze with vision model
            analysis_result = await self.vision_client.analyze_captcha(
                screenshot_data,
                preprocess=self.config.enable_preprocessing
            )
            
            logger.info(f"CAPTCHA analysis: type={analysis_result.captcha_type}, "
                       f"confidence={analysis_result.confidence_score}")
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"CAPTCHA analysis failed: {e}")
            return CaptchaAnalysisResult(
                captcha_detected=False,
                captcha_type=CaptchaType.UNKNOWN,
                confidence_score=0.0,
                error_message=str(e)
            )
    
    async def _solve_captcha_with_retries(self, 
                                        analysis_result: CaptchaAnalysisResult,
                                        workflow_result: WorkflowResult,
                                        workflow_id: str) -> bool:
        """
        Solve CAPTCHA with retry logic based on configuration.
        
        Args:
            analysis_result: CAPTCHA analysis result
            workflow_result: Workflow result to update
            workflow_id: Workflow identifier
            
        Returns:
            True if solving succeeded, False otherwise
        """
        for attempt in range(1, self.config.max_attempts + 1):
            workflow_result.attempts_made = attempt
            
            logger.info(f"Workflow {workflow_id}: Solving attempt {attempt}/{self.config.max_attempts}")
            
            try:
                # Choose solving method based on CAPTCHA type and strategy
                if analysis_result.captcha_type == CaptchaType.TEXT:
                    solution = await self._solve_text_captcha(analysis_result)
                elif analysis_result.captcha_type == CaptchaType.IMAGE:
                    solution = await self._solve_image_captcha(analysis_result)
                elif analysis_result.captcha_type in [CaptchaType.RECAPTCHA_V2, CaptchaType.HCAPTCHA]:
                    solution = await self._solve_interactive_captcha(analysis_result)
                else:
                    solution = await self._solve_generic_captcha(analysis_result)
                
                if solution:
                    workflow_result.solution = solution
                    workflow_result.confidence_score = analysis_result.confidence_score
                    logger.info(f"Workflow {workflow_id}: Solution found on attempt {attempt}")
                    return True
                
            except Exception as e:
                logger.warning(f"Workflow {workflow_id}: Attempt {attempt} failed: {e}")
            
            # Wait before retry (except on last attempt)
            if attempt < self.config.max_attempts:
                await asyncio.sleep(self.config.retry_delay_seconds)
        
        logger.error(f"Workflow {workflow_id}: All solving attempts failed")
        return False
    
    async def _solve_text_captcha(self, analysis_result: CaptchaAnalysisResult) -> Optional[str]:
        """
        Solve text-based CAPTCHA using specialized vision analysis.
        
        Args:
            analysis_result: CAPTCHA analysis result
            
        Returns:
            Solution string if successful, None otherwise
        """
        try:
            # Take fresh screenshot for text analysis
            screenshot_response = await self.browser_client.take_screenshot(full_page=False)
            
            if not screenshot_response.success:
                logger.error("Failed to capture screenshot for text CAPTCHA")
                return None
            
            screenshot_data = screenshot_response.data.get("screenshot_data")
            if not screenshot_data:
                logger.error("No screenshot data for text CAPTCHA")
                return None
            
            # Use specialized text CAPTCHA solving
            text_result = await self.vision_client.solve_text_captcha(screenshot_data)
            
            if (text_result.solution and 
                text_result.confidence_score >= self.config.confidence_threshold):
                
                logger.info(f"Text CAPTCHA solved: '{text_result.solution}' "
                           f"(confidence: {text_result.confidence_score})")
                return text_result.solution
            
            logger.warning(f"Text CAPTCHA solution confidence too low: {text_result.confidence_score}")
            return None
            
        except Exception as e:
            logger.error(f"Text CAPTCHA solving failed: {e}")
            return None
    
    async def _solve_image_captcha(self, analysis_result: CaptchaAnalysisResult) -> Optional[str]:
        """
        Solve image-based CAPTCHA using vision analysis.
        
        Args:
            analysis_result: CAPTCHA analysis result
            
        Returns:
            Solution string if successful, None otherwise
        """
        try:
            # For image CAPTCHAs, we need to analyze the grid and select appropriate images
            # This is a complex task that requires understanding the challenge instruction
            
            if not analysis_result.solution:
                logger.warning("No solution provided in analysis result for image CAPTCHA")
                return None
            
            # The solution from vision analysis should contain grid positions or instructions
            solution = analysis_result.solution
            
            if analysis_result.confidence_score >= self.config.confidence_threshold:
                logger.info(f"Image CAPTCHA solution: {solution} "
                           f"(confidence: {analysis_result.confidence_score})")
                return solution
            
            logger.warning(f"Image CAPTCHA solution confidence too low: {analysis_result.confidence_score}")
            return None
            
        except Exception as e:
            logger.error(f"Image CAPTCHA solving failed: {e}")
            return None
    
    async def _solve_interactive_captcha(self, analysis_result: CaptchaAnalysisResult) -> Optional[str]:
        """
        Solve interactive CAPTCHAs like reCAPTCHA v2 or hCaptcha.
        
        Args:
            analysis_result: CAPTCHA analysis result
            
        Returns:
            Solution string if successful, None otherwise
        """
        try:
            # Interactive CAPTCHAs often require clicking checkboxes or solving challenges
            # This is complex and may require multiple steps
            
            if analysis_result.captcha_type == CaptchaType.RECAPTCHA_V2:
                return await self._solve_recaptcha_v2(analysis_result)
            elif analysis_result.captcha_type == CaptchaType.HCAPTCHA:
                return await self._solve_hcaptcha(analysis_result)
            
            logger.warning(f"Interactive CAPTCHA type not fully supported: {analysis_result.captcha_type}")
            return None
            
        except Exception as e:
            logger.error(f"Interactive CAPTCHA solving failed: {e}")
            return None
    
    async def _solve_recaptcha_v2(self, analysis_result: CaptchaAnalysisResult) -> Optional[str]:
        """Solve reCAPTCHA v2 challenges."""
        try:
            # Look for "I'm not a robot" checkbox
            checkbox_selectors = [
                ".recaptcha-checkbox-checkmark",
                "#recaptcha-anchor",
                "[role='checkbox'][aria-labelledby*='recaptcha']"
            ]
            
            for selector in checkbox_selectors:
                try:
                    element_selector = ElementSelector(css_selector=selector)
                    click_response = await self.browser_client.click_element(element_selector)
                    
                    if click_response.success:
                        logger.info("Clicked reCAPTCHA checkbox")
                        
                        # Wait for potential challenge to appear
                        await asyncio.sleep(3)
                        
                        # Check if additional challenge appeared
                        challenge_response = await self.browser_client.take_screenshot()
                        if challenge_response.success:
                            # Analyze for image challenge
                            challenge_analysis = await self.vision_client.analyze_captcha(
                                challenge_response.data.get("screenshot_data"),
                                captcha_type=CaptchaType.IMAGE
                            )
                            
                            if challenge_analysis.captcha_detected and challenge_analysis.solution:
                                # This would require implementing image grid selection
                                logger.info("reCAPTCHA image challenge detected")
                                return "recaptcha_challenge_detected"
                        
                        return "recaptcha_checkbox_clicked"
                        
                except Exception as e:
                    logger.debug(f"reCAPTCHA selector {selector} failed: {e}")
                    continue
            
            logger.warning("Could not find reCAPTCHA checkbox")
            return None
            
        except Exception as e:
            logger.error(f"reCAPTCHA v2 solving failed: {e}")
            return None
    
    async def _solve_hcaptcha(self, analysis_result: CaptchaAnalysisResult) -> Optional[str]:
        """Solve hCaptcha challenges."""
        try:
            # hCaptcha typically shows image grids immediately
            # The solution would be in the analysis result
            
            if analysis_result.solution and analysis_result.confidence_score >= self.config.confidence_threshold:
                logger.info(f"hCaptcha solution: {analysis_result.solution}")
                return analysis_result.solution
            
            logger.warning("hCaptcha solution not confident enough or missing")
            return None
            
        except Exception as e:
            logger.error(f"hCaptcha solving failed: {e}")
            return None
    
    async def _solve_generic_captcha(self, analysis_result: CaptchaAnalysisResult) -> Optional[str]:
        """
        Solve generic or unknown CAPTCHA types.
        
        Args:
            analysis_result: CAPTCHA analysis result
            
        Returns:
            Solution string if successful, None otherwise
        """
        try:
            # For generic CAPTCHAs, rely on the vision model analysis
            if (analysis_result.solution and 
                analysis_result.confidence_score >= self.config.confidence_threshold):
                
                logger.info(f"Generic CAPTCHA solution: {analysis_result.solution} "
                           f"(confidence: {analysis_result.confidence_score})")
                return analysis_result.solution
            
            logger.warning(f"Generic CAPTCHA solution confidence too low or missing: "
                          f"{analysis_result.confidence_score}")
            return None
            
        except Exception as e:
            logger.error(f"Generic CAPTCHA solving failed: {e}")
            return None
    
    async def _validate_solution(self, 
                               solution: Optional[str], 
                               captcha_type: Optional[CaptchaType]) -> Dict[str, Any]:
        """
        Validate CAPTCHA solution using AgentCore browser tool feedback.
        
        Args:
            solution: CAPTCHA solution to validate
            captcha_type: Type of CAPTCHA
            
        Returns:
            Validation result dictionary
        """
        if not solution or not captcha_type:
            return {
                "valid": False,
                "error": "No solution or CAPTCHA type provided"
            }
        
        try:
            # Use solution validator to check with browser feedback
            validation_result = await self.solution_validator.validate_solution_with_feedback(
                solution=solution,
                captcha_type=captcha_type
            )
            
            logger.info(f"Solution validation: {validation_result}")
            return validation_result
            
        except Exception as e:
            logger.error(f"Solution validation failed: {e}")
            return {
                "valid": False,
                "error": str(e)
            }
    
    def get_workflow_statistics(self) -> Dict[str, Any]:
        """Get statistics about workflow performance."""
        if not self.workflow_history:
            return {
                "total_workflows": 0,
                "successful_workflows": 0,
                "success_rate": 0.0,
                "average_completion_time_ms": 0.0,
                "active_workflows": len(self.active_workflows),
                "type_statistics": {},
                "status_statistics": {},
                "recent_workflows": []
            }
        
        total_workflows = len(self.workflow_history)
        successful_workflows = sum(1 for w in self.workflow_history if w.success)
        
        # Calculate average times
        completion_times = [w.total_time_ms for w in self.workflow_history if w.total_time_ms and w.total_time_ms > 0]
        avg_completion_time = sum(completion_times) / len(completion_times) if completion_times else 0.0
        
        # Group by CAPTCHA type
        type_stats = {}
        for workflow in self.workflow_history:
            if workflow.captcha_type:
                captcha_type = workflow.captcha_type.value
                if captcha_type not in type_stats:
                    type_stats[captcha_type] = {"total": 0, "successful": 0}
                
                type_stats[captcha_type]["total"] += 1
                if workflow.success:
                    type_stats[captcha_type]["successful"] += 1
        
        # Group by status
        status_stats = {}
        for workflow in self.workflow_history:
            if workflow.status:
                status = workflow.status.value
                status_stats[status] = status_stats.get(status, 0) + 1
        
        return {
            "total_workflows": total_workflows,
            "successful_workflows": successful_workflows,
            "success_rate": successful_workflows / total_workflows if total_workflows > 0 else 0.0,
            "average_completion_time_ms": avg_completion_time,
            "active_workflows": len(self.active_workflows),
            "type_statistics": type_stats,
            "status_statistics": status_stats,
            "recent_workflows": [
                {
                    "success": w.success,
                    "captcha_type": w.captcha_type.value if w.captcha_type else None,
                    "status": w.status.value if w.status else None,
                    "attempts": w.attempts_made,
                    "time_ms": w.total_time_ms
                }
                for w in self.workflow_history[-10:]  # Last 10 workflows
            ]
        }
    
    async def solve_captcha_with_timeout(self, 
                                       page_url: Optional[str] = None,
                                       timeout_seconds: Optional[int] = None) -> WorkflowResult:
        """
        Solve CAPTCHA with configurable timeout.
        
        Args:
            page_url: Optional URL to navigate to first
            timeout_seconds: Override default timeout
            
        Returns:
            WorkflowResult with solving outcome
        """
        timeout = timeout_seconds or self.config.timeout_seconds
        
        try:
            return await asyncio.wait_for(
                self.detect_and_solve_captcha(page_url),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            return WorkflowResult(
                success=False,
                status=WorkflowStatus.TIMEOUT,
                error_message=f"Workflow timeout after {timeout} seconds"
            )


class CaptchaWorkflowManager:
    """Manager for multiple CAPTCHA workflow engines and configurations."""
    
    def __init__(self):
        """Initialize workflow manager."""
        self.engines: Dict[str, CaptchaWorkflowEngine] = {}
        self.default_config = WorkflowConfig()
    
    def create_engine(self, 
                     engine_id: str,
                     browser_client: IBrowserClient,
                     vision_client: Optional[BedrockVisionClient] = None,
                     config: Optional[WorkflowConfig] = None) -> CaptchaWorkflowEngine:
        """
        Create and register a new workflow engine.
        
        Args:
            engine_id: Unique identifier for the engine
            browser_client: AgentCore browser client
            vision_client: Bedrock vision client
            config: Workflow configuration
            
        Returns:
            Created workflow engine
        """
        engine = CaptchaWorkflowEngine(
            browser_client=browser_client,
            vision_client=vision_client,
            config=config or self.default_config
        )
        
        self.engines[engine_id] = engine
        logger.info(f"Created workflow engine: {engine_id}")
        
        return engine
    
    def get_engine(self, engine_id: str) -> Optional[CaptchaWorkflowEngine]:
        """Get workflow engine by ID."""
        return self.engines.get(engine_id)
    
    def remove_engine(self, engine_id: str) -> bool:
        """Remove workflow engine by ID."""
        if engine_id in self.engines:
            del self.engines[engine_id]
            logger.info(f"Removed workflow engine: {engine_id}")
            return True
        return False
    
    def get_global_statistics(self) -> Dict[str, Any]:
        """Get statistics across all workflow engines."""
        total_stats = {
            "total_engines": len(self.engines),
            "total_workflows": 0,
            "successful_workflows": 0,
            "active_workflows": 0,
            "engine_statistics": {}
        }
        
        for engine_id, engine in self.engines.items():
            engine_stats = engine.get_workflow_statistics()
            total_stats["engine_statistics"][engine_id] = engine_stats
            
            total_stats["total_workflows"] += engine_stats.get("total_workflows", 0)
            total_stats["successful_workflows"] += engine_stats.get("successful_workflows", 0)
            total_stats["active_workflows"] += engine_stats.get("active_workflows", 0)
        
        if total_stats["total_workflows"] > 0:
            total_stats["global_success_rate"] = (
                total_stats["successful_workflows"] / total_stats["total_workflows"]
            )
        else:
            total_stats["global_success_rate"] = 0.0
        
        return total_stats