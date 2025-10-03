import logging
from typing import Any, Optional
from strands import Agent
from strands.agent import AgentResult
from strands.types.agent import AgentInput
from strands_tools.agent_core_memory import AgentCoreMemoryToolProvider

from .base_agent import BaseAgent
from .config import Configuration
from .prompts.supervisor_prompt import SUPERVISOR_AGENT_PROMPT
from .agent_tools.web_research_agent_tool import web_research_agent
from .agent_tools.database_query_agent_tool import database_query_agent
from .agent_tools.code_analysis_agent_tool import code_analysis_agent
from .agent_tools.marketing_report_agent_tool import marketing_report_agent
from .utils import get_today_str
from .memory.memory_manager import MemoryConfig
from .memory.hooks import MarketingMemoryHookProvider


logger = logging.getLogger(__name__)

class SupervisorAgent(BaseAgent):
    def __init__(self, config: Configuration, memory_config: Optional[MemoryConfig] = None):
        super().__init__(config)
        self.memory_config = memory_config
        self._init_agent()

    def _init_agent(self):
        # Start with base tools
        tools = [web_research_agent, database_query_agent, code_analysis_agent, marketing_report_agent]
         
        # Add memory tools if memory is configured
        memory_provider = None
        if self.memory_config:
            try:
                memory_provider = AgentCoreMemoryToolProvider(
                    memory_id=self.memory_config.memory_id,
                    actor_id=self.memory_config.actor_id,
                    session_id=self.memory_config.session_id,
                    namespace=self.memory_config.namespace,
                    region=self.config.aws_region
                )
                tools.extend(memory_provider.tools)
                logger.info(f"Added {len(memory_provider.tools)} memory tools to supervisor agent")
                
                # Log available memory tools
                for tool in memory_provider.tools:
                    tool_name = getattr(tool, 'name', getattr(tool, '__name__', 'Unknown Tool'))
                    logger.info(f"  - Memory tool: {tool_name}")
                    
            except Exception as e:
                logger.error(f"Failed to initialize memory tools: {e}")
                logger.warning("Supervisor agent will run without memory tools")
        
        # Prepare agent state with memory info if available
        agent_state = {}
        if self.memory_config:
            agent_state = {
                "actor_id": self.memory_config.actor_id,
                "session_id": self.memory_config.session_id,
                "memory_id": self.memory_config.memory_id,
                "namespace": self.memory_config.namespace
            }
        
        # Set up memory hooks for automatic conversation capture
        hooks = []
        if self.memory_config:
            try:
                memory_hooks = MarketingMemoryHookProvider(
                    memory_id=self.memory_config.memory_id,
                    client=self.memory_config.memory_client,
                    agent_type="supervisor"
                )
                hooks = [memory_hooks]
                logger.info("Memory hooks configured for supervisor agent")
            except Exception as e:
                logger.error(f"Failed to initialize memory hooks: {e}")
                logger.warning("Supervisor agent will run without memory hooks")
        
        self.agent = Agent(
            model=self._init_model(self.config.supervisor_model,
                                   self.config.supervisor_thinking_enabled,
                                   self.config.supervisor_thinking_tokens),
            system_prompt=SUPERVISOR_AGENT_PROMPT.format(date=get_today_str()),
            tools=tools,
            hooks=hooks,
            state=agent_state
        )
        
        logger.info(f"Supervisor agent initialized with {len(tools)} tools and {len(hooks)} hooks")
    
    def query_cross_agent_memory(self, query: str, agent_types: list = None) -> dict:
        """Query memory across multiple agent namespaces for cross-agent insights."""
        if not self.memory_config:
            return {"error": "Memory not configured"}
        
        # Default to querying all agent types if none specified
        if agent_types is None:
            agent_types = ["supervisor", "research", "database", "code_generator", "reporting"]
        
        results = {}
        
        for agent_type in agent_types:
            try:
                # Generate namespace for the agent type
                namespace_map = {
                    "supervisor": "marketing/{actorId}/coordination",
                    "research": "marketing/{actorId}/intelligence", 
                    "database": "marketing/{actorId}/customer_insights",
                    "code_generator": "marketing/{actorId}/analytics",
                    "reporting": "marketing/{actorId}/reports"
                }
                
                # For cross-agent queries, we'll use a generic actor ID pattern
                # In a real implementation, you'd want to track actual actor IDs
                namespace_template = namespace_map.get(agent_type, "marketing/{actorId}/general")
                
                # Query memory for this agent type
                # Note: This is a simplified implementation - in practice you'd need
                # to handle multiple actor IDs and more sophisticated querying
                results[agent_type] = {
                    "namespace": namespace_template,
                    "query": query,
                    "status": "ready_for_query"
                }
                
            except Exception as e:
                logger.error(f"Failed to query {agent_type} memory: {e}")
                results[agent_type] = {"error": str(e)}
        
        return results
    
    def coordinate_memory_sharing(self, insights: dict, target_agents: list = None) -> bool:
        """Coordinate sharing of insights across agent memory namespaces."""
        if not self.memory_config:
            logger.warning("Memory not configured for cross-agent sharing")
            return False
        
        try:
            # Store coordination insights in supervisor memory
            # This allows other agents to query coordination decisions
            coordination_data = {
                "timestamp": get_today_str(),
                "shared_insights": insights,
                "target_agents": target_agents or [],
                "coordination_type": "cross_agent_sharing"
            }
            
            # In a full implementation, you would store this using memory tools
            # For now, we'll log the coordination activity
            logger.info(f"Coordinating memory sharing: {coordination_data}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to coordinate memory sharing: {e}")
            return False
    
    def plan_memory_enhanced_research(self, research_topic: str) -> dict:
        """Plan research approach using memory-based insights and past methodologies."""
        if not self.memory_config:
            return {"approach": "standard", "memory_insights": None}
        
        try:
            # Query memory for relevant past research
            memory_context = self.query_cross_agent_memory(
                query=f"research methodology for {research_topic}",
                agent_types=["supervisor", "research"]
            )
            
            # Plan research approach based on memory insights
            research_plan = {
                "topic": research_topic,
                "memory_context": memory_context,
                "approach": "memory_enhanced",
                "recommended_agents": ["research"],  # Start with research agent
                "coordination_strategy": "incremental_building",
                "memory_sharing_plan": {
                    "store_insights": True,
                    "cross_reference": True,
                    "build_on_previous": True
                }
            }
            
            return research_plan
            
        except Exception as e:
            logger.error(f"Failed to plan memory-enhanced research: {e}")
            return {"approach": "fallback", "error": str(e)}
    
    def coordinate_database_analysis(self, analysis_request: dict) -> dict:
        """Coordinate database analysis with memory-enhanced customer insights."""
        if not self.memory_config:
            logger.warning("Memory not configured for database analysis coordination")
            return {"approach": "standard", "memory_enabled": False}
        
        try:
            # Query memory for relevant customer analysis patterns
            memory_context = self.query_cross_agent_memory(
                query=f"customer analysis for {analysis_request.get('topic', 'general')}",
                agent_types=["supervisor", "database"]
            )
            
            # Coordinate database analysis approach
            analysis_plan = {
                "request": analysis_request,
                "memory_context": memory_context,
                "approach": "memory_enhanced_database",
                "recommended_tools": ["database_agent"],
                "coordination_strategy": "customer_insight_building",
                "memory_sharing_plan": {
                    "store_segmentation_patterns": True,
                    "learn_query_optimizations": True,
                    "build_customer_intelligence": True
                }
            }
            
            logger.info(f"Coordinated memory-enhanced database analysis: {analysis_plan}")
            return analysis_plan
            
        except Exception as e:
            logger.error(f"Failed to coordinate database analysis: {e}")
            return {"approach": "fallback", "error": str(e), "memory_enabled": False}
    
    def coordinate_code_generation(self, code_request: dict) -> dict:
        """Coordinate code generation with memory-enhanced analytics patterns."""
        if not self.memory_config:
            logger.warning("Memory not configured for code generation coordination")
            return {"approach": "standard", "memory_enabled": False}
        
        try:
            # Query memory for relevant code patterns and analytics approaches
            memory_context = self.query_cross_agent_memory(
                query=f"analytics code for {code_request.get('analysis_type', 'general')}",
                agent_types=["supervisor", "code_generator"]
            )
            
            # Coordinate code generation approach
            generation_plan = {
                "request": code_request,
                "memory_context": memory_context,
                "approach": "memory_enhanced_code_generation",
                "recommended_tools": ["code_generator_agent"],
                "coordination_strategy": "analytics_pattern_building",
                "memory_sharing_plan": {
                    "store_successful_patterns": True,
                    "learn_optimization_strategies": True,
                    "build_template_library": True
                }
            }
            
            logger.info(f"Coordinated memory-enhanced code generation: {generation_plan}")
            return generation_plan
            
        except Exception as e:
            logger.error(f"Failed to coordinate code generation: {e}")
            return {"approach": "fallback", "error": str(e), "memory_enabled": False}

    def __call__(self, prompt: AgentInput = None, **kwargs: Any) -> AgentResult:
        return self.agent(prompt=prompt, **kwargs)
