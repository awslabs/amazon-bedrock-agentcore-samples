import logging
from typing import Optional
from strands.hooks import AfterInvocationEvent, HookProvider, HookRegistry
from bedrock_agentcore.memory import MemoryClient

logger = logging.getLogger(__name__)


class MarketingMemoryHookProvider(HookProvider):
    """Automatic memory capture for marketing research agent conversations."""
    
    def __init__(self, memory_id: str, client: MemoryClient, agent_type: str):
        """
        Initialize the memory hook provider.
        
        Args:
            memory_id: The AgentCore Memory resource ID
            client: The MemoryClient instance
            agent_type: Type of agent (supervisor, research, database, etc.)
        """
        self.memory_id = memory_id
        self.client = client
        self.agent_type = agent_type
    
    def save_memories(self, event: AfterInvocationEvent):
        """Save conversation after agent response."""
        try:
            messages = event.agent.messages
            if len(messages) >= 2:
                # Get last user and assistant messages
                user_msg = None
                assistant_msg = None
                
                for msg in reversed(messages):
                    if msg["role"] == "assistant" and not assistant_msg:
                        if isinstance(msg["content"], list) and len(msg["content"]) > 0:
                            assistant_msg = msg["content"][0].get("text", "")
                        else:
                            assistant_msg = str(msg["content"])
                    elif msg["role"] == "user" and not user_msg:
                        if isinstance(msg["content"], list) and len(msg["content"]) > 0:
                            content = msg["content"][0]
                            if "toolResult" not in content:
                                user_msg = content.get("text", "")
                        else:
                            user_msg = str(msg["content"])
                        if user_msg:
                            break
                
                if user_msg and assistant_msg:
                    # Get session info from agent state
                    actor_id = getattr(event.agent.state, "actor_id", None) if hasattr(event.agent.state, "actor_id") else event.agent.state.get("actor_id", None)
                    session_id = getattr(event.agent.state, "session_id", None) if hasattr(event.agent.state, "session_id") else event.agent.state.get("session_id", None)
                    memory_id = getattr(event.agent.state, "memory_id", self.memory_id) if hasattr(event.agent.state, "memory_id") else event.agent.state.get("memory_id", self.memory_id)
                    
                    if not actor_id or not session_id:
                        logger.warning(f"Missing actor_id or session_id in {self.agent_type} agent state")
                        logger.debug(f"Agent state: {event.agent.state}")
                        return
                    
                    # Save conversation to AgentCore Memory
                    self.client.create_event(
                        memory_id=memory_id,
                        actor_id=actor_id,
                        session_id=session_id,
                        messages=[(user_msg, "USER"), (assistant_msg, "ASSISTANT")]
                    )
                    logger.info(f"✓ Saved {self.agent_type} agent conversation to memory (Actor: {actor_id[:12]}...)")
                else:
                    logger.debug(f"No valid user/assistant message pair found for {self.agent_type} agent")
                    
        except Exception as e:
            logger.error(f"❌ Failed to save {self.agent_type} agent memories: {e}")
            import traceback
            logger.debug(traceback.format_exc())
    
    def register_hooks(self, registry: HookRegistry) -> None:
        """Register memory hooks with the agent."""
        registry.add_callback(AfterInvocationEvent, self.save_memories)
        logger.info(f"Memory hooks registered for {self.agent_type} agent")