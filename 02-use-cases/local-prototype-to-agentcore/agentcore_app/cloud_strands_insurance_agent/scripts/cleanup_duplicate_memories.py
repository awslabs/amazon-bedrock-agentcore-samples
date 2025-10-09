#!/usr/bin/env python3
"""
Cleanup script to delete duplicate InsuranceAgentMemory resources

This script will:
1. List all memories
2. Find all "InsuranceAgentMemory" instances
3. Keep the oldest one
4. Delete the duplicates
"""

import boto3
import sys
from datetime import datetime

def cleanup_duplicate_memories(region='us-east-1', dry_run=True):
    """
    Clean up duplicate memory resources
    
    Args:
        region: AWS region
        dry_run: If True, only show what would be deleted without actually deleting
    """
    client = boto3.client('bedrock-agentcore-control', region_name=region)
    
    print(f"Listing memories in region: {region}")
    print("=" * 60)
    
    try:
        response = client.list_memories()
        memories = response.get('memories', [])
        
        print(f"Found {len(memories)} total memories")
        
        # Filter for InsuranceAgentMemory
        insurance_memories = [m for m in memories if m.get('name') == 'InsuranceAgentMemory']
        
        if len(insurance_memories) <= 1:
            print(f"\n✓ Only {len(insurance_memories)} InsuranceAgentMemory found - no cleanup needed")
            return
        
        print(f"\n⚠️  Found {len(insurance_memories)} duplicate InsuranceAgentMemory resources")
        print("\nMemories:")
        for i, memory in enumerate(insurance_memories, 1):
            memory_id = memory.get('id', 'unknown')
            created = memory.get('createdAt', 'unknown')
            status = memory.get('status', 'unknown')
            print(f"  {i}. ID: {memory_id}")
            print(f"     Created: {created}")
            print(f"     Status: {status}")
        
        # Sort by creation time (oldest first)
        insurance_memories.sort(key=lambda x: x.get('createdAt', ''))
        
        # Keep the first (oldest) one
        keep_memory = insurance_memories[0]
        delete_memories = insurance_memories[1:]
        
        print(f"\n📌 Will KEEP: {keep_memory.get('id')} (oldest)")
        print(f"🗑️  Will DELETE: {len(delete_memories)} duplicate(s)")
        
        if dry_run:
            print("\n" + "=" * 60)
            print("DRY RUN MODE - No memories will be deleted")
            print("To actually delete, run: python cleanup_duplicate_memories.py --delete")
            print("=" * 60)
            print(f"\nTo use the kept memory, add this to your .env file:")
            print(f"MEMORY_ID={keep_memory.get('id')}")
            return keep_memory.get('id')
        
        # Actually delete the duplicates
        print("\n" + "=" * 60)
        print("DELETING DUPLICATES...")
        print("=" * 60)
        
        for memory in delete_memories:
            memory_id = memory.get('id')
            try:
                print(f"\nDeleting: {memory_id}")
                client.delete_memory(id=memory_id)
                print(f"  ✓ Deleted successfully")
            except Exception as e:
                print(f"  ✗ Failed to delete: {str(e)}")
        
        print("\n" + "=" * 60)
        print("CLEANUP COMPLETE")
        print("=" * 60)
        print(f"\nKept memory ID: {keep_memory.get('id')}")
        print(f"\nAdd this to your .env file to prevent future duplicates:")
        print(f"MEMORY_ID={keep_memory.get('id')}")
        
        return keep_memory.get('id')
        
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Cleanup duplicate InsuranceAgentMemory resources')
    parser.add_argument('--region', default='us-east-1', help='AWS region (default: us-east-1)')
    parser.add_argument('--delete', action='store_true', help='Actually delete duplicates (default is dry-run)')
    
    args = parser.parse_args()
    
    if not args.delete:
        print("\n⚠️  Running in DRY RUN mode - no memories will be deleted")
        print("Use --delete flag to actually delete duplicates\n")
    
    memory_id = cleanup_duplicate_memories(region=args.region, dry_run=not args.delete)
    
    if memory_id and args.delete:
        print(f"\n✓ Cleanup complete! Use MEMORY_ID={memory_id} in your .env file")
