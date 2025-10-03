#!/usr/bin/env python3
"""
Clean up duplicate memories and create a fresh one with proper strategies.
"""

import os
import sys
import logging
from datetime import datetime

# Add the project root to the path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore.memory.constants import StrategyType
from src.config import config

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("clean_memory")

def clean_and_recreate_memory():
    """Delete all MarketingResearchAgentMemory resources and create a fresh one."""
    
    logger.info("Cleaning up duplicate memories and creating fresh one...")
    
    try:
        client = MemoryClient(region_name=config.aws_region)
        
        # List all memories
        memories = list(client.list_memories())
        logger.info(f"Found {len(memories)} memory resources")
        
        # Delete all MarketingResearchAgentMemory resources
        marketing_memories = []
        for memory in memories:
            if 'MarketingResearchAgentMemory' in memory.get('id', ''):
                marketing_memories.append(memory)
        
        logger.info(f"Found {len(marketing_memories)} MarketingResearchAgentMemory resources to delete")
        
        for memory in marketing_memories:
            try:
                logger.info(f"Deleting memory: {memory['id']}")
                client.delete_memory_and_wait(
                    memory_id=memory['id'],
                    max_wait=120,
                    poll_interval=5
                )
                logger.info(f"Deleted: {memory['id']}")
            except Exception as e:
                logger.error(f"Failed to delete {memory['id']}: {e}")
        
        # Wait a moment for cleanup
        import time
        logger.info("Waiting 5 seconds for cleanup...")
        time.sleep(5)
        
        # Create a fresh memory with proper strategies
        logger.info("Creating fresh memory with strategies...")
        
        memory = client.create_memory_and_wait(
            name="MarketingResearchAgentMemory",
            description="Memory for marketing research agent system with competitive intelligence and team preferences",
            strategies=[
                {
                    StrategyType.SEMANTIC.value: {
                        "name": "MarketIntelligence",
                        "description": "Captures market research facts and competitor intelligence",
                        "namespaces": ["marketing/{actorId}/intelligence"]
                    }
                },
                {
                    StrategyType.USER_PREFERENCE.value: {
                        "name": "TeamPreferences", 
                        "description": "Tracks marketing team preferences and methodologies",
                        "namespaces": ["marketing/{actorId}/preferences"]
                    }
                },
                {
                    StrategyType.SUMMARY.value: {
                        "name": "SessionSummaries",
                        "description": "Creates summaries of research sessions and findings",
                        "namespaces": ["marketing/{actorId}/summaries/{sessionId}"]
                    }
                }
            ],
            event_expiry_days=7,
            max_wait=300,
            poll_interval=10
        )
        
        memory_id = memory['id']
        logger.info(f"Created fresh memory: {memory_id}")
        
        # Verify the memory has strategies
        memory_details = client.get_memory(memoryId=memory_id)
        strategies = memory_details.get('strategies', [])
        logger.info(f"Memory has {len(strategies)} strategies:")
        
        for i, strategy in enumerate(strategies, 1):
            strategy_type = list(strategy.keys())[0] if strategy else "unknown"
            strategy_info = strategy.get(strategy_type, {})
            logger.info(f"   {i}. {strategy_type}: {strategy_info.get('name')}")
            logger.info(f"      Namespaces: {strategy_info.get('namespaces', [])}")
        
        # Test basic operations
        logger.info("Testing basic memory operations...")
        
        import uuid
        test_actor_id = f"test_actor_{uuid.uuid4().hex[:8]}"
        test_session_id = f"test_session_{uuid.uuid4().hex[:8]}"
        
        # Create test event
        client.create_event(
            memory_id=memory_id,
            actor_id=test_actor_id,
            session_id=test_session_id,
            messages=[
                ("This is a test of the new memory system", "USER"),
                ("Test successful - memory is working with strategies", "ASSISTANT")
            ]
        )
        logger.info("Event creation successful")
        
        # List events
        events = client.list_events(
            memory_id=memory_id,
            actor_id=test_actor_id,
            session_id=test_session_id,
            max_results=5
        )
        logger.info(f"Event listing successful - found {len(events)} events")
        
        logger.info("🎉 Memory cleanup and recreation completed successfully!")
        logger.info(f"New memory ID: {memory_id}")
        logger.info("You can now run 'task run' to test the agent with proper memory!")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to clean and recreate memory: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    success = clean_and_recreate_memory()
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)