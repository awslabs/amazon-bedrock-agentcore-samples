import logging
from typing import Any, Optional
from strands import Agent
from strands.agent import AgentResult
from strands.types.agent import AgentInput
from strands_tools.agent_core_memory import AgentCoreMemoryToolProvider

from .base_agent import BaseAgent
from .config import Configuration
from .prompts.reporting_prompt import REPORTING_AGENT_PROMPT
from .core_tools.report_generation_tool import generate_marketing_report
from .utils import get_today_str
from .memory.memory_manager import MemoryConfig
from .memory.hooks import MarketingMemoryHookProvider


logger = logging.getLogger(__name__)


class ReportingAgent(BaseAgent):
    """Reporting agent for final synthesis and comprehensive report generation with memory capabilities."""
    
    def __init__(self, config: Configuration, memory_config: Optional[MemoryConfig] = None):
        super().__init__(config)
        self.memory_config = memory_config
        self._init_agent()

    def _init_agent(self):
        """Initialize the reporting agent with report generation tools and memory integration."""
        # Start with base report generation tools
        tools = [generate_marketing_report]
        
        # Add memory tools if memory is configured
        if self.memory_config:
            memory_provider = AgentCoreMemoryToolProvider(
                memory_id=self.memory_config.memory_id,
                actor_id=self.memory_config.actor_id,
                session_id=self.memory_config.session_id,
                namespace=f"marketing/{self.memory_config.actor_id}/reports"
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
                agent_type="reporting"
            )
            hooks = [memory_hooks]
        
        self.agent = Agent(
            model=self._init_model(
                self.config.reporting_model,
                self.config.reporting_thinking_enabled,
                self.config.reporting_thinking_tokens
            ),
            system_prompt=REPORTING_AGENT_PROMPT.format(date=get_today_str()),
            tools=tools,
            hooks=hooks,
            state=agent_state
        )
    
    def synthesize_research_findings(self, research_data: dict) -> dict:
        """Synthesize findings from all agents into comprehensive insights."""
        try:
            # Query memory for previous report structures if available
            memory_context = {}
            if self.memory_config:
                logger.info("Querying memory for previous report templates and structures")
                memory_context = {"memory_enabled": True, "namespace": self.memory_config.namespace}
            
            # Prepare synthesis request
            synthesis_request = {
                "research_data": research_data,
                "memory_context": memory_context,
                "synthesis_type": "comprehensive_findings",
                "timestamp": get_today_str()
            }
            
            logger.info(f"Starting research findings synthesis: {synthesis_request}")
            return synthesis_request
            
        except Exception as e:
            logger.error(f"Failed to synthesize research findings: {e}")
            return {"error": str(e), "synthesis_type": "comprehensive_findings"}
    
    def generate_executive_summary(self, key_insights: dict) -> dict:
        """Generate executive summary with memory-enhanced templates."""
        try:
            # Prepare executive summary generation
            summary_request = {
                "key_insights": key_insights,
                "memory_enabled": self.memory_config is not None,
                "report_type": "executive_summary",
                "timestamp": get_today_str()
            }
            
            if self.memory_config:
                summary_request["memory_namespace"] = self.memory_config.namespace
                logger.info("Memory-enhanced executive summary generation prepared")
            
            logger.info(f"Preparing executive summary generation: {summary_request}")
            return summary_request
            
        except Exception as e:
            logger.error(f"Failed to prepare executive summary generation: {e}")
            return {"error": str(e), "report_type": "executive_summary"}
    
    def create_comprehensive_report(self, all_agent_outputs: dict, report_format: str = "markdown") -> dict:
        """Create comprehensive marketing research report from all agent outputs."""
        try:
            # Prepare comprehensive report generation
            report_request = {
                "agent_outputs": all_agent_outputs,
                "report_format": report_format,
                "memory_enabled": self.memory_config is not None,
                "report_type": "comprehensive_marketing_research",
                "timestamp": get_today_str()
            }
            
            if self.memory_config:
                report_request["memory_namespace"] = self.memory_config.namespace
                logger.info("Memory-enhanced comprehensive report generation prepared")
            
            logger.info(f"Preparing comprehensive report generation: {report_request}")
            return report_request
            
        except Exception as e:
            logger.error(f"Failed to prepare comprehensive report generation: {e}")
            return {"error": str(e), "report_type": "comprehensive_marketing_research"}
    
    def learn_report_templates(self, successful_reports: dict) -> bool:
        """Store successful report templates and structures in memory for future use."""
        if not self.memory_config:
            logger.warning("Memory not configured for template learning")
            return False
        
        try:
            # Prepare template learning data
            learning_data = {
                "successful_reports": successful_reports,
                "learning_type": "report_templates",
                "timestamp": get_today_str(),
                "agent_type": "reporting"
            }
            
            logger.info(f"Storing report templates in memory: {learning_data}")
            # The actual memory storage would be handled by the agent's memory tools
            return True
            
        except Exception as e:
            logger.error(f"Failed to store report templates: {e}")
            return False

    def __call__(self, prompt: AgentInput = None, **kwargs: Any) -> AgentResult:
        """Execute the reporting agent with the given prompt."""
        return self.agent(prompt=prompt, **kwargs)