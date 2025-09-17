"""
Main integration class for LlamaIndex + AgentCore browser tool.

This module provides the primary interface for integrating LlamaIndex agents
with AgentCore's browser automation capabilities.
"""

import logging
from typing import Dict, Any, Optional, List
import asyncio
from datetime import datetime

from client import AgentCoreBrowserClient
from config import ConfigurationManager, IntegrationConfig
from exceptions import AgentCoreBrowserError, ConfigurationError
from workflow_orchestrator import BrowserWorkflowOrchestrator

logger = logging.getLogger(__name__)


class LlamaIndexAgentCoreIntegration:
    """
    Main integration class for LlamaIndex + AgentCore browser tool.
    
    This class serves as the primary entry point for developers who want to
    integrate LlamaIndex agents with AgentCore's browser automation service.
    """
    
    def __init__(self, 
                 config_path: Optional[str] = None,
                 config_manager: Optional[ConfigurationManager] = None,
                 aws_credentials: Optional[Dict[str, str]] = None,
                 llm_model: Optional[str] = None,
                 vision_model: Optional[str] = None):
        """
        Initialize the LlamaIndex-AgentCore integration.
        
        Args:
            config_path: Path to configuration file
            config_manager: Pre-configured configuration manager
            aws_credentials: AWS credentials dictionary
            llm_model: LlamaIndex LLM model identifier
            vision_model: LlamaIndex vision model identifier
        """
        # Initialize configuration
        self.config_manager = config_manager or ConfigurationManager(config_path)
        
        # Override configuration with provided parameters
        if aws_credentials or llm_model or vision_model:
            self._override_config(aws_credentials, llm_model, vision_model)
        
        # Initialize components
        self.browser_client: Optional[AgentCoreBrowserClient] = None
        self.llm = None
        self.vision_llm = None
        self.agent = None
        self.tools: List[Any] = []
        self.workflow_orchestrator: Optional[BrowserWorkflowOrchestrator] = None
        
        # Load configuration and initialize components
        self._initialize_components()
    
    def _override_config(self, 
                        aws_credentials: Optional[Dict[str, str]] = None,
                        llm_model: Optional[str] = None,
                        vision_model: Optional[str] = None):
        """Override configuration with provided parameters."""
        try:
            config = self.config_manager.get_integration_config()
            
            if aws_credentials:
                for key, value in aws_credentials.items():
                    if key == 'region':
                        config.aws_credentials.region = value
                    elif key == 'aws_access_key_id':
                        config.aws_credentials.access_key_id = value
                    elif key == 'aws_secret_access_key':
                        config.aws_credentials.secret_access_key = value
                    elif key == 'aws_session_token':
                        config.aws_credentials.session_token = value
                    elif key == 'profile':
                        config.aws_credentials.profile = value
            
            if llm_model:
                config.llm_model = llm_model
            
            if vision_model:
                config.vision_model = vision_model
            
            # Update the configuration manager with modified config
            self.config_manager._config = config
            
        except Exception as e:
            raise ConfigurationError(f"Failed to override configuration: {str(e)}")
    
    def _initialize_components(self):
        """Initialize LlamaIndex and AgentCore components."""
        try:
            # Load configuration
            config = self.config_manager.get_integration_config()
            
            # Initialize browser client
            self.browser_client = AgentCoreBrowserClient(self.config_manager)
            
            # Initialize LlamaIndex components (placeholders for now)
            self._initialize_llm_components(config)
            
            # Create browser tools (will be implemented in later tasks)
            self.tools = self._create_browser_tools()
            
            # Create agent (will be implemented in later tasks)
            self.agent = self._create_agent()
            
            # Initialize workflow orchestrator
            self.workflow_orchestrator = self._create_workflow_orchestrator()
            
            logger.info("LlamaIndex-AgentCore integration initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize integration components: {e}")
            raise ConfigurationError(f"Integration initialization failed: {str(e)}")
    
    def _initialize_llm_components(self, config: IntegrationConfig):
        """
        Initialize LlamaIndex LLM components.
        
        Args:
            config: Integration configuration
        """
        try:
            # Import LlamaIndex components
            from llama_index.llms.bedrock import Bedrock
            from llama_index.multi_modal_llms.bedrock import BedrockMultiModal
            
            # Get AWS credentials for Bedrock
            aws_credentials = self.config_manager.get_aws_credentials()
            
            # Initialize LLM for text reasoning
            self.llm = Bedrock(
                model=config.llm_model,
                region_name=aws_credentials.get('region', 'us-east-1'),
                aws_access_key_id=aws_credentials.get('aws_access_key_id'),
                aws_secret_access_key=aws_credentials.get('aws_secret_access_key'),
                aws_session_token=aws_credentials.get('aws_session_token'),
                max_tokens=4096,
                temperature=0.1
            )
            
            # Initialize multi-modal LLM for vision tasks
            self.vision_llm = BedrockMultiModal(
                model=config.vision_model,
                region_name=aws_credentials.get('region', 'us-east-1'),
                aws_access_key_id=aws_credentials.get('aws_access_key_id'),
                aws_secret_access_key=aws_credentials.get('aws_secret_access_key'),
                aws_session_token=aws_credentials.get('aws_session_token'),
                max_tokens=4096,
                temperature=0.1
            )
            
            logger.info(f"Initialized LLM model: {config.llm_model}")
            logger.info(f"Initialized vision model: {config.vision_model}")
            
        except ImportError as e:
            logger.warning(f"LlamaIndex Bedrock components not available: {e}")
            logger.info("Using placeholder LLM components for testing")
            self.llm = None
            self.vision_llm = None
        except Exception as e:
            logger.error(f"Failed to initialize LLM components: {e}")
            self.llm = None
            self.vision_llm = None
    
    def _create_browser_tools(self) -> List[Any]:
        """
        Create LlamaIndex tools that wrap AgentCore browser functionality.
        
        Returns:
            List of LlamaIndex tools
        """
        tools = []
        
        try:
            # Import tool implementations
            from tools import (
                BrowserNavigationTool, TextExtractionTool, ScreenshotCaptureTool,
                ElementClickTool, FormInteractionTool
            )
            from captcha_tools import (
                AdvancedCaptchaDetectionTool, CaptchaSolvingTool, TextCaptchaSolvingTool
            )
            from vision_models import BedrockVisionClient
            
            # Create vision client for CAPTCHA tools
            vision_client = BedrockVisionClient(self.config_manager)
            
            # Create core browser tools
            tools.extend([
                BrowserNavigationTool(self.browser_client),
                TextExtractionTool(self.browser_client),
                ScreenshotCaptureTool(self.browser_client),
                ElementClickTool(self.browser_client),
                FormInteractionTool(self.browser_client)
            ])
            
            # Create CAPTCHA tools
            tools.extend([
                AdvancedCaptchaDetectionTool(self.browser_client, vision_client),
                CaptchaSolvingTool(self.browser_client, vision_client),
                TextCaptchaSolvingTool(self.browser_client, vision_client)
            ])
            
            logger.info(f"Created {len(tools)} browser tools for LlamaIndex agent")
            
        except ImportError as e:
            logger.warning(f"Some tool implementations not available: {e}")
            logger.info("Using minimal tool set")
            
        except Exception as e:
            logger.error(f"Failed to create browser tools: {e}")
            
        return tools
    
    def _create_agent(self) -> Any:
        """
        Create LlamaIndex ReActAgent with browser tools.
        
        Returns:
            LlamaIndex agent instance
        """
        try:
            # Import LlamaIndex agent components
            from llama_index.core.agent import ReActAgent
            from llama_index.core.memory import ChatMemoryBuffer
            
            # Check if we have LLM and tools
            if not self.llm:
                logger.warning("No LLM available, cannot create agent")
                return None
                
            if not self.tools:
                logger.warning("No tools available, cannot create agent")
                return None
            
            # Create chat memory for conversation history
            memory = ChatMemoryBuffer.from_defaults(token_limit=8192)
            
            # Create ReActAgent with browser tools
            agent = ReActAgent.from_tools(
                tools=self.tools,
                llm=self.llm,
                memory=memory,
                verbose=True,
                max_iterations=10,
                system_prompt=self._get_system_prompt()
            )
            
            logger.info(f"Created LlamaIndex ReActAgent with {len(self.tools)} tools")
            return agent
            
        except ImportError as e:
            logger.warning(f"LlamaIndex agent components not available: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to create LlamaIndex agent: {e}")
            return None
    
    def _create_workflow_orchestrator(self) -> Optional[BrowserWorkflowOrchestrator]:
        """
        Create workflow orchestrator for complex browser automation.
        
        Returns:
            BrowserWorkflowOrchestrator instance
        """
        try:
            from vision_models import BedrockVisionClient
            
            # Create vision client for CAPTCHA handling
            vision_client = BedrockVisionClient(self.config_manager)
            
            # Create workflow orchestrator
            orchestrator = BrowserWorkflowOrchestrator(
                browser_client=self.browser_client,
                vision_client=vision_client,
                max_workflow_time=600  # 10 minutes
            )
            
            logger.info("Created workflow orchestrator for complex browser automation")
            return orchestrator
            
        except Exception as e:
            logger.warning(f"Failed to create workflow orchestrator: {e}")
            return None
    
    def _get_system_prompt(self) -> str:
        """
        Get system prompt for LlamaIndex agent.
        
        Returns:
            System prompt string
        """
        return """
You are an intelligent web automation agent with access to AgentCore's secure browser tool capabilities. 
You can navigate websites, extract content, interact with elements, and handle CAPTCHAs using enterprise-grade infrastructure.

Your capabilities include:
- Navigate to URLs and wait for page loading
- Extract text content from pages or specific elements
- Capture screenshots for visual analysis
- Click buttons, links, and interactive elements
- Fill out forms and interact with input fields
- Detect and solve various types of CAPTCHAs using vision models
- Handle complex multi-step browser workflows

When working with websites:
1. Always navigate to the URL first before attempting other operations
2. Use screenshots to understand page layout when needed
3. Extract text content to understand page context
4. Handle CAPTCHAs automatically when encountered
5. Be patient with page loading and element visibility
6. Provide clear explanations of what you're doing and what you find

For CAPTCHA handling:
- Detect CAPTCHAs using both DOM analysis and visual inspection
- Use appropriate solving strategies based on CAPTCHA type
- Validate solutions and retry if necessary
- Report confidence levels and success rates

Always prioritize security and follow best practices for web automation.
"""

    async def process_web_content(self, url: str) -> Dict[str, Any]:
        """
        Process web content using integrated browser capabilities.
        
        Args:
            url: URL to process
            
        Returns:
            Processing results
            
        Raises:
            AgentCoreBrowserError: If processing fails
        """
        if not self.agent:
            logger.warning("No agent available, using basic browser operations")
            return await self._basic_web_processing(url)
        
        try:
            # Use LlamaIndex agent to process web content intelligently
            prompt = f"""
            Please navigate to {url} and analyze the web content. Perform the following tasks:
            
            1. Navigate to the URL and wait for it to load completely
            2. Take a screenshot to see the page layout
            3. Extract the main text content from the page
            4. Check for any CAPTCHAs or interactive elements that need attention
            5. Provide a summary of what you found on the page
            
            If you encounter any CAPTCHAs, please detect and solve them automatically.
            """
            
            # Execute agent workflow
            response = await self.agent.achat(prompt)
            
            return {
                "success": True,
                "url": url,
                "agent_response": str(response),
                "processing_method": "llamaindex_agent",
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Agent-based web processing failed: {e}")
            # Fallback to basic processing
            return await self._basic_web_processing(url)
    
    async def _basic_web_processing(self, url: str) -> Dict[str, Any]:
        """
        Basic web content processing without agent.
        
        Args:
            url: URL to process
            
        Returns:
            Basic processing results
        """
        if not self.browser_client:
            raise AgentCoreBrowserError("Browser client not initialized")
        
        try:
            # Create session
            session_id = await self.browser_client.create_session()
            logger.info(f"Created browser session: {session_id}")
            
            # Navigate to URL
            nav_response = await self.browser_client.navigate(url)
            if not nav_response.success:
                raise AgentCoreBrowserError(f"Navigation failed: {nav_response.error_message}")
            
            # Extract text content
            text_response = await self.browser_client.extract_text()
            text_content = text_response.data.get("text", "") if text_response.success else ""
            
            # Take screenshot
            screenshot_response = await self.browser_client.take_screenshot()
            screenshot_data = screenshot_response.data.get("screenshot_data", "") if screenshot_response.success else ""
            
            # Close session
            await self.browser_client.close_session()
            
            return {
                "success": True,
                "url": url,
                "text_content": text_content,
                "text_length": len(text_content),
                "screenshot_available": bool(screenshot_data),
                "screenshot_size": len(screenshot_data) if screenshot_data else 0,
                "processing_method": "basic_browser_operations",
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Basic web processing failed: {e}")
            raise
    
    async def detect_captcha(self, url: str) -> Dict[str, Any]:
        """
        Detect CAPTCHAs on a web page.
        
        Args:
            url: URL to analyze for CAPTCHAs
            
        Returns:
            CAPTCHA detection results
        """
        # Placeholder implementation
        # This will be fully implemented in task 3.4
        logger.info(f"CAPTCHA detection for {url} will be implemented in task 3.4")
        
        return {
            "status": "placeholder_implementation",
            "url": url,
            "captcha_detected": False,
            "message": "Full CAPTCHA detection will be available in task 3.4"
        }
    
    async def solve_captcha(self, captcha_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Solve a detected CAPTCHA.
        
        Args:
            captcha_data: CAPTCHA information from detection
            
        Returns:
            CAPTCHA solution results
        """
        # Placeholder implementation
        # This will be fully implemented in task 4.2
        logger.info("CAPTCHA solving will be implemented in task 4.2")
        
        return {
            "status": "placeholder_implementation",
            "captcha_data": captcha_data,
            "solution": None,
            "message": "Full CAPTCHA solving will be available in task 4.2"
        }
    
    def get_configuration(self) -> Dict[str, Any]:
        """
        Get current integration configuration.
        
        Returns:
            Configuration dictionary
        """
        return self.config_manager.get_integration_config().to_dict()
    
    def get_browser_client(self) -> AgentCoreBrowserClient:
        """
        Get the browser client instance.
        
        Returns:
            Browser client instance
            
        Raises:
            AgentCoreBrowserError: If client not initialized
        """
        if not self.browser_client:
            raise AgentCoreBrowserError("Browser client not initialized")
        return self.browser_client
    
    def get_tools(self) -> List[Any]:
        """
        Get list of available browser tools.
        
        Returns:
            List of LlamaIndex tools
        """
        return self.tools
    
    async def close(self):
        """Close the integration and clean up resources."""
        if self.browser_client:
            await self.browser_client.close()
        
        logger.info("LlamaIndex-AgentCore integration closed")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def chat_with_agent(self, message: str) -> str:
        """
        Chat with the LlamaIndex agent directly.
        
        Args:
            message: Message to send to the agent
            
        Returns:
            Agent response string
        """
        if not self.agent:
            return "Agent not available. Please check LlamaIndex installation and configuration."
        
        try:
            response = await self.agent.achat(message)
            return str(response)
        except Exception as e:
            logger.error(f"Agent chat failed: {e}")
            return f"Agent chat error: {str(e)}"
    
    def get_agent_tools_info(self) -> List[Dict[str, Any]]:
        """
        Get information about available agent tools.
        
        Returns:
            List of tool information dictionaries
        """
        tools_info = []
        
        for tool in self.tools:
            try:
                tool_info = {
                    "name": tool.metadata.name,
                    "description": tool.metadata.description,
                    "tool_class": tool.__class__.__name__
                }
                
                # Add schema information if available
                if hasattr(tool.metadata, 'fn_schema') and tool.metadata.fn_schema:
                    tool_info["schema"] = tool.metadata.fn_schema.schema()
                
                tools_info.append(tool_info)
                
            except Exception as e:
                logger.warning(f"Failed to get info for tool {tool}: {e}")
                tools_info.append({
                    "name": "unknown",
                    "description": "Tool information unavailable",
                    "tool_class": tool.__class__.__name__,
                    "error": str(e)
                })
        
        return tools_info
    
    def get_integration_status(self) -> Dict[str, Any]:
        """
        Get current integration status and health information.
        
        Returns:
            Status information dictionary
        """
        return {
            "browser_client_initialized": self.browser_client is not None,
            "llm_initialized": self.llm is not None,
            "vision_llm_initialized": self.vision_llm is not None,
            "agent_initialized": self.agent is not None,
            "tools_count": len(self.tools),
            "tools_available": [tool.metadata.name for tool in self.tools if hasattr(tool, 'metadata')],
            "configuration_loaded": self.config_manager is not None,
            "workflow_orchestrator_initialized": self.workflow_orchestrator is not None,
            "integration_ready": all([
                self.browser_client is not None,
                len(self.tools) > 0,
                self.config_manager is not None
            ])
        }
    
    async def execute_workflow(self, workflow_definition: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a complex multi-step browser automation workflow.
        
        Args:
            workflow_definition: Workflow definition dictionary
            
        Returns:
            Workflow execution results
            
        Raises:
            AgentCoreBrowserError: If workflow execution fails
        """
        if not self.workflow_orchestrator:
            raise AgentCoreBrowserError("Workflow orchestrator not initialized")
        
        try:
            logger.info(f"Executing workflow: {workflow_definition.get('name', 'unnamed')}")
            result = await self.workflow_orchestrator.execute_workflow(workflow_definition)
            
            logger.info(f"Workflow execution completed: success={result.get('success', False)}")
            return result
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            raise AgentCoreBrowserError(f"Workflow execution failed: {str(e)}")
    
    async def execute_captcha_workflow(self, url: str, max_attempts: int = 3) -> Dict[str, Any]:
        """
        Execute a specialized workflow for CAPTCHA detection and solving.
        
        Args:
            url: URL to navigate to and check for CAPTCHAs
            max_attempts: Maximum number of solving attempts
            
        Returns:
            CAPTCHA workflow results
        """
        workflow_definition = {
            "name": "captcha_detection_and_solving",
            "description": "Detect and solve CAPTCHAs on a web page",
            "steps": [
                {
                    "id": "navigate",
                    "type": "navigate",
                    "parameters": {"url": url, "wait_for_load": True},
                    "description": "Navigate to target URL"
                },
                {
                    "id": "detect_captcha",
                    "type": "detect_captcha",
                    "parameters": {"include_screenshot": True},
                    "description": "Detect CAPTCHAs on the page"
                },
                {
                    "id": "solve_captcha",
                    "type": "solve_captcha",
                    "parameters": {"max_attempts": max_attempts},
                    "conditions": [
                        {
                            "type": "captcha_detected",
                            "expected_result": True,
                            "description": "Only solve if CAPTCHA detected"
                        }
                    ],
                    "description": "Solve detected CAPTCHA"
                }
            ]
        }
        
        return await self.execute_workflow(workflow_definition)
    
    async def execute_form_filling_workflow(self, 
                                          url: str, 
                                          form_data: Dict[str, str],
                                          submit_selector: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute a workflow for filling out web forms.
        
        Args:
            url: URL containing the form
            form_data: Dictionary of field selectors to values
            submit_selector: CSS selector for submit button
            
        Returns:
            Form filling workflow results
        """
        steps = [
            {
                "id": "navigate",
                "type": "navigate",
                "parameters": {"url": url, "wait_for_load": True},
                "description": "Navigate to form page"
            }
        ]
        
        # Add form filling steps
        for i, (selector, value) in enumerate(form_data.items()):
            steps.append({
                "id": f"fill_field_{i}",
                "type": "type_text",
                "parameters": {
                    "css_selector": selector,
                    "text": value,
                    "clear_first": True
                },
                "description": f"Fill form field: {selector}"
            })
        
        # Add submit step if selector provided
        if submit_selector:
            steps.append({
                "id": "submit_form",
                "type": "click_element",
                "parameters": {
                    "css_selector": submit_selector,
                    "wait_for_response": True
                },
                "description": "Submit the form"
            })
        
        workflow_definition = {
            "name": "form_filling_workflow",
            "description": "Fill out and submit a web form",
            "steps": steps
        }
        
        return await self.execute_workflow(workflow_definition)
    
    async def execute_content_extraction_workflow(self, 
                                                url: str,
                                                extraction_rules: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Execute a workflow for extracting structured content from web pages.
        
        Args:
            url: URL to extract content from
            extraction_rules: List of extraction rule dictionaries
            
        Returns:
            Content extraction workflow results
        """
        steps = [
            {
                "id": "navigate",
                "type": "navigate",
                "parameters": {"url": url, "wait_for_load": True},
                "description": "Navigate to content page"
            },
            {
                "id": "screenshot",
                "type": "screenshot",
                "parameters": {"full_page": False},
                "description": "Take page screenshot"
            }
        ]
        
        # Add extraction steps
        for i, rule in enumerate(extraction_rules):
            steps.append({
                "id": f"extract_{i}",
                "type": "extract_text",
                "parameters": {
                    "css_selector": rule.get("selector"),
                    "xpath": rule.get("xpath"),
                    "store_in_variable": rule.get("variable_name", f"extracted_content_{i}")
                },
                "description": f"Extract content: {rule.get('description', f'Rule {i}')}"
            })
        
        workflow_definition = {
            "name": "content_extraction_workflow",
            "description": "Extract structured content from web page",
            "steps": steps
        }
        
        return await self.execute_workflow(workflow_definition)
    
    def get_workflow_status(self) -> Dict[str, Any]:
        """
        Get current workflow execution status.
        
        Returns:
            Workflow status dictionary
        """
        if not self.workflow_orchestrator:
            return {"error": "Workflow orchestrator not initialized"}
        
        return self.workflow_orchestrator.get_workflow_status()
    
    def create_custom_workflow(self, 
                             name: str,
                             steps: List[Dict[str, Any]],
                             description: str = "") -> Dict[str, Any]:
        """
        Create a custom workflow definition.
        
        Args:
            name: Workflow name
            steps: List of workflow step definitions
            description: Workflow description
            
        Returns:
            Workflow definition dictionary
        """
        return {
            "name": name,
            "description": description,
            "steps": steps,
            "created_at": datetime.utcnow().isoformat(),
            "version": "1.0"
        }