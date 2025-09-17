"""
Memory Tools for Market Trends Agent

This module contains all memory-related tools for managing broker profiles,
conversation history, and financial interests using AgentCore Memory.
"""

from langchain_core.tools import tool
from bedrock_agentcore.memory import MemoryClient
from botocore.exceptions import ClientError
import hashlib
import logging
import os
import re

# Configure logging
logger = logging.getLogger(__name__)

def cleanup_duplicate_memories():
    """Clean up duplicate memory instances, keeping only the most recent ACTIVE one"""
    region = os.getenv('AWS_REGION', 'us-east-1')
    client = MemoryClient(region_name=region)
    memory_name = "MarketTrendsAgentMultiStrategy"
    
    try:
        memories = client.list_memories()
        market_memories = [m for m in memories if m.get('id', '').startswith(memory_name + '-')]
        
        if len(market_memories) <= 1:
            print(f"Found {len(market_memories)} memory instances - no cleanup needed")
            return
        
        print(f"Found {len(market_memories)} memory instances - cleaning up duplicates...")
        
        # Sort by creation time (if available) or just use the first active one
        active_memories = [m for m in market_memories if m.get('status') == 'ACTIVE']
        
        if active_memories:
            # Keep the first active one, delete the rest
            keep_memory = active_memories[0]
            delete_memories = active_memories[1:] + [m for m in market_memories if m.get('status') != 'ACTIVE']
            
            print(f"Keeping memory: {keep_memory['id']}")
            
            # Save the kept memory ID to file
            with open('.memory_id', 'w') as f:
                f.write(keep_memory['id'])
            
            for memory in delete_memories:
                try:
                    print(f"Deleting duplicate memory: {memory['id']}")
                    client.delete_memory(memory['id'])
                except Exception as e:
                    print(f"Error deleting memory {memory['id']}: {e}")
        
        print("Memory cleanup completed")
        
    except Exception as e:
        print(f"Error during memory cleanup: {e}")

