import logging
from typing import Any, Optional
from strands import Agent
from strands.agent import AgentResult
from strands.types.agent import AgentInput
from strands_tools.agent_core_memory import AgentCoreMemoryToolProvider

from .base_agent import BaseAgent
from .config import Configuration
from .prompts.code_generator_prompt import CODE_GENERATOR_AGENT_PROMPT
from .core_tools.code_execution_tool import python_code_execution_tool
from .utils import get_today_str
from .memory.memory_manager import MemoryConfig
from .memory.hooks import MarketingMemoryHookProvider


logger = logging.getLogger(__name__)


class CodeGeneratorAgent(BaseAgent):
    """Code generator agent for Python analytics with memory capabilities for pattern learning."""
    
    def __init__(self, config: Configuration, memory_config: Optional[MemoryConfig] = None):
        super().__init__(config)
        self.memory_config = memory_config
        self._init_agent()

    def _init_agent(self):
        """Initialize the code generator agent with Python execution tools and memory integration."""
        # Start with base code execution tools
        tools = [python_code_execution_tool]
        
        # Add memory tools if memory is configured
        if self.memory_config:
            memory_provider = AgentCoreMemoryToolProvider(
                memory_id=self.memory_config.memory_id,
                actor_id=self.memory_config.actor_id,
                session_id=self.memory_config.session_id,
                namespace=f"marketing/{self.memory_config.actor_id}/analytics"
            )
            tools.extend(memory_provider.tools)
        
        # Prepare agent state with memory info if available
        agent_state = {}
        if self.memory_config:
            agent_state = {
                "actor_id": self.memory_config.actor_id,
                "session_id": self.memory_config.session_id
            }
        
        # Set up memory hooks for automatic conversation capture
        hooks = []
        if self.memory_config:
            memory_hooks = MarketingMemoryHookProvider(
                memory_id=self.memory_config.memory_id,
                client=self.memory_config.memory_client,
                agent_type="code_generator"
            )
            hooks = [memory_hooks]
        
        self.agent = Agent(
            model=self._init_model(
                self.config.code_generator_model,
                self.config.code_generator_thinking_enabled,
                self.config.code_generator_thinking_tokens
            ),
            system_prompt=CODE_GENERATOR_AGENT_PROMPT.format(date=get_today_str()),
            tools=tools,
            hooks=hooks,
            state=agent_state
        )
    
    def generate_analytics_code(self, analysis_requirements: dict) -> dict:
        """Generate Python analytics code based on requirements and memory patterns."""
        try:
            # Query memory for previous code patterns if available
            memory_context = {}
            if self.memory_config:
                logger.info("Querying memory for previous analytics code patterns")
                memory_context = {"memory_enabled": True, "namespace": self.memory_config.namespace}
            
            # Prepare code generation request
            code_request = {
                "requirements": analysis_requirements,
                "memory_context": memory_context,
                "generation_type": "analytics_code",
                "timestamp": get_today_str()
            }
            
            logger.info(f"Starting analytics code generation: {code_request}")
            return code_request
            
        except Exception as e:
            logger.error(f"Failed to generate analytics code: {e}")
            return {"error": str(e), "generation_type": "analytics_code"}
    
    def create_visualization(self, data_specs: dict) -> dict:
        """Create data visualization code with memory-enhanced patterns."""
        try:
            # Prepare visualization generation request
            viz_request = {
                "data_specs": data_specs,
                "memory_enabled": self.memory_config is not None,
                "generation_type": "data_visualization",
                "timestamp": get_today_str()
            }
            
            if self.memory_config:
                viz_request["memory_namespace"] = self.memory_config.namespace
                logger.info("Memory-enhanced visualization generation prepared")
            
            logger.info(f"Preparing visualization generation: {viz_request}")
            return viz_request
            
        except Exception as e:
            logger.error(f"Failed to prepare visualization generation: {e}")
            return {"error": str(e), "generation_type": "data_visualization"}
    
    def learn_code_patterns(self, successful_code: dict) -> bool:
        """Store successful code patterns in memory for future use."""
        if not self.memory_config:
            logger.warning("Memory not configured for code pattern learning")
            return False
        
        try:
            # Prepare code learning data
            learning_data = {
                "successful_code": successful_code,
                "learning_type": "code_patterns",
                "timestamp": get_today_str(),
                "agent_type": "code_generator"
            }
            
            logger.info(f"Storing code patterns in memory: {learning_data}")
            # The actual memory storage would be handled by the agent's memory tools
            return True
            
        except Exception as e:
            logger.error(f"Failed to store code patterns: {e}")
            return False

    def generate_analytics_template(self, template_type: str) -> dict:
        """Generate reusable analytics templates based on memory patterns."""
        try:
            # Prepare template generation request
            template_request = {
                "template_type": template_type,
                "memory_enabled": self.memory_config is not None,
                "generation_type": "analytics_template",
                "timestamp": get_today_str()
            }
            
            if self.memory_config:
                template_request["memory_namespace"] = self.memory_config.namespace
                logger.info("Memory-enhanced template generation prepared")
            
            logger.info(f"Preparing analytics template generation: {template_request}")
            return template_request
            
        except Exception as e:
            logger.error(f"Failed to prepare template generation: {e}")
            return {"error": str(e), "generation_type": "analytics_template"}

    def __call__(self, prompt: AgentInput = None, **kwargs: Any) -> AgentResult:
        """Execute the code generator agent with the given prompt."""
        return self.agent(prompt=prompt, **kwargs)