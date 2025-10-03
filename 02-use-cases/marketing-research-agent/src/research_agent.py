from typing import  List, Any, Optional
from strands import Agent
from strands.agent import AgentResult
from strands.types.agent import AgentInput
from strands_tools.agent_core_memory import AgentCoreMemoryToolProvider

from .base_agent import BaseAgent
from .config import Configuration
from .prompts.research_prompt import RESEARCH_AGENT_PROMPT
from .core_tools.web_search_tools import web_search, web_crawl, web_extract
from .utils import get_today_str
from .memory.hooks import MarketingMemoryHookProvider

class ResearchAgent(BaseAgent):
    def __init__(self, config: Configuration, tools: List = None, memory_config: dict = None):
        """Initialize the ResearchAgent with the given configuration."""
        super().__init__(config)

        if tools is None:
            tools = []

        self.memory_config = memory_config
        self._init_agent(tools)


    def _init_agent(self, tools):
        """Initialize the agent with the model, system prompt, and tools."""

        self.model = self._init_model(self.config.research_model, self.config.research_thinking_enabled, self.config.research_thinking_tokens)

        self.system_prompt = RESEARCH_AGENT_PROMPT.format(
            date = get_today_str()
        )

        # Initialize memory tools if memory config is provided
        agent_tools = [web_search, web_extract, web_crawl] + tools
        
        if self.memory_config:
            # Add AgentCore Memory tools for competitive intelligence
            memory_tool_provider = AgentCoreMemoryToolProvider(
                memory_id=self.memory_config["memory_id"],
                actor_id=self.memory_config["actor_id"],
                session_id=self.memory_config["session_id"],
                namespace=f"marketing/{self.memory_config['actor_id']}/intelligence"
            )
            agent_tools.extend(memory_tool_provider.tools)

        # Prepare agent state with memory info if available
        agent_state = {}
        if self.memory_config:
            agent_state = {
                "actor_id": self.memory_config["actor_id"],
                "session_id": self.memory_config["session_id"]
            }

        # Set up memory hooks for automatic conversation capture
        hooks = []
        if self.memory_config:
            memory_hooks = MarketingMemoryHookProvider(
                memory_id=self.memory_config["memory_id"],
                client=self.memory_config["memory_client"],
                agent_type="research"
            )
            hooks = [memory_hooks]

        self.agent = Agent(
            model=self.model,
            system_prompt=self.system_prompt,
            tools=agent_tools,
            hooks=hooks,
            state=agent_state
        )



    def __call__(self, prompt: AgentInput = None, **kwargs: Any) -> AgentResult:
        # If memory is available, enhance the prompt with relevant context
        if self.memory_config and isinstance(prompt, str):
            enhanced_prompt = self._enhance_prompt_with_memory_context(prompt)
            return self.agent(prompt=enhanced_prompt, **kwargs)
        
        return self.agent(prompt=prompt, **kwargs)

    def _enhance_prompt_with_memory_context(self, original_prompt: str) -> str:
        """Enhance the research prompt with relevant memory context."""
        try:
            # Query memory for relevant past research
            memory_context = self._query_relevant_memory(original_prompt)
            
            if memory_context:
                enhanced_prompt = f"""
MEMORY CONTEXT FROM PREVIOUS RESEARCH:
{memory_context}

CURRENT RESEARCH REQUEST:
{original_prompt}

Please build upon the memory context above when conducting your research. Look for new developments, updates, or gaps in the previous research. Focus on competitive intelligence and market trends that have evolved since the last analysis.
"""
                return enhanced_prompt
            
        except Exception as e:
            print(f"Failed to enhance prompt with memory context: {e}")
        
        return original_prompt

    def _query_relevant_memory(self, prompt: str) -> Optional[str]:
        """Query memory for relevant competitive intelligence and market insights."""
        try:
            # Extract key terms for memory search
            search_terms = self._extract_marketing_keywords(prompt)
            
            memory_results = []
            for term in search_terms[:3]:  # Limit to top 3 terms
                try:
                    results = self.memory_config["memory_client"].query_memory(
                        memory_id=self.memory_config["memory_id"],
                        query=term,
                        actor_id=self.memory_config["actor_id"],
                        max_results=5
                    )
                    
                    if results and "results" in results:
                        for result in results["results"][:2]:  # Top 2 results per term
                            if "content" in result:
                                memory_results.append(f"- {result['content']}")
                                
                except Exception as e:
                    print(f"Memory query failed for term '{term}': {e}")
                    continue
            
            if memory_results:
                return "\n".join(memory_results[:5])  # Limit total results
                
        except Exception as e:
            print(f"Failed to query memory: {e}")
        
        return None

    def _extract_marketing_keywords(self, prompt: str) -> List[str]:
        """Extract marketing-relevant keywords for memory search."""
        # Simple keyword extraction focusing on marketing terms
        marketing_keywords = [
            "competitor", "competition", "market", "industry", "pricing", 
            "strategy", "customer", "segment", "trend", "analysis",
            "intelligence", "positioning", "campaign", "brand", "product"
        ]
        
        prompt_lower = prompt.lower()
        found_keywords = []
        
        # Look for marketing keywords in the prompt
        for keyword in marketing_keywords:
            if keyword in prompt_lower:
                found_keywords.append(keyword)
        
        # Also extract potential company/product names (capitalized words)
        words = prompt.split()
        for word in words:
            if word[0].isupper() and len(word) > 3 and word.isalpha():
                found_keywords.append(word)
        
        # If no specific keywords found, use the first few meaningful words
        if not found_keywords:
            words = [w for w in words if len(w) > 3 and w.isalpha()]
            found_keywords = words[:3]
        
        return found_keywords[:5]  # Return top 5 keywords
