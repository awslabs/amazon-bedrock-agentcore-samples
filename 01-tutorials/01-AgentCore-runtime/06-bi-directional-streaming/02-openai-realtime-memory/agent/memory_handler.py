from strands.experimental.bidi.agent import BidiAgent
from strands.experimental.bidi.models.openai_realtime import BidiOpenAIRealtimeModel
from strands.experimental.hooks.events import BidiMessageAddedEvent

from bedrock_agentcore.memory import MemoryClient


import logging



logger = logging.getLogger(__name__)



class MemoryHandler:
    def __init__(self, memory_client, memory_id, user_id, session_id):
        self.memory_client = memory_client
        self.memory_id = memory_id
        self.actor_id = user_id
        self.session_id = session_id


    #Keep it sync as it is on initialization, outside the async loop.
    def get_past_conversation(self):
        messages = self.memory_client.get_last_k_turns(
            memory_id = self.memory_id,
            actor_id = self.actor_id,
            session_id = self.session_id,
            k = 50
        )
        return messages

    async def log_message(self, event: BidiMessageAddedEvent):
    
        actor_id = self.actor_id
        memory_id = self.memory_id
        session_id = self.session_id
        logger.info(f"State values - memory_id: {memory_id}, actor_id: {actor_id}, session_id: {session_id}")

        message_role = event.message['role']

        # Handle gracefully tool use where there is no text
        try:
            message_content = event.message['content'][0]['text']
        except (KeyError, IndexError, TypeError):
            return  # Skip messages without text content

        try:
            logger.info(f"Saving {message_role} message to memory: {message_content[:30]}...")
            self.memory_client.create_event(
                memory_id=memory_id,
                actor_id=actor_id,
                session_id=session_id,
                messages=[(message_content, message_role)]
            )
            logger.info(f"Event details - actor_id {actor_id}, session_id: {session_id}, memory_id: {memory_id}")
        except Exception as e:
            logger.error(f"Memory save error: {e}", exc_info=True)
    




