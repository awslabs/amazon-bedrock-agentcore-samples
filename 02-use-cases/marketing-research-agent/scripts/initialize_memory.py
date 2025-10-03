#!/usr/bin/env python3
"""
Memory initialization script for Marketing Research Agent.
This script creates and configures AgentCore Memory resources with marketing intelligence strategies.
"""

import os
import sys
import argparse
import logging
import time
from datetime import datetime

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore.memory.constants import StrategyType
from botocore.exceptions import ClientError
# from src.config import Configuration  # Not needed for this script

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("memory_init")

def create_memory_resource(client: MemoryClient, memory_name: str = "MarketingResearchAgentMemory") -> dict:
    """Create AgentCore Memory resource with marketing intelligence strategies."""
    
    logger.info(f"Checking for existing memory resource: {memory_name}")
    
    try:
        # First, check if memory already exists
        memories = list(client.list_memories())
        logger.info(f"Found {len(memories)} existing memories")
        
        # Look for existing memory by ID pattern (name property is unreliable)
        existing_memory = None
        for m in memories:
            logger.info(f"  Memory ID: {m.get('id')}")
            # Check by ID pattern - this is what actually works
            if m.get('id', '').startswith(memory_name):
                existing_memory = m
                break
        
        if existing_memory:
            logger.info(f"Using existing memory resource")
            logger.info(f"- Memory ID: {existing_memory['id']}")
            logger.info(f"- Memory ARN: {existing_memory.get('arn', 'N/A')}")
            logger.info(f"- Status: {existing_memory.get('status', 'N/A')}")
            return existing_memory
        
        # Create new memory if it doesn't exist
        logger.info(f"Creating new memory resource: {memory_name}")
        memory = client.create_memory_and_wait(
            name=memory_name,
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
        
        logger.info(f"Memory resource created successfully")
        logger.info(f"- Memory ID: {memory['id']}")
        logger.info(f"- Memory ARN: {memory.get('arn', 'N/A')}")
        logger.info(f"- Status: {memory.get('status', 'N/A')}")
        
        return memory
        
    except Exception as e:
        logger.error(f"Failed to create or retrieve memory resource: {e}")
        raise e

def bootstrap_marketing_intelligence(client: MemoryClient, memory_id: str) -> bool:
    """Bootstrap memory with initial marketing intelligence data."""
    
    logger.info("Bootstrapping memory with marketing intelligence data...")
    
    # Sample marketing intelligence conversations to seed the memory
    bootstrap_conversations = [
        {
            "actor_id": "marketing_analyst_001",
            "session_id": "bootstrap_competitive_intel",
            "messages": [
                ("What are the key trends in B2B SaaS marketing for 2024?", "USER"),
                ("Key B2B SaaS marketing trends for 2024 include: 1) Product-led growth strategies, 2) Account-based marketing automation, 3) AI-powered personalization, 4) Customer success integration with marketing, 5) Multi-touch attribution models", "ASSISTANT"),
                ("How should we approach competitive analysis in the AI tools market?", "USER"),
                ("For AI tools competitive analysis: 1) Monitor feature releases and pricing changes, 2) Track customer reviews and sentiment, 3) Analyze marketing messaging and positioning, 4) Study partnership announcements, 5) Watch for talent acquisition patterns", "ASSISTANT")
            ]
        },
        {
            "actor_id": "marketing_strategist_001", 
            "session_id": "bootstrap_customer_segments",
            "messages": [
                ("What are effective customer segmentation strategies for B2B marketing?", "USER"),
                ("Effective B2B customer segmentation includes: 1) Firmographic segmentation (company size, industry, revenue), 2) Behavioral segmentation (usage patterns, engagement levels), 3) Needs-based segmentation (pain points, goals), 4) Technographic segmentation (tech stack, digital maturity)", "ASSISTANT"),
                ("How do we measure marketing campaign effectiveness?", "USER"),
                ("Key marketing metrics include: 1) Lead quality scores and conversion rates, 2) Customer acquisition cost (CAC) and lifetime value (LTV), 3) Pipeline velocity and deal size, 4) Brand awareness and share of voice, 5) Content engagement and attribution", "ASSISTANT")
            ]
        },
        {
            "actor_id": "research_specialist_001",
            "session_id": "bootstrap_research_methods", 
            "messages": [
                ("What are the best practices for market research in technology sectors?", "USER"),
                ("Technology market research best practices: 1) Combine primary research (surveys, interviews) with secondary data, 2) Monitor patent filings and R&D investments, 3) Track developer community engagement, 4) Analyze API usage and integration patterns, 5) Study regulatory and compliance trends", "ASSISTANT"),
                ("How should we structure competitive intelligence reports?", "USER"),
                ("Competitive intelligence reports should include: 1) Executive summary with key findings, 2) Competitor profiles with SWOT analysis, 3) Market positioning maps, 4) Feature comparison matrices, 5) Pricing analysis and recommendations, 6) Strategic implications and action items", "ASSISTANT")
            ]
        }
    ]
    
    try:
        for conversation in bootstrap_conversations:
            logger.info(f"Adding bootstrap conversation for {conversation['actor_id']}")
            
            client.create_event(
                memory_id=memory_id,
                actor_id=conversation["actor_id"],
                session_id=conversation["session_id"],
                messages=conversation["messages"]
            )
            
            # Small delay between conversations
            time.sleep(1)
        
        logger.info("Bootstrap conversations added successfully")
        logger.info("Note: Long-term memory extraction will process these conversations in the background (~1-2 minutes)")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to bootstrap marketing intelligence: {e}")
        return False

def validate_memory_setup(client: MemoryClient, memory_id: str) -> bool:
    """Validate that memory is properly configured and accessible."""
    
    logger.info("Validating memory setup...")
    
    try:
        # List memories to verify access
        memories = list(client.list_memories())
        target_memory = next((m for m in memories if m.get('id') == memory_id), None)
        
        if not target_memory:
            logger.error(f"Memory {memory_id} not found in list")
            return False
        
        logger.info(f"- Memory found: {target_memory.get('name')}")
        logger.info(f"- Status: {target_memory.get('status')}")
        logger.info(f"- Strategies: {len(target_memory.get('strategies', []))}")
        
        # Test event creation
        test_actor_id = f"test_actor_{int(time.time())}"
        test_session_id = f"validation_session_{int(time.time())}"
        
        client.create_event(
            memory_id=memory_id,
            actor_id=test_actor_id,
            session_id=test_session_id,
            messages=[
                ("This is a validation test message", "USER"),
                ("Validation test successful", "ASSISTANT")
            ]
        )
        
        logger.info("Event creation test successful")
        
        # Test event retrieval
        events = client.list_events(
            memory_id=memory_id,
            actor_id=test_actor_id,
            session_id=test_session_id,
            max_results=5
        )
        
        if events:
            logger.info("Event retrieval test successful")
        else:
            logger.warning("Event retrieval returned no results (may be expected)")
        
        return True
        
    except Exception as e:
        logger.error(f"Memory validation failed: {e}")
        return False

def main():
    """Main initialization function."""
    parser = argparse.ArgumentParser(description="Initialize AgentCore Memory for Marketing Research Agent")
    parser.add_argument("--region", default="us-east-1", help="AWS region for memory resources")
    parser.add_argument("--memory-name", default="MarketingResearchAgentMemory", help="Name for the memory resource")
    parser.add_argument("--bootstrap", action="store_true", help="Bootstrap memory with sample marketing intelligence")
    parser.add_argument("--validate-only", action="store_true", help="Only validate existing memory setup")
    
    args = parser.parse_args()
    
    logger.info("Starting AgentCore Memory initialization...")
    logger.info(f"Region: {args.region}")
    logger.info(f"Memory name: {args.memory_name}")
    
    try:
        # Initialize memory client
        client = MemoryClient(region_name=args.region)
        logger.info("Memory client initialized")
        
        if args.validate_only:
            # Just validate existing setup
            memories = list(client.list_memories())
            target_memory = next((m for m in memories if m.get('name') == args.memory_name), None)
            
            if not target_memory:
                logger.error(f"Memory '{args.memory_name}' not found")
                return False
            
            return validate_memory_setup(client, target_memory['id'])
        
        # Create or retrieve memory resource
        memory = create_memory_resource(client, args.memory_name)
        memory_id = memory['id']
        
        # Bootstrap with marketing intelligence if requested
        if args.bootstrap:
            bootstrap_success = bootstrap_marketing_intelligence(client, memory_id)
            if not bootstrap_success:
                logger.warning("Bootstrap failed, but memory resource was created")
        
        # Validate the setup
        validation_success = validate_memory_setup(client, memory_id)
        
        if validation_success:
            logger.info("Memory initialization completed successfully!")
            logger.info(f"Memory ID: {memory_id}")
            logger.info("You can now use this memory with your marketing research agents.")
            return True
        else:
            logger.error("Memory validation failed")
            return False
            
    except Exception as e:
        logger.error(f"Memory initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)