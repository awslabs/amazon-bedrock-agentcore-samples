from bedrock_agentcore.memory import MemoryClient
from strands.hooks.events import AgentInitializedEvent, MessageAddedEvent
from strands.hooks.registry import HookProvider, HookRegistry
import copy


class MemoryHook(HookProvider):
    def __init__(
        self,
        memory_client: MemoryClient,
        memory_id: str,
        actor_id: str,
        session_id: str,
    ):
        self.memory_client = memory_client
        self.memory_id = memory_id
        self.actor_id = actor_id
        self.session_id = session_id

    def on_agent_initialized(self, event: AgentInitializedEvent):
        """Load recent conversation history when agent starts"""
        try:
            # Load the last 5 conversation turns from memory
            recent_turns = self.memory_client.get_last_k_turns(
                memory_id=self.memory_id,
                actor_id=self.actor_id,
                session_id=self.session_id,
                k=5,
            )

            if recent_turns:
                # Format conversation history for context
                context_messages = []
                for turn in recent_turns:
                    for message in turn:
                        role = "assistant" if message["role"] == "ASSISTANT" else "user"
                        content = message["content"]["text"]
                        context_messages.append(
                            {"role": role, "content": [{"text": content}]}
                        )

                # context = "\n".join(context_messages)
                # Add context to agent's system prompt.
                event.agent.system_prompt += """
                Do not respond with user preferences or user facts. 
                Strictly use user preferences and user facts to know more about the user.
                Also be aware that this information can be outdated.
                """
                event.agent.messages = context_messages

        except Exception as e:
            print(f"Memory load error: {e}")

    def _add_context_user_query(
        self, namespace: str, query: str, init_content: str, event: MessageAddedEvent
    ):
        content = None
        memories = self.memory_client.retrieve_memories(
            memory_id=self.memory_id, namespace=namespace, query=query, top_k=3
        )

        for memory in memories:
            if not content:
                content = "\n\n" + init_content + "\n\n"

            content += memory["content"]["text"]

            if content:
                event.agent.messages[-1]["content"][0]["text"] += content + "\n\n"

    def on_message_added(self, event: MessageAddedEvent):
        """Store messages in memory"""
        messages = copy.deepcopy(event.agent.messages)
        try:
            if messages[-1]["role"] == "user" or messages[-1]["role"] == "assistant":
                if "text" not in messages[-1]["content"][0]:
                    return

                if messages[-1]["role"] == "user":
                    self._add_context_user_query(
                        namespace=f"support/user/{self.actor_id}/preferences",
                        query=messages[-1]["content"][0]["text"],
                        init_content="These are user preferences:",
                        event=event,
                    )

                    self._add_context_user_query(
                        namespace=f"support/user/{self.actor_id}/facts",
                        query=messages[-1]["content"][0]["text"],
                        init_content="These are user facts:",
                        event=event,
                    )
                self.memory_client.save_conversation(
                    memory_id=self.memory_id,
                    actor_id=self.actor_id,
                    session_id=self.session_id,
                    messages=[
                        (messages[-1]["content"][0]["text"], messages[-1]["role"])
                    ],
                )

        except Exception as e:
            raise RuntimeError(f"Memory save error: {e}")

    def register_hooks(self, registry: HookRegistry):
        registry.add_callback(MessageAddedEvent, self.on_message_added)
        registry.add_callback(AgentInitializedEvent, self.on_agent_initialized)
