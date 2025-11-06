"""
AgentCore Memory Utilities

This module provides utility functions for retrieving and formatting conversation
messages from Bedrock Agent Core memory system.
"""

import logging
from typing import List, Dict, Any
from bedrock_agentcore.memory import MemoryClient

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agentcore-memory-utils")

def get_agentcore_memory_messages(
    memory_client: MemoryClient,
    memory_id: str,
    actor_id: str,
    session_id: str,
    last_k_turns: int = 20
) -> List[Dict[str, Any]]:
    """
    Retrieve conversation messages from AgentCore memory and format them.
    
    This function retrieves the specified number of conversation turns from memory
    and formats them in the standard message format with role and content structure.
    
    Args:
        memory_client: Client for interacting with Bedrock Agent Core memory
        memory_id: ID of the memory resource
        actor_id: ID of the user/actor
        session_id: ID of the current conversation session
        last_k_turns: Number of conversation turns to retrieve from history (default: 20)
    
    Returns:
        List of formatted messages in the format:
        [
            {"role": "user", "content": [{"text": "Hello, my name is Strands!"}]},
            {"role": "assistant", "content": [{"text": "Hi there! How can I help you today?"}]}
        ]
    
    Raises:
        Exception: If there's an error retrieving messages from memory
    """
    try:
        # Pretty console output for memory retrieval start
        print("\n" + "="*70)
        print("🧠 AGENTCORE MEMORY RETRIEVAL")
        print("="*70)
        print(f"📋 Memory ID: {memory_id}")
        print(f"👤 Actor ID: {actor_id}")
        print(f"🔗 Session ID: {session_id}")
        print(f"🔄 Requesting turns: {last_k_turns}")
        print("-"*70)
        
        # Load the specified number of conversation turns from memory
        print(f"⏳ Retrieving {last_k_turns} conversation turns from memory...")
        
        recent_turns = memory_client.get_last_k_turns(
            memory_id=memory_id,
            actor_id=actor_id,
            session_id=session_id,
            k=last_k_turns
        )
        
        formatted_messages = []
        
        if recent_turns:
            print(f"✅ Successfully retrieved {len(recent_turns)} conversation turns")
            print("-"*70)
            
            # Process each turn in the conversation
            for turn_idx, turn in enumerate(recent_turns, 1):
                print(f"📝 Processing Turn {turn_idx}:")
                
                for msg_idx, message in enumerate(turn, 1):
                    # Extract role and content from the memory format
                    raw_role = message.get('role', 'user')
                    
                    # Normalize role to lowercase to match Bedrock Converse API requirements
                    role = raw_role.lower() if isinstance(raw_role, str) else 'user'
                    
                    if role not in ['user', 'assistant']:
                        print(f"⚠️  Invalid role '{role}' found, defaulting to 'user'")
                        role = 'user'
                    
                    # Handle different content formats
                    content_text = ""
                    if 'content' in message:
                        if isinstance(message['content'], dict) and 'text' in message['content']:
                            content_text = message['content']['text']
                        elif isinstance(message['content'], str):
                            content_text = message['content']
                        elif isinstance(message['content'], list):
                            # Handle list of content items
                            for content_item in message['content']:
                                if isinstance(content_item, dict) and 'text' in content_item:
                                    content_text = content_item['text']
                                    break
                                elif isinstance(content_item, str):
                                    content_text = content_item
                                    break
                    
                    # Skip messages with empty content
                    if not content_text.strip():
                        print(f"⚠️  Skipping message {msg_idx} with empty content")
                        continue
                    
                    # Format message in the required structure
                    formatted_message = {
                        "role": role,
                        "content": [{"text": content_text}]
                    }
                    
                    formatted_messages.append(formatted_message)
                    
                    # Pretty output for each processed message
                    role_icon = "🤖" if role == 'assistant' else "👤"
                    content_preview = content_text[:100] + "..." if len(content_text) > 100 else content_text
                    print(f"   {role_icon} {role.upper()}: {content_preview}")
            
            print("-"*70)
            print(f"✨ Successfully formatted {len(formatted_messages)} messages")
        else:
            print("📭 No conversation history found in memory")
        
        print("="*70 + "\n")
        # Return messages in inverted order (most recent first)
        return formatted_messages[::-1]
        
    except Exception as e:
        print("❌ ERROR: Failed to retrieve messages from AgentCore memory")
        print(f"💥 Exception: {str(e)}")
        print("="*70 + "\n")
        logger.error(f"Error retrieving messages from memory: {e}")
        raise Exception(f"Failed to retrieve messages from AgentCore memory: {str(e)}")