def create_memory():
    """Create or retrieve existing AgentCore Memory for the market trends agent with multiple memory strategies"""
    from bedrock_agentcore.memory.constants import StrategyType
    import boto3
    
    region = os.getenv('AWS_REGION', 'us-east-1')
    memory_name = "MarketTrendsAgentMultiStrategy"
    client = MemoryClient(region_name=region)
    
    # Use SSM Parameter Store for distributed coordination
    ssm_client = boto3.client('ssm', region_name=region)
    param_name = "/bedrock-agentcore/market-trends-agent/memory-id"
    
    # Check SSM Parameter Store for existing memory ID (distributed coordination)
    try:
        response = ssm_client.get_parameter(Name=param_name)
        saved_memory_id = response['Parameter']['Value']
        
        # Verify this memory still exists and is active
        memories = client.list_memories()
        for memory in memories:
            if (memory.get('id') == saved_memory_id and 
                memory.get('status') == 'ACTIVE'):
                logger.info(f"Using memory ID from SSM: {saved_memory_id}")
                return client, saved_memory_id
        
        # Saved memory doesn't exist or isn't active, remove the parameter
        logger.warning(f"Memory ID {saved_memory_id} from SSM is not active, removing parameter")
        try:
            ssm_client.delete_parameter(Name=param_name)
        except Exception as delete_error:
            logger.warning(f"Could not delete SSM parameter: {delete_error}")
            
    except ssm_client.exceptions.ParameterNotFound:
        logger.info("No memory ID found in SSM Parameter Store")
    except Exception as e:
        logger.warning(f"Error reading memory ID from SSM: {e}")
    
    # Fallback: Check local file for development/testing
    memory_id_file = '.memory_id'
    if os.path.exists(memory_id_file):
        try:
            with open(memory_id_file, 'r') as f:
                saved_memory_id = f.read().strip()
            
            # Verify this memory still exists and is active
            memories = client.list_memories()
            for memory in memories:
                if (memory.get('id') == saved_memory_id and 
                    memory.get('status') == 'ACTIVE'):
                    logger.info(f"Using saved memory ID from local file: {saved_memory_id}")
                    
                    # Save to SSM for future distributed access
                    try:
                        ssm_client.put_parameter(
                            Name=param_name,
                            Value=saved_memory_id,
                            Type='String',
                            Overwrite=True,
                            Description='Memory ID for Market Trends Agent'
                        )
                        logger.info("Saved memory ID to SSM Parameter Store")
                    except Exception as ssm_error:
                        logger.warning(f"Could not save to SSM: {ssm_error}")
                    
                    return client, saved_memory_id
            
            # Saved memory doesn't exist or isn't active, remove the file
            logger.warning(f"Saved memory ID {saved_memory_id} is not active, removing file")
            os.remove(memory_id_file)
            
        except Exception as e:
            logger.warning(f"Error reading saved memory ID: {e}")
            if os.path.exists(memory_id_file):
                os.remove(memory_id_file)
    
    # Check if any memory already exists - get the FIRST active one
    logger.info(f"Checking if memory '{memory_name}' already exists...")
    try:
        memories = client.list_memories()
        active_memories = []
        for memory in memories:
            if (memory.get('id', '').startswith(memory_name + '-') and 
                memory.get('status') == 'ACTIVE'):
                active_memories.append(memory)
        
        if active_memories:
            # Use the first active memory and save its ID
            memory_id = active_memories[0]['id']
            logger.info(f"Found existing ACTIVE memory '{memory_name}' with ID: {memory_id}")
            
            # Save the memory ID to SSM Parameter Store for distributed access
            try:
                ssm_client.put_parameter(
                    Name=param_name,
                    Value=memory_id,
                    Type='String',
                    Overwrite=True,
                    Description='Memory ID for Market Trends Agent'
                )
                logger.info("Saved existing memory ID to SSM Parameter Store")
            except Exception as ssm_error:
                logger.warning(f"Could not save to SSM: {ssm_error}")
            
            # Also save to local file for development
            try:
                with open('.memory_id', 'w') as f:
                    f.write(memory_id)
            except Exception as file_error:
                logger.warning(f"Could not save to local file: {file_error}")
            
            # If there are multiple active memories, log a warning
            if len(active_memories) > 1:
                logger.warning(f"Found {len(active_memories)} active memories - using first one: {memory_id}")
            
            return client, memory_id
            
    except Exception as e:
        logger.warning(f"Error checking existing memories: {e}")
    
    # Memory doesn't exist, create it with race condition protection
    logger.info("Creating new AgentCore Memory with multiple memory strategies...")
    
    # Add retry logic to handle race conditions during deployment
    import random
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            # Add small random delay to reduce race condition probability
            if attempt > 0:
                delay = random.uniform(1, 3) * attempt
                logger.info(f"Retry attempt {attempt + 1} after {delay:.1f}s delay...")
                import time
                time.sleep(delay)
                
                # Re-check for existing memories before creating
                memories = client.list_memories()
                for memory in memories:
                    if (memory.get('id', '').startswith(memory_name + '-') and 
                        memory.get('status') == 'ACTIVE'):
                        memory_id = memory['id']
                        logger.info(f"Found memory created by another process: {memory_id}")
                        
                        # Save the memory ID to SSM and local file
                        try:
                            ssm_client.put_parameter(
                                Name=param_name,
                                Value=memory_id,
                                Type='String',
                                Overwrite=True,
                                Description='Memory ID for Market Trends Agent'
                            )
                            logger.info("Saved memory ID to SSM Parameter Store")
                        except Exception as ssm_error:
                            logger.warning(f"Could not save to SSM: {ssm_error}")
                        
                        try:
                            with open('.memory_id', 'w') as f:
                                f.write(memory_id)
                        except Exception as file_error:
                            logger.warning(f"Could not save to local file: {file_error}")
                        
                        return client, memory_id
            
            # Define memory strategies for market trends agent
            strategies = [
                {
                    StrategyType.USER_PREFERENCE.value: {
                        "name": "BrokerPreferences",
                        "description": "Captures broker preferences, risk tolerance, and investment styles",
                        "namespaces": ["market-trends/broker/{actorId}/preferences"]
                    }
                },
                {
                    StrategyType.SEMANTIC.value: {
                        "name": "MarketTrendsSemantic",
                        "description": "Stores financial facts, market analysis, and investment insights",
                        "namespaces": ["market-trends/broker/{actorId}/semantic"]
                    }
                }
            ]
            
            memory = client.create_memory_and_wait(
                name=memory_name,
                description="Market Trends Agent with multi-strategy memory for broker financial interests",
                strategies=strategies,  # Multiple memory strategies for comprehensive storage
                event_expiry_days=90,  # Keep conversations for 90 days (longer for financial data)
                max_wait=300,
                poll_interval=10
            )
            memory_id = memory['id']
            break  # Success, exit retry loop
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ValidationException' and "already exists" in str(e):
                # Another process created the memory, try to find it
                logger.info(f"Memory creation conflict on attempt {attempt + 1}, checking for existing memory...")
                try:
                    memories = client.list_memories()
                    for memory in memories:
                        if (memory.get('id', '').startswith(memory_name + '-') and 
                            memory.get('status') == 'ACTIVE'):
                            memory_id = memory['id']
                            logger.info(f"Using memory created by another process: {memory_id}")
                            
                            # Save the memory ID to file for future use
                            with open(memory_id_file, 'w') as f:
                                f.write(memory_id)
                            
                            return client, memory_id
                except Exception as find_error:
                    logger.warning(f"Error finding existing memory: {find_error}")
                
                if attempt == max_retries - 1:
                    raise Exception(f"Could not create or find memory after {max_retries} attempts")
            else:
                if attempt == max_retries - 1:
                    logger.error(f"Error creating memory on final attempt: {e}")
                    raise
                else:
                    logger.warning(f"Error creating memory on attempt {attempt + 1}: {e}")
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Unexpected error creating memory: {e}")
                raise
            else:
                logger.warning(f"Unexpected error on attempt {attempt + 1}: {e}")
    
    # If we get here, memory was created successfully
    logger.info(f"Multi-strategy memory created successfully with ID: {memory_id}")
    
    # Save the memory ID to SSM Parameter Store for distributed access
    try:
        ssm_client.put_parameter(
            Name=param_name,
            Value=memory_id,
            Type='String',
            Overwrite=True,
            Description='Memory ID for Market Trends Agent'
        )
        logger.info("Saved new memory ID to SSM Parameter Store")
    except Exception as ssm_error:
        logger.warning(f"Could not save to SSM: {ssm_error}")
    
    # Also save to local file for development
    try:
        with open('.memory_id', 'w') as f:
            f.write(memory_id)
    except Exception as file_error:
        logger.warning(f"Could not save to local file: {file_error}")
    
    return client, memory_id

