#!/usr/bin/env python3
"""
Voice Agent Server - OpenAI Realtime
"""
import sys
import logging
import uvicorn
import os
import asyncio
import requests
import json
from datetime import datetime

from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore import BedrockAgentCoreApp

from strands.experimental.bidi.agent import BidiAgent
from strands.experimental.bidi.models.openai_realtime import BidiOpenAIRealtimeModel
from strands.experimental.bidi.models.nova_sonic import BidiNovaSonicModel
from strands.experimental.hooks.events import BidiMessageAddedEvent
from strands_tools import calculator

from memory_handler import MemoryHandler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)  # Explicitly use stdout
    ]
)
logger = logging.getLogger(__name__)

# Log to confirm logging is working
logger.info("=" * 80)
logger.info("SERVER STARTING - Logging initialized")
logger.info(f"OPENAI_API_KEY set: {'Yes' if os.getenv('OPENAI_API_KEY') else 'No'}")
logger.info(f"AWS_REGION: {os.getenv('AWS_DEFAULT_REGION', 'not set')}")
logger.info("=" * 80)

region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')

agentcore_memory_client = MemoryClient(region_name = region)


#The actor is used for memory segregation. In this example we will use a test actor placeholder and will not distinguish between users.
user_id = 'test-actor'


#Load environment variables.
memory_id = os.getenv('MEMORY_ID')
if memory_id:
    logger.info(f"Memory ID found: {memory_id}")
else:
    logger.warning("No MEMORY_ID found - memory will not be used")
openai_key = os.getenv("OPENAI_API_KEY")
if openai_key:
    logger.info(f"OpenAI key found.")
else:
    logger.error("No OpenAI key has been set.")


app = BedrockAgentCoreApp()

            


@app.websocket
async def websocket_endpoint(websocket,context):
    print("=" * 80, flush=True)
    print("WEBSOCKET CONNECTION ATTEMPT", flush=True)
    print(f"Client: {websocket.client}", flush=True)
    print(f"Headers: {dict(websocket.headers)}", flush=True)
    print(f"Query params: {dict(websocket.query_params)}", flush=True)
    print("=" * 80, flush=True)
    
    logger.info("=" * 80)
    logger.info("WebSocket connection attempt")
    logger.info(f"Client: {websocket.client}")
    logger.info(f"Query params: {dict(websocket.query_params)}")
    logger.info(f"Headers: {dict(websocket.headers)}")

    # Wrapper to chunk large audio messages
    async def chunked_send(msg: dict) -> None:
        """Send message, chunking audio if needed to stay under 16KB limit."""
        msg_json = json.dumps(msg)
        msg_size = len(msg_json.encode('utf-8'))
        
        # If message is small enough, send as-is
        if msg_size <= 31000:  # 31KB threshold for safety
            await websocket.send_json(msg)
            return
        
        # Only chunk bidi_audio_stream messages
        if msg.get("type") != "bidi_audio_stream" or "audio" not in msg:
            logger.warning(f"Large message ({msg_size} bytes) cannot be chunked, sending anyway")
            await websocket.send_json(msg)
            return
        
        # Calculate chunk size for audio content
        audio_content = msg["audio"]
        template_msg = msg.copy()
        template_msg["audio"] = ""
        overhead = len(json.dumps(template_msg).encode('utf-8'))
        max_audio_size = 31000 - overhead - 100
        
        # For PCM 16-bit audio:
        # - Base64: 4 chars = 3 bytes
        # - PCM samples: 2 bytes per sample
        # - LCM(3, 2) = 6 bytes = 8 base64 chars
        # So we need to align to 8-char boundaries to preserve sample alignment
        max_audio_size = (max_audio_size // 8) * 8
        
        # Split and send chunks
        chunk_count = (len(audio_content) + max_audio_size - 1) // max_audio_size
        logger.info(f"Splitting audio ({msg_size} bytes) into {chunk_count} chunks")
        
        for i in range(0, len(audio_content), max_audio_size):
            chunk_audio = audio_content[i:i + max_audio_size]
            chunk_msg = msg.copy()
            chunk_msg["audio"] = chunk_audio
            await websocket.send_json(chunk_msg)
    

    # Handle the websocket connection
    try:
        await websocket.accept()
    except Exception as e:
        logger.error(f"❌ Failed to accept WebSocket: {e}", exc_info=True)
        raise

    # Get voice from headers (set via X-Amzn-Bedrock-AgentCore-Runtime-Custom-VoiceId),
    # fall back to voice_id query param, then default to alloy
    voice_id = (
        websocket.headers.get("x-amzn-bedrock-agentcore-runtime-custom-voiceid")
        or "alloy"
    )

    # Get session from headers, default to test-session
    session_id = websocket.headers.get("x-amzn-bedrock-agentcore-runtime-session-id", "test-session")

    
    logger.info(f"Voice: {voice_id}")
    logger.info(f"Session: {session_id}")
    
    #Initialise Memory Handler.
    memory_handler = MemoryHandler(agentcore_memory_client, memory_id, user_id, session_id)
    

    try:
        
        logger.info("Using OpenAI Realtime API")
        model = BidiOpenAIRealtimeModel(
            model_id="gpt-realtime",
            provider_config={
                "audio": {
                    "voice": voice_id,
                    # OpenAI Realtime uses 24kHz by default
                    "input_rate": 24000,
                    "output_rate": 24000,
                },
            },
            client_config={
                "api_key": openai_key,
                "timeout": 60.0,  # 60 second timeout for OpenAI API calls
            },
            tools=[calculator],            
        )
        logger.info("Retrieiving past conversation...")
        message_history = memory_handler.get_past_conversation()

        

        flattened_message_history = [
            {'role': msg['role'].lower(), 'content': [{'text': msg['content']['text']}]}
            for turn in message_history
            for msg in turn
        ]
        if flattened_message_history and flattened_message_history[0]['role'] == 'assistant':
            flattened_message_history.insert(0, {'role': 'user', 'content': [{'text': 'Hello'}]})
        logger.info(f"Retrieved {len(flattened_message_history)} past messages")
        base_system_prompt = "You are a helpful assistant with access to a calculator tool."

        # Build history string from your messages
        history_text = "\n\n## Previous Conversation:\n"
        for msg in flattened_message_history:
            role = msg['role'].capitalize()
            text = msg['content'][0]['text']
            history_text += f"{role}: {text}\n"

        history_text += "\nContinue the conversation naturally based on this context. Do not repeat or summarize the history. If the user told you their name, address the user by name on any further conversation."

        # Combine into final system prompt
        system_prompt = base_system_prompt + history_text

        logger.info(f"Instantiating BidiAgent with this conversation history: {flattened_message_history}")
        agent = BidiAgent(
            model=model,
            tools=[calculator],
            system_prompt=system_prompt,
        )

        agent.hooks.add_callback(BidiMessageAddedEvent, memory_handler.log_message)

        await agent.run(inputs=[websocket.receive_json], outputs=[chunked_send])

    except Exception as e:
        logger.error(f"Error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        logger.info("Connection closed")
 

if __name__ == "__main__":
    app.run(log_level="info")
