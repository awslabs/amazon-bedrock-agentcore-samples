#!/usr/bin/env python3
"""
List and manage AgentCore Memory resources

This script helps you find and manage memory resources.
"""

import os
from dotenv import load_dotenv
from bedrock_agentcore.memory import MemoryClient

# Load environment
load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

def list_memories():
    """List all memory resources"""
    try:
        client = MemoryClient(region_name=AWS_REGION)
        memories = client.list_memories()
        
        print(f"\n{'='*60}")
        print(f"AgentCore Memory Resources in {AWS_REGION}")
        print(f"{'='*60}\n")
        
        if not memories:
            print("No memory resources found.")
            return
        
        for i, memory in enumerate(memories, 1):
            print(f"{i}. Name: {memory.get('name')}")
            print(f"   ID: {memory.get('id')}")
            print(f"   Description: {memory.get('description', 'N/A')}")
            print(f"   Created: {memory.get('createdAt', 'N/A')}")
            print()
        
        print(f"Total: {len(memories)} memory resource(s)\n")
        
        # Find InsuranceAgentMemory
        insurance_memory = None
        for memory in memories:
            if memory.get('name') == 'InsuranceAgentMemory':
                insurance_memory = memory
                break
        
        # Find any InsuranceAgentMemory (including ones with suffixes)
        insurance_memories = []
        for memory in memories:
            if 'InsuranceAgentMemory' in memory.get('name', ''):
                insurance_memories.append(memory)
        
        if insurance_memories:
            print(f"✓ Found {len(insurance_memories)} InsuranceAgentMemory resource(s):")
            for mem in insurance_memories:
                print(f"  - {mem.get('name')}: {mem.get('id')}")
            
            # Use the first one
            selected = insurance_memories[0]
            print(f"\n💡 Recommended: Use the first one")
            print(f"\nAdd this to your .env file:")
            print(f'MEMORY_ID="{selected.get("id")}"')
            
            if len(insurance_memories) > 1:
                print(f"\n⚠ Warning: {len(insurance_memories)} duplicate memories found!")
                print(f"   Consider deleting the extras to avoid confusion.")
                print(f"   Keep: {selected.get('name')} ({selected.get('id')})")
        else:
            print("⚠ No InsuranceAgentMemory found")
            print("\nAvailable memory names:")
            for memory in memories:
                print(f"  - {memory.get('name')}")
        
        print()
        
    except Exception as e:
        print(f"Error listing memories: {e}")

if __name__ == "__main__":
    list_memories()