def extract_actor_id(user_message: str) -> str:
    """Extract actor_id from broker card format or user message"""
    # Look for broker card format: "Name: [Name]"
    name_match = re.search(r'Name:\s*([^\n]+)', user_message, re.IGNORECASE)
    if name_match:
        name = name_match.group(1).strip()
        if name and name.lower() != "unknown":
            # Clean name for actor_id
            clean_name = re.sub(r'[^a-zA-Z0-9]', '_', name.lower())
            return f"broker_{clean_name}"
    
    # Look for "I'm [Name]" or "My name is [Name]" patterns
    intro_patterns = [
        r"I'?m\s+([A-Z][a-zA-Z\s]+?)(?:\s+from|\s+at|\s*[,.]|$)",
        r"My name is\s+([A-Z][a-zA-Z\s]+?)(?:\s+from|\s+at|\s*[,.]|$)",
        r"This is\s+([A-Z][a-zA-Z\s]+?)(?:\s+from|\s+at|\s*[,.]|$)"
    ]
    
    for pattern in intro_patterns:
        match = re.search(pattern, user_message, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if len(name.split()) <= 3:  # Reasonable name length
                clean_name = re.sub(r'[^a-zA-Z0-9]', '_', name.lower())
                return f"broker_{clean_name}"
    
    # Fallback: use message hash for anonymous users
    message_hash = hashlib.sha256(user_message.lower().encode()).hexdigest()[:8]
    return f"user_{message_hash}"

def get_namespaces(mem_client: MemoryClient, memory_id: str) -> dict:
    """Get namespace mapping for memory strategies."""
    try:
        strategies = mem_client.get_memory_strategies(memory_id)
        return {i["type"]: i["namespaces"][0] for i in strategies}
    except Exception as e:
        logger.error(f"Error getting namespaces: {e}")
        return {}

def create_memory_tools(memory_client: MemoryClient, memory_id: str, session_id: str, default_actor_id: str):
    """Create memory tools with the provided memory client and configuration"""
    
    @tool
    def list_conversation_history(actor_id_override: str = None):
        """Retrieve recent conversation history and user preferences from memory"""
        try:
            # Use provided actor_id or default
            current_actor_id = actor_id_override or default_actor_id
            
            events = memory_client.list_events(
                memory_id=memory_id,
                actor_id=current_actor_id,
                session_id=session_id,
                max_results=10
            )
            
            if events:
                # Convert events to readable format
                history_parts = []
                for i, event in enumerate(events[-5:], 1):  # Show last 5 events
                    if 'messages' in event:
                        for message in event['messages']:
                            content = message.get('content', '').strip()
                            role = message.get('role', 'unknown')
                            if content:
                                history_parts.append(f"{role.upper()}: {content[:100]}...")
                
                if history_parts:
                    return "Recent conversation history:\n" + "\n".join(history_parts)
                else:
                    return "No meaningful conversation history found"
            else:
                return "No conversation history available"
                
        except Exception as e:
            logger.error(f"Error retrieving conversation history: {e}")
            return "No conversation history available"

    @tool
    def get_broker_financial_profile(actor_id_override: str = None):
        """Retrieve the long-term financial interests and investment profile from multiple memory strategies
        
        Args:
            actor_id_override: Specific actor_id to retrieve profile for (use the actor_id from identify_broker())
        """
        try:
            # Use provided actor_id or default
            current_actor_id = actor_id_override or default_actor_id
            
            if not actor_id_override:
                return "No actor_id provided. Please use identify_broker() first to get the correct actor_id, then call this function with that actor_id."
            
            # Get namespaces for all memory strategies
            namespaces_dict = get_namespaces(memory_client, memory_id)
            
            all_profile_info = []
            
            # Retrieve from all memory strategies
            for strategy_type, namespace_template in namespaces_dict.items():
                try:
                    namespace = namespace_template.format(actorId=current_actor_id)
                    
                    memories = memory_client.retrieve_memories(
                        memory_id=memory_id,
                        namespace=namespace,
                        query="broker financial profile investment preferences risk tolerance",
                        top_k=3
                    )
                    
                    for memory in memories:
                        if isinstance(memory, dict):
                            content = memory.get('content', {})
                            if isinstance(content, dict):
                                text = content.get('text', '').strip()
                                if text and len(text) > 20:  # Meaningful content
                                    all_profile_info.append(f"[{strategy_type.upper()}] {text}")
                                    
                except Exception as strategy_error:
                    logger.info(f"No memories found in {strategy_type} strategy: {strategy_error}")
            
            if all_profile_info:
                return "Broker Financial Profile:\n" + "\n\n".join(all_profile_info)
            else:
                # Fallback: Get recent events to build profile from conversation history
                events = memory_client.list_events(
                    memory_id=memory_id,
                    actor_id=current_actor_id,
                    session_id=session_id,
                    max_results=10
                )
                
                if events:
                    profile_elements = []
                    for event in events:
                        if 'messages' in event:
                            for message in event['messages']:
                                content = message.get('content', '')
                                # Look for profile-related information
                                if any(keyword in content.lower() for keyword in ['broker', 'investment', 'risk tolerance', 'portfolio', 'preference', 'client']):
                                    if len(content) > 50:  # Meaningful content
                                        profile_elements.append(content[:200] + "..." if len(content) > 200 else content)
                    
                    if profile_elements:
                        return "Broker Profile (from conversation history):\n" + "\n\n".join(profile_elements[-2:])
                    else:
                        return "Building financial profile from our conversations. Profile will be enhanced as we continue our discussions."
                else:
                    return "No financial profile found for this broker yet. This will be created as we learn about their investment preferences."
                
        except Exception as e:
            logger.error(f"Error retrieving broker financial profile: {e}")
            return "Unable to retrieve financial profile at this time"
    
    @tool 
    def update_broker_financial_interests(interests_update: str, actor_id_override: str = None):
        """Update or add to the broker's financial interests and investment preferences
        
        Args:
            interests_update: New financial interests, preferences, or profile updates to store
            actor_id_override: Specific actor_id to store profile for (use the actor_id from identify_broker())
        """
        try:
            # Use provided actor_id or default
            current_actor_id = actor_id_override or default_actor_id
            
            if not actor_id_override:
                return "No actor_id provided. Please use identify_broker() first to get the correct actor_id, then call this function with that actor_id."
            
            # Create an event with proper roles for memory storage
            conversation = [
                (f"Please update my financial profile with this information: {interests_update}", "USER"),
                ("I've updated your financial profile with the new information. This will be included in your long-term investment profile for future reference.", "ASSISTANT")
            ]
            
            memory_client.create_event(
                memory_id=memory_id,
                actor_id=current_actor_id,
                session_id=session_id,
                messages=conversation
            )
            
            return "Financial interests successfully updated in long-term memory profile"
            
        except Exception as e:
            logger.error(f"Error updating financial interests: {e}")
            return "Unable to update financial interests at this time"
    
    @tool
    def identify_broker(user_message: str):
        """Identify the broker from their message and return their consistent actor_id
        
        Args:
            user_message: The user's message containing identity information (broker card format or introduction)
            
        Returns:
            Information about the identified broker and their actor_id for use in other memory functions
        """
        try:
            # Extract actor_id using simple parsing
            identified_actor_id = extract_actor_id(user_message)
            
            # Try to get existing profile for this broker across all sessions
            try:
                # Check all namespaces for existing profile data
                namespaces_dict = get_namespaces(memory_client, memory_id)
                found_existing_profile = False
                
                for strategy_type, namespace_template in namespaces_dict.items():
                    try:
                        namespace = namespace_template.format(actorId=identified_actor_id)
                        memories = memory_client.retrieve_memories(
                            memory_id=memory_id,
                            namespace=namespace,
                            query="broker profile investment preferences",
                            top_k=1
                        )
                        if memories:
                            found_existing_profile = True
                            break
                    except Exception as memory_error:
                        logger.debug(f"No memories found in {strategy_type}: {memory_error}")
                        continue
                
                if found_existing_profile:
                    return f"ACTOR_ID: {identified_actor_id}\nSTATUS: Existing broker found\nACTION: Use get_broker_financial_profile('{identified_actor_id}') to retrieve their stored preferences."
                else:
                    return f"ACTOR_ID: {identified_actor_id}\nSTATUS: New broker\nACTION: Use update_broker_financial_interests(profile_info, '{identified_actor_id}') to store their preferences."
                    
            except Exception as e:
                return f"ACTOR_ID: {identified_actor_id}\nSTATUS: Unable to check existing profile\nERROR: {e}\nACTION: Proceed as new broker and use update_broker_financial_interests(profile_info, '{identified_actor_id}')"
                
        except Exception as e:
            logger.error(f"Error identifying broker: {e}")
            return f"ERROR: Unable to identify broker - {e}"
    
    return [
        list_conversation_history,
        get_broker_financial_profile,
        update_broker_financial_interests,
        identify_broker
    ]