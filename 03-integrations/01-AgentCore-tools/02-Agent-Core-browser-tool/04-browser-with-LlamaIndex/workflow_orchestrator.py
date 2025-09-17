"""
Workflow orchestration capabilities for AgentCore browser tool operations.

This module provides complex multi-step browser automation workflows that coordinate
multiple AgentCore browser tool API calls with intelligent decision-making and
error recovery mechanisms.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import json

from interfaces import IBrowserClient, BrowserResponse, ElementSelector
from exceptions import AgentCoreBrowserError, BrowserErrorType
from vision_models import BedrockVisionClient, CaptchaType


logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """Status of workflow execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class StepStatus(Enum):
    """Status of individual workflow steps."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


class ConditionType(Enum):
    """Types of conditions for workflow branching."""
    ELEMENT_EXISTS = "element_exists"
    TEXT_CONTAINS = "text_contains"
    URL_MATCHES = "url_matches"
    CAPTCHA_DETECTED = "captcha_detected"
    PAGE_LOADED = "page_loaded"
    CUSTOM = "custom"


@dataclass
class WorkflowCondition:
    """Condition for workflow branching and decision-making."""
    condition_type: ConditionType
    parameters: Dict[str, Any] = field(default_factory=dict)
    expected_result: Any = True
    description: str = ""


@dataclass
class WorkflowStep:
    """Individual step in a browser automation workflow."""
    step_id: str
    step_type: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    conditions: List[WorkflowCondition] = field(default_factory=list)
    retry_count: int = 3
    timeout_seconds: int = 30
    on_success: Optional[str] = None  # Next step ID on success
    on_failure: Optional[str] = None  # Next step ID on failure
    description: str = ""
    
    # Runtime state
    status: StepStatus = StepStatus.PENDING
    attempts: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


@dataclass
class WorkflowContext:
    """Context and state management for workflow execution."""
    variables: Dict[str, Any] = field(default_factory=dict)
    session_data: Dict[str, Any] = field(default_factory=dict)
    step_results: Dict[str, Any] = field(default_factory=dict)
    error_history: List[Dict[str, Any]] = field(default_factory=list)
    
    def set_variable(self, key: str, value: Any):
        """Set a workflow variable."""
        self.variables[key] = value
        logger.debug(f"Set workflow variable: {key} = {value}")
    
    def get_variable(self, key: str, default: Any = None) -> Any:
        """Get a workflow variable."""
        return self.variables.get(key, default)
    
    def update_session_data(self, data: Dict[str, Any]):
        """Update session data."""
        self.session_data.update(data)
    
    def record_step_result(self, step_id: str, result: Dict[str, Any]):
        """Record the result of a workflow step."""
        self.step_results[step_id] = result
    
    def record_error(self, step_id: str, error: str, error_type: str = "unknown"):
        """Record an error in the workflow."""
        error_record = {
            "step_id": step_id,
            "error": error,
            "error_type": error_type,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.error_history.append(error_record)


class BrowserWorkflowOrchestrator:
    """Orchestrates complex multi-step browser automation workflows."""
    
    def __init__(self, 
                 browser_client: IBrowserClient,
                 vision_client: Optional[BedrockVisionClient] = None,
                 max_workflow_time: int = 600):  # 10 minutes default
        """
        Initialize workflow orchestrator.
        
        Args:
            browser_client: AgentCore browser client
            vision_client: Vision client for CAPTCHA handling
            max_workflow_time: Maximum workflow execution time in seconds
        """
        self.browser_client = browser_client
        self.vision_client = vision_client
        self.max_workflow_time = max_workflow_time
        
        # Workflow state
        self.current_workflow: Optional[Dict[str, Any]] = None
        self.workflow_context = WorkflowContext()
        self.workflow_status = WorkflowStatus.PENDING
        self.workflow_start_time: Optional[datetime] = None
        
        # Step handlers
        self.step_handlers = {
            "navigate": self._handle_navigate_step,
            "extract_text": self._handle_extract_text_step,
            "screenshot": self._handle_screenshot_step,
            "click_element": self._handle_click_element_step,
            "type_text": self._handle_type_text_step,
            "wait_for_element": self._handle_wait_for_element_step,
            "detect_captcha": self._handle_detect_captcha_step,
            "solve_captcha": self._handle_solve_captcha_step,
            "conditional": self._handle_conditional_step,
            "loop": self._handle_loop_step,
            "delay": self._handle_delay_step,
            "custom": self._handle_custom_step
        }
        
        # Condition evaluators
        self.condition_evaluators = {
            ConditionType.ELEMENT_EXISTS: self._evaluate_element_exists,
            ConditionType.TEXT_CONTAINS: self._evaluate_text_contains,
            ConditionType.URL_MATCHES: self._evaluate_url_matches,
            ConditionType.CAPTCHA_DETECTED: self._evaluate_captcha_detected,
            ConditionType.PAGE_LOADED: self._evaluate_page_loaded,
            ConditionType.CUSTOM: self._evaluate_custom_condition
        }
    
    async def execute_workflow(self, workflow_definition: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a complete browser automation workflow.
        
        Args:
            workflow_definition: Workflow definition dictionary
            
        Returns:
            Workflow execution results
        """
        try:
            # Initialize workflow
            self.current_workflow = workflow_definition
            self.workflow_context = WorkflowContext()
            self.workflow_status = WorkflowStatus.RUNNING
            self.workflow_start_time = datetime.utcnow()
            
            logger.info(f"Starting workflow: {workflow_definition.get('name', 'unnamed')}")
            
            # Parse workflow steps
            steps = self._parse_workflow_steps(workflow_definition.get("steps", []))
            
            # Execute workflow steps
            result = await self._execute_workflow_steps(steps)
            
            # Update final status
            if result.get("success", False):
                self.workflow_status = WorkflowStatus.COMPLETED
            else:
                self.workflow_status = WorkflowStatus.FAILED
            
            # Calculate execution time
            execution_time = (datetime.utcnow() - self.workflow_start_time).total_seconds()
            
            # Prepare final result
            final_result = {
                "workflow_name": workflow_definition.get("name", "unnamed"),
                "success": result.get("success", False),
                "status": self.workflow_status.value,
                "execution_time_seconds": execution_time,
                "steps_executed": len([s for s in steps if s.status in [StepStatus.COMPLETED, StepStatus.FAILED]]),
                "steps_successful": len([s for s in steps if s.status == StepStatus.COMPLETED]),
                "steps_failed": len([s for s in steps if s.status == StepStatus.FAILED]),
                "context_variables": self.workflow_context.variables,
                "step_results": self.workflow_context.step_results,
                "error_history": self.workflow_context.error_history,
                "final_result": result.get("result", {}),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Workflow completed: success={final_result['success']}, "
                       f"time={execution_time:.2f}s, steps={final_result['steps_executed']}")
            
            return final_result
            
        except Exception as e:
            self.workflow_status = WorkflowStatus.FAILED
            error_msg = f"Workflow execution failed: {str(e)}"
            logger.error(error_msg)
            
            return {
                "workflow_name": workflow_definition.get("name", "unnamed"),
                "success": False,
                "status": WorkflowStatus.FAILED.value,
                "error": error_msg,
                "error_type": type(e).__name__,
                "execution_time_seconds": (datetime.utcnow() - self.workflow_start_time).total_seconds() if self.workflow_start_time else 0,
                "context_variables": self.workflow_context.variables,
                "error_history": self.workflow_context.error_history,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def _parse_workflow_steps(self, steps_definition: List[Dict[str, Any]]) -> List[WorkflowStep]:
        """Parse workflow steps from definition."""
        steps = []
        
        for i, step_def in enumerate(steps_definition):
            # Parse conditions
            conditions = []
            for cond_def in step_def.get("conditions", []):
                condition = WorkflowCondition(
                    condition_type=ConditionType(cond_def.get("type", "custom")),
                    parameters=cond_def.get("parameters", {}),
                    expected_result=cond_def.get("expected_result", True),
                    description=cond_def.get("description", "")
                )
                conditions.append(condition)
            
            # Create workflow step
            step = WorkflowStep(
                step_id=step_def.get("id", f"step_{i}"),
                step_type=step_def.get("type", "custom"),
                parameters=step_def.get("parameters", {}),
                conditions=conditions,
                retry_count=step_def.get("retry_count", 3),
                timeout_seconds=step_def.get("timeout_seconds", 30),
                on_success=step_def.get("on_success"),
                on_failure=step_def.get("on_failure"),
                description=step_def.get("description", "")
            )
            
            steps.append(step)
        
        return steps
    
    async def _execute_workflow_steps(self, steps: List[WorkflowStep]) -> Dict[str, Any]:
        """Execute workflow steps with branching logic."""
        if not steps:
            return {"success": True, "result": {}, "message": "No steps to execute"}
        
        # Create step lookup
        step_lookup = {step.step_id: step for step in steps}
        
        # Start with first step
        current_step_id = steps[0].step_id
        executed_steps = []
        
        while current_step_id and current_step_id in step_lookup:
            # Check workflow timeout
            if self._is_workflow_timeout():
                return {
                    "success": False,
                    "error": "Workflow timeout exceeded",
                    "executed_steps": executed_steps
                }
            
            current_step = step_lookup[current_step_id]
            
            # Execute current step
            step_result = await self._execute_single_step(current_step)
            executed_steps.append(current_step_id)
            
            # Record step result
            self.workflow_context.record_step_result(current_step_id, step_result)
            
            # Determine next step based on result
            if step_result.get("success", False):
                next_step_id = current_step.on_success
                if not next_step_id and len(executed_steps) < len(steps):
                    # Default to next step in sequence
                    current_index = next(i for i, s in enumerate(steps) if s.step_id == current_step_id)
                    if current_index + 1 < len(steps):
                        next_step_id = steps[current_index + 1].step_id
            else:
                next_step_id = current_step.on_failure
                
                # If no failure handler and step failed, stop workflow
                if not next_step_id:
                    return {
                        "success": False,
                        "error": f"Step {current_step_id} failed: {step_result.get('error', 'Unknown error')}",
                        "executed_steps": executed_steps,
                        "failed_step": current_step_id
                    }
            
            current_step_id = next_step_id
        
        # Workflow completed successfully
        return {
            "success": True,
            "result": self.workflow_context.step_results,
            "executed_steps": executed_steps,
            "message": "Workflow completed successfully"
        }
    
    async def _execute_single_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Execute a single workflow step with retry logic."""
        step.status = StepStatus.RUNNING
        step.start_time = datetime.utcnow()
        
        logger.info(f"Executing step: {step.step_id} ({step.step_type})")
        
        for attempt in range(step.retry_count + 1):
            step.attempts = attempt + 1
            
            try:
                # Check conditions before execution
                if step.conditions:
                    condition_result = await self._evaluate_conditions(step.conditions)
                    if not condition_result:
                        step.status = StepStatus.SKIPPED
                        return {
                            "success": True,
                            "skipped": True,
                            "reason": "Conditions not met",
                            "step_id": step.step_id
                        }
                
                # Execute step with timeout
                step_result = await asyncio.wait_for(
                    self._execute_step_handler(step),
                    timeout=step.timeout_seconds
                )
                
                # Step succeeded
                step.status = StepStatus.COMPLETED
                step.end_time = datetime.utcnow()
                step.result = step_result
                
                logger.info(f"Step {step.step_id} completed successfully")
                return {
                    "success": True,
                    "result": step_result,
                    "step_id": step.step_id,
                    "attempts": step.attempts
                }
                
            except asyncio.TimeoutError:
                error_msg = f"Step {step.step_id} timed out after {step.timeout_seconds} seconds"
                logger.warning(error_msg)
                
                if attempt < step.retry_count:
                    step.status = StepStatus.RETRYING
                    await asyncio.sleep(min(2 ** attempt, 10))  # Exponential backoff
                    continue
                else:
                    step.status = StepStatus.FAILED
                    step.error_message = error_msg
                    
            except Exception as e:
                error_msg = f"Step {step.step_id} failed: {str(e)}"
                logger.warning(error_msg)
                
                # Record error
                self.workflow_context.record_error(
                    step.step_id, 
                    str(e), 
                    type(e).__name__
                )
                
                if attempt < step.retry_count:
                    step.status = StepStatus.RETRYING
                    await asyncio.sleep(min(2 ** attempt, 10))  # Exponential backoff
                    continue
                else:
                    step.status = StepStatus.FAILED
                    step.error_message = error_msg
        
        # All attempts failed
        step.end_time = datetime.utcnow()
        logger.error(f"Step {step.step_id} failed after {step.attempts} attempts")
        
        return {
            "success": False,
            "error": step.error_message,
            "step_id": step.step_id,
            "attempts": step.attempts
        }
    
    async def _execute_step_handler(self, step: WorkflowStep) -> Dict[str, Any]:
        """Execute the appropriate handler for a step type."""
        handler = self.step_handlers.get(step.step_type)
        
        if not handler:
            raise AgentCoreBrowserError(
                f"Unknown step type: {step.step_type}",
                error_type=BrowserErrorType.CONFIGURATION_ERROR
            )
        
        return await handler(step)
    
    # Step Handlers
    
    async def _handle_navigate_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Handle navigation step."""
        url = step.parameters.get("url")
        if not url:
            raise ValueError("Navigation step requires 'url' parameter")
        
        # Support variable substitution
        url = self._substitute_variables(url)
        
        response = await self.browser_client.navigate(
            url=url,
            wait_for_load=step.parameters.get("wait_for_load", True),
            timeout=step.parameters.get("timeout", 30)
        )
        
        if not response.success:
            raise AgentCoreBrowserError(f"Navigation failed: {response.error_message}")
        
        # Update context with current URL
        self.workflow_context.set_variable("current_url", url)
        self.workflow_context.update_session_data(response.data)
        
        return {
            "url": url,
            "page_title": response.data.get("page_title", ""),
            "load_time": response.data.get("load_time_ms", 0)
        }
    
    async def _handle_extract_text_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Handle text extraction step."""
        # Create element selector if specified
        element_selector = None
        if any(key in step.parameters for key in ["css_selector", "xpath", "element_id"]):
            element_selector = ElementSelector(
                css_selector=step.parameters.get("css_selector"),
                xpath=step.parameters.get("xpath"),
                element_id=step.parameters.get("element_id"),
                text_content=step.parameters.get("text_content")
            )
        
        response = await self.browser_client.extract_text(element_selector)
        
        if not response.success:
            raise AgentCoreBrowserError(f"Text extraction failed: {response.error_message}")
        
        extracted_text = response.data.get("text", "")
        
        # Store text in context variable if specified
        variable_name = step.parameters.get("store_in_variable")
        if variable_name:
            self.workflow_context.set_variable(variable_name, extracted_text)
        
        return {
            "text": extracted_text,
            "text_length": len(extracted_text),
            "element_found": response.data.get("element_found", True)
        }
    
    async def _handle_screenshot_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Handle screenshot step."""
        # Create element selector if specified
        element_selector = None
        if any(key in step.parameters for key in ["css_selector", "xpath", "element_id"]):
            element_selector = ElementSelector(
                css_selector=step.parameters.get("css_selector"),
                xpath=step.parameters.get("xpath"),
                element_id=step.parameters.get("element_id")
            )
        
        response = await self.browser_client.take_screenshot(
            element_selector=element_selector,
            full_page=step.parameters.get("full_page", False)
        )
        
        if not response.success:
            raise AgentCoreBrowserError(f"Screenshot failed: {response.error_message}")
        
        screenshot_data = response.data.get("screenshot_data", "")
        
        # Store screenshot in context variable if specified
        variable_name = step.parameters.get("store_in_variable")
        if variable_name:
            self.workflow_context.set_variable(variable_name, screenshot_data)
        
        return {
            "screenshot_size": len(screenshot_data),
            "screenshot_format": response.data.get("format", "png"),
            "element_found": response.data.get("element_found", True)
        }
    
    async def _handle_click_element_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Handle element click step."""
        # Create element selector
        element_selector = ElementSelector(
            css_selector=step.parameters.get("css_selector"),
            xpath=step.parameters.get("xpath"),
            element_id=step.parameters.get("element_id"),
            text_content=step.parameters.get("text_content")
        )
        
        response = await self.browser_client.click_element(
            element_selector=element_selector,
            wait_for_response=step.parameters.get("wait_for_response", True),
            timeout=step.parameters.get("timeout", 30)
        )
        
        if not response.success:
            raise AgentCoreBrowserError(f"Element click failed: {response.error_message}")
        
        return {
            "element_found": response.data.get("element_found", True),
            "click_successful": response.data.get("click_successful", True),
            "page_changed": response.data.get("page_changed", False),
            "new_url": response.data.get("new_url")
        }
    
    async def _handle_type_text_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Handle text typing step."""
        # Create element selector
        element_selector = ElementSelector(
            css_selector=step.parameters.get("css_selector"),
            xpath=step.parameters.get("xpath"),
            element_id=step.parameters.get("element_id")
        )
        
        text = step.parameters.get("text", "")
        # Support variable substitution
        text = self._substitute_variables(text)
        
        response = await self.browser_client.type_text(
            element_selector=element_selector,
            text=text,
            clear_first=step.parameters.get("clear_first", True),
            typing_delay=step.parameters.get("typing_delay")
        )
        
        if not response.success:
            raise AgentCoreBrowserError(f"Text typing failed: {response.error_message}")
        
        return {
            "text_entered": text,
            "element_found": response.data.get("element_found", True),
            "typing_successful": response.data.get("typing_successful", True)
        }
    
    async def _handle_wait_for_element_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Handle wait for element step."""
        # Create element selector
        element_selector = ElementSelector(
            css_selector=step.parameters.get("css_selector"),
            xpath=step.parameters.get("xpath"),
            element_id=step.parameters.get("element_id"),
            text_content=step.parameters.get("text_content")
        )
        
        response = await self.browser_client.wait_for_element(
            element_selector=element_selector,
            timeout=step.parameters.get("timeout", 30),
            visible=step.parameters.get("visible", True)
        )
        
        if not response.success:
            raise AgentCoreBrowserError(f"Wait for element failed: {response.error_message}")
        
        return {
            "element_found": response.data.get("element_found", True),
            "element_visible": response.data.get("element_visible", True),
            "wait_time": response.data.get("wait_time_ms", 0)
        }
    
    async def _handle_detect_captcha_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Handle CAPTCHA detection step."""
        if not self.vision_client:
            raise AgentCoreBrowserError("Vision client required for CAPTCHA detection")
        
        # Take screenshot for analysis
        screenshot_response = await self.browser_client.take_screenshot(full_page=False)
        if not screenshot_response.success:
            raise AgentCoreBrowserError("Failed to capture screenshot for CAPTCHA detection")
        
        screenshot_data = screenshot_response.data.get("screenshot_data", "")
        if not screenshot_data:
            raise AgentCoreBrowserError("No screenshot data available")
        
        # Analyze with vision model
        import base64
        image_bytes = base64.b64decode(screenshot_data)
        analysis_result = await self.vision_client.analyze_captcha(image_bytes)
        
        # Store results in context
        self.workflow_context.set_variable("captcha_detected", analysis_result.captcha_detected)
        self.workflow_context.set_variable("captcha_type", analysis_result.captcha_type.value if analysis_result.captcha_type else None)
        self.workflow_context.set_variable("captcha_solution", analysis_result.solution)
        
        return {
            "captcha_detected": analysis_result.captcha_detected,
            "captcha_type": analysis_result.captcha_type.value if analysis_result.captcha_type else None,
            "confidence_score": analysis_result.confidence_score,
            "solution": analysis_result.solution,
            "processing_time_ms": analysis_result.processing_time_ms
        }
    
    async def _handle_solve_captcha_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Handle CAPTCHA solving step."""
        # This would integrate with the CAPTCHA solving workflow
        # For now, return a placeholder
        return {
            "success": False,
            "message": "CAPTCHA solving step not fully implemented",
            "requires": "Integration with captcha_workflows.py"
        }
    
    async def _handle_conditional_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Handle conditional branching step."""
        conditions_met = await self._evaluate_conditions(step.conditions)
        
        return {
            "conditions_met": conditions_met,
            "condition_count": len(step.conditions)
        }
    
    async def _handle_loop_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Handle loop step."""
        max_iterations = step.parameters.get("max_iterations", 10)
        loop_condition = step.parameters.get("condition", {})
        
        iterations = 0
        while iterations < max_iterations:
            # Check loop condition
            if loop_condition:
                condition = WorkflowCondition(
                    condition_type=ConditionType(loop_condition.get("type", "custom")),
                    parameters=loop_condition.get("parameters", {}),
                    expected_result=loop_condition.get("expected_result", True)
                )
                
                if not await self._evaluate_conditions([condition]):
                    break
            
            iterations += 1
            
            # Add delay between iterations
            delay = step.parameters.get("iteration_delay", 1)
            await asyncio.sleep(delay)
        
        return {
            "iterations_completed": iterations,
            "max_iterations": max_iterations
        }
    
    async def _handle_delay_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Handle delay step."""
        delay_seconds = step.parameters.get("seconds", 1)
        await asyncio.sleep(delay_seconds)
        
        return {
            "delay_seconds": delay_seconds
        }
    
    async def _handle_custom_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Handle custom step with user-defined logic."""
        # This would allow users to inject custom step handlers
        return {
            "success": False,
            "message": "Custom step handler not implemented",
            "step_id": step.step_id
        }
    
    # Condition Evaluators
    
    async def _evaluate_conditions(self, conditions: List[WorkflowCondition]) -> bool:
        """Evaluate a list of conditions (AND logic)."""
        for condition in conditions:
            evaluator = self.condition_evaluators.get(condition.condition_type)
            if not evaluator:
                logger.warning(f"Unknown condition type: {condition.condition_type}")
                continue
            
            try:
                result = await evaluator(condition)
                if not result:
                    return False
            except Exception as e:
                logger.warning(f"Condition evaluation failed: {e}")
                return False
        
        return True
    
    async def _evaluate_element_exists(self, condition: WorkflowCondition) -> bool:
        """Evaluate if an element exists on the page."""
        element_selector = ElementSelector(
            css_selector=condition.parameters.get("css_selector"),
            xpath=condition.parameters.get("xpath"),
            element_id=condition.parameters.get("element_id")
        )
        
        response = await self.browser_client.extract_text(element_selector)
        exists = response.success and response.data.get("element_found", False)
        
        return exists == condition.expected_result
    
    async def _evaluate_text_contains(self, condition: WorkflowCondition) -> bool:
        """Evaluate if page text contains specific content."""
        search_text = condition.parameters.get("text", "")
        case_sensitive = condition.parameters.get("case_sensitive", False)
        
        # Extract page text
        response = await self.browser_client.extract_text()
        if not response.success:
            return False
        
        page_text = response.data.get("text", "")
        
        if not case_sensitive:
            page_text = page_text.lower()
            search_text = search_text.lower()
        
        contains = search_text in page_text
        return contains == condition.expected_result
    
    async def _evaluate_url_matches(self, condition: WorkflowCondition) -> bool:
        """Evaluate if current URL matches pattern."""
        pattern = condition.parameters.get("pattern", "")
        current_url = self.workflow_context.get_variable("current_url", "")
        
        import re
        matches = bool(re.search(pattern, current_url))
        return matches == condition.expected_result
    
    async def _evaluate_captcha_detected(self, condition: WorkflowCondition) -> bool:
        """Evaluate if CAPTCHA is detected on page."""
        captcha_detected = self.workflow_context.get_variable("captcha_detected", False)
        return captcha_detected == condition.expected_result
    
    async def _evaluate_page_loaded(self, condition: WorkflowCondition) -> bool:
        """Evaluate if page is fully loaded."""
        # This would check page loading state
        # For now, assume page is loaded if we can extract text
        response = await self.browser_client.extract_text()
        loaded = response.success
        return loaded == condition.expected_result
    
    async def _evaluate_custom_condition(self, condition: WorkflowCondition) -> bool:
        """Evaluate custom condition."""
        # This would allow users to inject custom condition evaluators
        return condition.expected_result
    
    # Utility Methods
    
    def _substitute_variables(self, text: str) -> str:
        """Substitute workflow variables in text."""
        if not isinstance(text, str):
            return text
        
        for key, value in self.workflow_context.variables.items():
            placeholder = f"{{{key}}}"
            if placeholder in text:
                text = text.replace(placeholder, str(value))
        
        return text
    
    def _is_workflow_timeout(self) -> bool:
        """Check if workflow has exceeded maximum execution time."""
        if not self.workflow_start_time:
            return False
        
        elapsed = (datetime.utcnow() - self.workflow_start_time).total_seconds()
        return elapsed > self.max_workflow_time
    
    def get_workflow_status(self) -> Dict[str, Any]:
        """Get current workflow status and progress."""
        return {
            "status": self.workflow_status.value,
            "start_time": self.workflow_start_time.isoformat() if self.workflow_start_time else None,
            "elapsed_seconds": (datetime.utcnow() - self.workflow_start_time).total_seconds() if self.workflow_start_time else 0,
            "context_variables": self.workflow_context.variables,
            "error_count": len(self.workflow_context.error_history),
            "workflow_name": self.current_workflow.get("name", "unnamed") if self.current_workflow else None
        }