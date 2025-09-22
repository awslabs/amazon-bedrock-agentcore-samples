#!/usr/bin/env python3
"""
Test script for Claude Code Python SDK
"""

import sys
import os

# Add the python-sdk folder to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python-sdk'))

try:
    from claude_code_sdk_wrapper import ClaudeCodeSDK
except ImportError:
    print("❌ Could not import ClaudeCodeSDK. Make sure you're in the right directory.")
    sys.exit(1)

def test_python_sdk():
    """Test the Python SDK wrapper"""
    
    print("🧪 Testing Claude Code Python SDK")
    print("=" * 50)
    
    # Initialize SDK
    try:
        sdk = ClaudeCodeSDK(use_bedrock=True)
        print("✅ SDK initialized with Bedrock configuration")
    except Exception as e:
        print(f"❌ Failed to initialize SDK: {e}")
        return
    
    # Test cases
    test_cases = [
        {
            "name": "Simple Code Generation",
            "prompt": "Create a Python function that reverses a string"
        },
        {
            "name": "Data Structure Creation",
            "prompt": "Create a Python implementation of a binary search tree"
        },
        {
            "name": "Algorithm Implementation",
            "prompt": "Implement the bubble sort algorithm in Python"
        }
    ]
    
    for test in test_cases:
        print(f"\n📝 Test: {test['name']}")
        print(f"   Prompt: {test['prompt'][:50]}...")
        
        try:
            result = sdk.execute(test['prompt'])
            
            if result['success']:
                print(f"   ✅ Success!")
                if 'metadata' in result:
                    meta = result['metadata']
                    print(f"   💰 Cost: ${meta.get('cost_usd', 0):.4f}")
                    print(f"   ⏱️  Duration: {meta.get('duration_ms', 0)/1000:.2f}s")
                    print(f"   🔄 Turns: {meta.get('num_turns', 0)}")
            else:
                print(f"   ❌ Failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
    
    # Test session continuity
    print("\n📝 Test: Session Continuity")
    try:
        result1 = sdk.execute("Create a Python class called Calculator")
        if result1['success'] and result1.get('session_id'):
            session_id = result1['session_id']
            print(f"   ✅ Session created: {session_id[:8]}...")
            
            result2 = sdk.execute(
                "Add a method to calculate compound interest",
                session_id=session_id
            )
            if result2['success']:
                print(f"   ✅ Session continued successfully")
            else:
                print(f"   ❌ Session continuation failed")
        else:
            print(f"   ❌ Could not create session")
    except Exception as e:
        print(f"   ❌ Session test error: {str(e)}")
    
    print("\n" + "=" * 50)
    print("✅ SDK testing complete!")

if __name__ == "__main__":
    # Check for required environment variables
    if not os.environ.get('CLAUDE_CODE_USE_BEDROCK'):
        print("⚠️  Setting CLAUDE_CODE_USE_BEDROCK=1 for testing")
        os.environ['CLAUDE_CODE_USE_BEDROCK'] = '1'
    
    test_python_sdk()
