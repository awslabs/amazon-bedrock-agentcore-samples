# import the memory client 
import logging
import time
from typing import List, Dict, Any
from bedrock_agentcore.memory import MemoryClient
# This will help set up for strategies that can then be used 
# across the code - user preferences, semantic memory or even
# summarizations across the sessions along with custom strategies
# for this monitoring agent
from bedrock_agentcore.memory.constants import StrategyType
from strands.hooks import AgentInitializedEvent, HookProvider, HookRegistry, MessageAddedEvent, AfterInvocationEvent

# Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# Helper function to get namespaces from memory strategies list
def get_namespaces(mem_client: MemoryClient, memory_id: str) -> Dict:
    """Get namespace mapping for memory strategies."""
    strategies = mem_client.get_memory_strategies(memory_id)
    return {i["type"]: i["namespaces"][0] for i in strategies}

# Create monitoring memory hooks
class MonitoringMemoryHooks(HookProvider):
    """Memory hooks for monitoring agent"""
    
    def __init__(self, memory_id: str, client: MemoryClient, actor_id: str, session_id: str):
        self.memory_id = memory_id
        self.client = client
        self.actor_id = actor_id
        self.session_id = session_id
        self.namespaces = get_namespaces(self.client, self.memory_id)

    def retrieve_monitoring_context(self, event: MessageAddedEvent):
        """Retrieve monitoring context before processing queries"""
        messages = event.agent.messages
        if messages[-1]["role"] == "user" and "toolResult" not in messages[-1]["content"][0]:
            user_query = messages[-1]["content"][0]["text"]
            
            try:
                # Retrieve monitoring context from all namespaces
                all_context = []
                
                for context_type, namespace in self.namespaces.items():
                    # to retrieve the memory events. This API helps retrieve
                    # the information using semantic search.
                    # this takes the memory id, the namespace where the data is stored, and 
                    # the search query, and the top number of results to return or top k chunks
                    memories = self.client.retrieve_memories(
                        memory_id=self.memory_id,
                        namespace=namespace.format(actorId=self.actor_id),
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
                
                # Inject monitoring context into the query
                if all_context:
                    context_text = "\n".join(all_context)
                    original_text = messages[-1]["content"][0]["text"]
                    messages[-1]["content"][0]["text"] = (
                        f"Monitoring Context:\n{context_text}\n\n{original_text}"
                    )
                    logger.info(f"Retrieved {len(all_context)} monitoring context items")
                    
            except Exception as e:
                logger.error(f"Failed to retrieve monitoring context: {e}")
    
    def save_monitoring_interaction(self, event: AfterInvocationEvent):
        """Save monitoring interaction after agent response"""
        try:
            messages = event.agent.messages
            if len(messages) >= 2 and messages[-1]["role"] == "assistant":
                # Get last user query and agent response
                user_query = None
                agent_response = None
                
                for msg in reversed(messages):
                    if msg["role"] == "assistant" and not agent_response:
                        agent_response = msg["content"][0]["text"]
                    elif msg["role"] == "user" and not user_query and "toolResult" not in msg["content"][0]:
                        user_query = msg["content"][0]["text"]
                        break
                
                if user_query and agent_response:
                    # Save both user query and assistant response in one call
                    self.client.create_event(
                        memory_id=self.memory_id,
                        actor_id=self.actor_id,
                        session_id=self.session_id,
                        messages=[
                            (user_query, "USER"),
                            (agent_response, "ASSISTANT")
                        ]
                    )
                    logger.info("Saved monitoring interaction to memory")
                    
        except Exception as e:
            logger.error(f"Failed to save monitoring interaction: {e}")

    def on_agent_initialized(self, event: AgentInitializedEvent):
        """Load recent conversation history when agent starts"""
        try:
            # Load the last 5 conversation turns from memory
            recent_turns = self.client.get_last_k_turns(
                memory_id=self.memory_id,
                actor_id=self.actor_id,
                session_id=self.session_id,
                k=5
            )
            
            if recent_turns:
                # Format conversation history for context
                context_messages = []
                for turn in recent_turns:
                    for message in turn:
                        role = message['role']
                        content = message['content']['text']
                        context_messages.append(f"{role}: {content}")
                
                context = "\n".join(context_messages)
                # Add context to agent's system prompt.
                event.agent.system_prompt += f"\n\nRecent conversation:\n{context}"
                logger.info(f"✅ Loaded {len(recent_turns)} conversation turns")
                
        except Exception as e:
            logger.error(f"Memory load error: {e}")
            
    def register_hooks(self, registry: HookRegistry) -> None:
        """Register monitoring memory hooks"""
        registry.add_callback(MessageAddedEvent, self.retrieve_monitoring_context)
        registry.add_callback(AfterInvocationEvent, self.save_monitoring_interaction)
        registry.add_callback(AgentInitializedEvent, self.on_agent_initialized)
        logger.info("Monitoring memory hooks registered")