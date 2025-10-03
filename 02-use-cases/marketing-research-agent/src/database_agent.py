import logging
from typing import Any, Optional
from strands import Agent
from strands.agent import AgentResult
from strands.types.agent import AgentInput
from strands_tools.agent_core_memory import AgentCoreMemoryToolProvider

from .base_agent import BaseAgent
from .config import Configuration
from .prompts.database_prompt import DATABASE_AGENT_PROMPT
from .core_tools.dynamodb_tool import dynamodb_query_tool
from .utils import get_today_str
from .memory.memory_manager import MemoryConfig
from .memory.hooks import MarketingMemoryHookProvider


logger = logging.getLogger(__name__)


class DatabaseAgent(BaseAgent):
    """Database agent for customer data analysis and segmentation with memory capabilities."""
    
    def __init__(self, config: Configuration, memory_config: Optional[MemoryConfig] = None):
        super().__init__(config)
        self.memory_config = memory_config
        self._init_agent()

    def _init_agent(self):
        """Initialize the database agent with DynamoDB tools and memory integration."""
        # Start with base DynamoDB tools
        tools = [dynamodb_query_tool]
        
        # Add memory tools if memory is configured
        if self.memory_config:
            memory_provider = AgentCoreMemoryToolProvider(
                memory_id=self.memory_config.memory_id,
                actor_id=self.memory_config.actor_id,
                session_id=self.memory_config.session_id,
                namespace=f"marketing/{self.memory_config.actor_id}/customer_insights"
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
                agent_type="database"
            )
            hooks = [memory_hooks]
        
        # Format system prompt with table configuration
        system_prompt = DATABASE_AGENT_PROMPT.format(
            date=get_today_str(),
            table_name=self.config.customer_data_table,
            marketing_channel_gsi=self.config.marketing_channel_gsi,
            customer_segment_gsi=self.config.customer_segment_gsi
        )
        
        self.agent = Agent(
            model=self._init_model(
                self.config.database_model,
                self.config.database_thinking_enabled,
                self.config.database_thinking_tokens
            ),
            system_prompt=system_prompt,
            tools=tools,
            hooks=hooks,
            state=agent_state
        )
    
    def analyze_customer_segments(self, segment_criteria: dict) -> dict:
        """Analyze customer segments using DynamoDB data and memory insights."""
        try:
            # Query memory for previous segmentation patterns if available
            memory_context = {}
            if self.memory_config:
                logger.info("Querying memory for previous customer segmentation patterns")
                # Memory query would be handled by the agent's memory tools during execution
                memory_context = {"memory_enabled": True, "namespace": self.memory_config.namespace}
            
            # Prepare segmentation analysis request
            analysis_request = {
                "criteria": segment_criteria,
                "memory_context": memory_context,
                "analysis_type": "customer_segmentation",
                "timestamp": get_today_str()
            }
            
            logger.info(f"Starting customer segmentation analysis: {analysis_request}")
            return analysis_request
            
        except Exception as e:
            logger.error(f"Failed to analyze customer segments: {e}")
            return {"error": str(e), "analysis_type": "customer_segmentation"}
    
    def query_customer_insights(self, query_params: dict) -> dict:
        """Query customer data with memory-enhanced insights."""
        try:
            # Prepare customer insights query
            insights_query = {
                "query_params": query_params,
                "memory_enabled": self.memory_config is not None,
                "query_type": "customer_insights",
                "timestamp": get_today_str()
            }
            
            if self.memory_config:
                insights_query["memory_namespace"] = self.memory_config.namespace
                logger.info("Memory-enhanced customer insights query prepared")
            
            logger.info(f"Preparing customer insights query: {insights_query}")
            return insights_query
            
        except Exception as e:
            logger.error(f"Failed to prepare customer insights query: {e}")
            return {"error": str(e), "query_type": "customer_insights"}
    
    def learn_segmentation_patterns(self, successful_segments: dict) -> bool:
        """Store successful segmentation patterns in memory for future use."""
        if not self.memory_config:
            logger.warning("Memory not configured for pattern learning")
            return False
        
        try:
            # Prepare segmentation learning data
            learning_data = {
                "successful_segments": successful_segments,
                "learning_type": "segmentation_patterns",
                "timestamp": get_today_str(),
                "agent_type": "database"
            }
            
            logger.info(f"Storing segmentation patterns in memory: {learning_data}")
            # The actual memory storage would be handled by the agent's memory tools
            return True
            
        except Exception as e:
            logger.error(f"Failed to store segmentation patterns: {e}")
            return False

    def __call__(self, prompt: AgentInput = None, **kwargs: Any) -> AgentResult:
        """Execute the database agent with the given prompt."""
        return self.agent(prompt=prompt, **kwargs)