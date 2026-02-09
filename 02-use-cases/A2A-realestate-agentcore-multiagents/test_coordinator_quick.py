#!/usr/bin/env python
"""
Quick Test for Coordinator Agent with OAuth A2A

Simple test script to verify coordinator can communicate with sub-agents.
"""

import os
import sys
import json
import asyncio

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'realestate_coordinator'))

from agent import create_realestate_coordinator, cleanup

async def quick_test():
    """Run a quick test of the coordinator"""
    
    print("\n" + "="*70)
    print("QUICK COORDINATOR TEST - A2A with OAuth")
    print("="*70)
    
    # Load configuration
    print("\n1. Loading configuration...")
    
    # Load deployment info
    script_dir = os.path.dirname(os.path.abspath(__file__))
    deployment_file = os.path.join(script_dir, 'deployment_info.json')
    
    with open(deployment_file, 'r', encoding='utf-8') as f:
        deployment_info = json.load(f)
    
    # Set agent URLs
    for agent in deployment_info['agents']:
        if agent['name'] == 'property_search_agent':
            from urllib.parse import quote
            arn = agent['arn']
            region = arn.split(':')[3]
            escaped_arn = quote(arn, safe='')
            url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{escaped_arn}/invocations/"
            os.environ['PROPERTY_SEARCH_AGENT_URL'] = url
            print(f"   ✓ Property Search Agent URL set")
        
        elif agent['name'] == 'property_booking_agent':
            from urllib.parse import quote
            arn = agent['arn']
            region = arn.split(':')[3]
            escaped_arn = quote(arn, safe='')
            url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{escaped_arn}/invocations/"
            os.environ['PROPERTY_BOOKING_AGENT_URL'] = url
            print(f"   ✓ Property Booking Agent URL set")
    
    # Load bearer token
    token_file = os.path.join(script_dir, '.bearer_token')
    with open(token_file, 'r', encoding='utf-8') as f:
        os.environ['BEARER_TOKEN'] = f.read().strip()
    print(f"   ✓ Bearer token loaded")
    
    # Create coordinator
    print("\n2. Creating coordinator agent...")
    coordinator = create_realestate_coordinator()
    print("   ✓ Coordinator created")
    
    # Test 1: Search properties
    print("\n3. Testing property search...")
    print("   Prompt: 'Find apartments in New York under $4000'")
    
    try:
        result = await coordinator.invoke_async("Find apartments in New York under $4000")
        
        # Extract response text from result
        if hasattr(result, 'text'):
            response = result.text
        elif hasattr(result, 'content'):
            response = result.content
        else:
            response = str(result)
        
        print(f"\n   Response:")
        print(f"   {'-'*66}")
        print(f"   {response[:500] if len(response) > 500 else response}")
        if len(response) > 500:
            print("   ...")
        print(f"   {'-'*66}")
        print("   ✅ Search test PASSED")
    except Exception as e:
        print(f"   ✗ Search test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 2: Get property details
    print("\n4. Testing property details...")
    print("   Prompt: 'Show me details for property PROP003'")
    
    try:
        result = await coordinator.invoke_async("Show me details for property PROP003")
        
        # Extract response text from result
        if hasattr(result, 'text'):
            response = result.text
        elif hasattr(result, 'content'):
            response = result.content
        else:
            response = str(result)
        
        print(f"\n   Response:")
        print(f"   {'-'*66}")
        print(f"   {response[:500] if len(response) > 500 else response}")
        if len(response) > 500:
            print("   ...")
        print(f"   {'-'*66}")
        print("   ✅ Details test PASSED")
    except Exception as e:
        print(f"   ✗ Details test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Cleanup
    print("\n5. Cleaning up...")
    await cleanup()
    print("   ✓ Cleanup complete")
    
    print("\n" + "="*70)
    print("✅ ALL TESTS PASSED")
    print("="*70)
    
    return True

if __name__ == "__main__":
    result = asyncio.run(quick_test())
    sys.exit(0 if result else 1)
