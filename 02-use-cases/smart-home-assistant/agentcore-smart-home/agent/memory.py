import logging
from typing import Dict
from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore.memory.constants import StrategyType
from strands.hooks import AfterInvocationEvent, HookProvider, HookRegistry, MessageAddedEvent, AgentInitializedEvent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Helper function to get namespaces from memory strategies list
def get_namespaces(mem_client: MemoryClient, memory_id: str) -> Dict:
    """Get namespace mapping for memory strategies."""
    strategies = mem_client.get_memory_strategies(memory_id)
    return {i["type"]: i["namespaces"][0] for i in strategies}


class UserMemoryHooks(HookProvider):
    """Memory hooks for user"""
    
    def __init__(self, memory_id: str):
        self.memory_id = memory_id
        self.client = MemoryClient()
        self.namespaces = get_namespaces(self.client, self.memory_id)

    def retrieve_customer_context(self, event: MessageAddedEvent):
        """Retrieve customer context before processing support query"""
        messages = event.agent.messages
        if messages[-1]["role"] == "user" and "toolResult" not in messages[-1]["content"][0]:
            user_query = messages[-1]["content"][0]["text"]
            
            try:
                # Retrieve customer context from all namespaces
                all_context = []
                
                # Get actor_id from agent state
                actor_id = event.agent.state.get("actor_id")
                if not actor_id:
                    logger.warning("Missing actor_id in agent state")
                    return
                
                for context_type, namespace in self.namespaces.items():
                    memories = self.client.retrieve_memories(
                        memory_id=self.memory_id,
                        namespace=namespace.format(actorId=actor_id),
                        query=user_query,
                        top_k=3
                    )
                    
                    for memory in memories:
                        if isinstance(memory, dict):
                            content = memory.get('content', {})
                            if isinstance(content, dict):
                                text = content.get('text', '').strip()
                                if text:
                                    all_context.append(f"[{context_type.upper()}] {text}")
                
                # Inject customer context into the query
                if all_context:
                    context_text = "\n".join(all_context)
                    original_text = messages[-1]["content"][0]["text"]
                    messages[-1]["content"][0]["text"] = (
                        f"Customer Context:\n{context_text}\n\n{original_text}"
                    )
                    logger.info(f"Retrieved {len(all_context)} customer context items")
                return all_context
                    
            except Exception as e:
                logger.error(f"Failed to retrieve customer context: {e}")
    
    def save_support_interaction(self, event: AfterInvocationEvent):
        """Save support interaction after agent response"""
        try:
            messages = event.agent.messages
            if len(messages) >= 2 and messages[-1]["role"] == "assistant":
                # Get last customer query and agent response
                customer_query = None
                agent_response = None
                
                for msg in reversed(messages):
                    if msg["role"] == "assistant" and not agent_response:
                        agent_response = msg["content"][0]["text"]
                    elif msg["role"] == "user" and not customer_query and "toolResult" not in msg["content"][0]:
                        customer_query = msg["content"][0]["text"]
                        break
                
                if customer_query and agent_response:
                    # Get session info from agent state
                    actor_id = event.agent.state.get("actor_id")
                    session_id = event.agent.state.get("session_id")
                    
                    if not actor_id or not session_id:
                        logger.warning("Missing actor_id or session_id in agent state")
                        return
                    
                    # Save the support interaction
                    self.client.create_event(
                        memory_id=self.memory_id,
                        actor_id=actor_id,
                        session_id=session_id,
                        messages=[(customer_query, "USER"), (agent_response, "ASSISTANT")]
                    )
                    logger.info("Saved interaction to memory")
                    
        except Exception as e:
            logger.error(f"Failed to save support interaction: {e}")

    def register_hooks(self, registry: HookRegistry) -> None:
        """Register user memory hooks"""
        registry.add_callback(MessageAddedEvent, self.retrieve_customer_context)
        registry.add_callback(AfterInvocationEvent, self.save_support_interaction)
        logger.info("User memory hooks registered")

