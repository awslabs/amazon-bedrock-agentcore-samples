#!/usr/bin/env python3
"""
Test script to verify strands-agents framework
"""

import os
import sys
from dotenv import load_dotenv

def test_strands_import():
    """Test strands-agents framework import"""
    print("Testing Strands-Agents Import")
    print("=" * 40)
    
    try:
        from strands import Agent, tool
        from strands.models import BedrockModel
        print("✓ strands-agents framework imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Failed to import strands-agents framework: {e}")
        print("Run: pip install strands-agents")
        return False

def test_bedrock_model():
    """Test BedrockModel creation"""
    print("\nTesting BedrockModel Creation")
    print("=" * 40)
    
    load_dotenv()
    
    try:
        from strands.models import BedrockModel
        
        model = BedrockModel(
            model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
            aws_region=os.getenv('AWS_REGION', 'us-east-1')
        )
        print("✓ BedrockModel created successfully")
        return True
    except Exception as e:
        print(f"✗ BedrockModel creation failed: {e}")
        return False

def test_agent_creation():
    """Test Agent creation"""
    print("\nTesting Agent Creation")
    print("=" * 40)
    
    try:
        from strands import Agent, tool
        from strands.models import BedrockModel
        
        # Create a simple tool
        @tool
        def test_tool(message: str) -> str:
            """A simple test tool"""
            return f"Tool received: {message}"
        
        model = BedrockModel(
            model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
            aws_region=os.getenv('AWS_REGION', 'us-east-1')
        )
        
        agent = Agent(
            model=model,
            tools=[test_tool],
            system_prompt="You are a test agent."
        )
        
        print("✓ Agent created successfully with tools")
        return True
    except Exception as e:
        print(f"✗ Agent creation failed: {e}")
        return False

def main():
    """Run all strands-agents tests"""
    print("Strands-Agents Framework Tests")
    print("=" * 50)
    
    load_dotenv()
    
    tests = [
        test_strands_import,
        test_bedrock_model,
        test_agent_creation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ Test failed with exception: {e}")
        print()
    
    print("=" * 50)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 Strands-Agents framework is working correctly!")
        return 0
    else:
        print("❌ Some strands-agents tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
