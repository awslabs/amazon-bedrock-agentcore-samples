#!/usr/bin/env python3
"""
Create AgentCore Memory resource for the insurance agent

Run this once to create the memory, then add the ID to .env
"""

import os
from dotenv import load_dotenv
from bedrock_agentcore.memory import MemoryClient

# Load environment
load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

def create_memory():
    """Create a new memory resource"""
    try:
        client = MemoryClient(region_name=AWS_REGION)
        
        print(f"\n{'='*60}")
        print(f"Creating AgentCore Memory in {AWS_REGION}")
        print(f"{'='*60}\n")
        
        print("Creating InsuranceAgentMemory...")
        memory_resource = client.create_memory_and_wait(
            name="InsuranceAgentMemory",
            description="Insurance agent conversation memory",
            strategies=[{
                "userPreferenceMemoryStrategy": {
                    "name": "CustomerPreferences",
                    "description": "Customer insurance preferences and history",
                    "namespaces": ["/insurance/customers/{actorId}"]
                }
            }]
        )
        
        memory_id = memory_resource.get('id')
        print(f"✓ Memory created successfully!")
        print(f"\nMemory ID: {memory_id}")
        print(f"\nAdd this to your .env file:")
        print(f'MEMORY_ID="{memory_id}"')
        print()
        
        # Optionally update .env file
        env_file = "../.env" if os.path.exists("../.env") else ".env"
        if os.path.exists(env_file):
            response = input(f"\nUpdate {env_file} automatically? (y/n): ")
            if response.lower() == 'y':
                with open(env_file, 'a') as f:
                    f.write(f'\n# AgentCore Memory (auto-added)\nMEMORY_ID="{memory_id}"\n')
                print(f"✓ Updated {env_file}")
        
    except Exception as e:
        print(f"Error creating memory: {e}")
        if "already exists" in str(e):
            print("\nMemory already exists! Use list_memories.py to find it.")

if __name__ == "__main__":
    create_memory()
