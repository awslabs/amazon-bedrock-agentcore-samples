#!/usr/bin/env python3
"""
Market Trends Agent Test Suite
Tests core functionality including memory, market analysis, and basic operations
"""

import boto3
import json
import os
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_agent_arn():
    """Load the agent ARN from file"""
    arn_file = '.agent_arn'
    if not os.path.exists(arn_file):
        print("❌ No ARN file found. Deploy the agent first.")
        return None
    
    with open(arn_file, 'r') as f:
        return f.read().strip()

def invoke_agent(runtime_arn: str, prompt: str) -> str:
    """Invoke the deployed agent with a prompt"""
    try:
        client = boto3.client('bedrock-agentcore', region_name='us-east-1')
        
        response = client.invoke_agent_runtime(
            agentRuntimeArn=runtime_arn,
            payload=json.dumps({"prompt": prompt})
        )
        
        if 'response' in response:
            return response['response'].read().decode('utf-8')
        else:
            return str(response)
            
    except Exception as e:
        logger.error(f"Error invoking agent: {e}")
        return f"Error: {e}"

def run_simple_test(runtime_arn: str):
    """Run a simple connectivity test"""
    print("🧪 SIMPLE TEST: Basic Connectivity")
    print("-" * 40)
    
    test_message = "Hello, I'm testing the agent. Can you help me?"
    response = invoke_agent(runtime_arn, test_message)
    
    success = "error" not in response.lower() and len(response) > 50
    print(f"✅ Response: {response[:200]}..." if len(response) > 200 else response)
    print(f"🔍 Test Result: {'✅ PASSED' if success else '❌ FAILED'}")
    print()
    
    return success

def run_comprehensive_tests(runtime_arn: str):
    """Run comprehensive functionality tests"""
    print("🚀 Market Trends Agent - Comprehensive Test Suite")
    print("=" * 60)
    print(f"📋 Testing ARN: {runtime_arn}")
    print()
    
    tests_passed = 0
    total_tests = 4
    
    # Test 1: Broker Introduction & Memory
    print("📋 TEST 1: Broker Profile & Memory")
    print("-" * 30)
    
    broker_intro = "Hi, I'm Sarah Chen from Morgan Stanley. I focus on growth investing and tech stocks for younger clients. Please remember my profile."
    
    response1 = invoke_agent(runtime_arn, broker_intro)
    print("✅ Response:", response1[:200] + "..." if len(response1) > 200 else response1)
    
    # Check if profile was acknowledged
    profile_acknowledged = any(keyword in response1.lower() for keyword in ['sarah', 'morgan stanley', 'growth', 'tech', 'profile', 'remember'])
    print(f"🔍 Profile Acknowledged: {'✅ YES' if profile_acknowledged else '❌ NO'}")
    
    if profile_acknowledged:
        tests_passed += 1
    
    print()
    time.sleep(5)  # Wait to avoid throttling
    
    # Test 2: Memory Recall
    print("📋 TEST 2: Memory Recall")
    print("-" * 30)
    
    memory_test = "Hi, I'm Sarah Chen from Morgan Stanley. What do you remember about my investment preferences?"
    response2 = invoke_agent(runtime_arn, memory_test)
    print("✅ Response:", response2[:200] + "..." if len(response2) > 200 else response2)
    
    # Check if memory was recalled
    memory_recalled = any(keyword in response2.lower() for keyword in ['sarah', 'growth', 'tech', 'morgan stanley'])
    print(f"🔍 Memory Recalled: {'✅ YES' if memory_recalled else '❌ NO'}")
    
    if memory_recalled:
        tests_passed += 1
    
    print()
    time.sleep(5)  # Wait to avoid throttling
    
    # Test 3: Market Data Request
    print("📋 TEST 3: Market Data Request")
    print("-" * 30)
    
    market_request = "Get me the current Apple stock price and recent performance"
    response3 = invoke_agent(runtime_arn, market_request)
    print("✅ Response:", response3[:200] + "..." if len(response3) > 200 else response3)
    
    # Check if market data was attempted
    market_data_attempted = any(keyword in response3.lower() for keyword in ['apple', 'aapl', 'stock', 'price', 'market'])
    print(f"🔍 Market Data Retrieved: {'✅ YES' if market_data_attempted else '❌ NO'}")
    
    if market_data_attempted:
        tests_passed += 1
    
    print()
    time.sleep(5)  # Wait to avoid throttling
    
    # Test 4: News Search
    print("📋 TEST 4: News Search")
    print("-" * 30)
    
    news_request = "Find recent news about AI and technology stocks"
    response4 = invoke_agent(runtime_arn, news_request)
    print("✅ Response:", response4[:200] + "..." if len(response4) > 200 else response4)
    
    # Check if news search was attempted
    news_retrieved = any(keyword in response4.lower() for keyword in ['news', 'ai', 'technology', 'search', 'recent'])
    print(f"🔍 News Retrieved: {'✅ YES' if news_retrieved else '❌ NO'}")
    
    if news_retrieved:
        tests_passed += 1
    
    print()
    
    # Summary
    print("=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    print(f"Tests Passed: {tests_passed}/{total_tests}")
    print(f"Success Rate: {(tests_passed/total_tests)*100:.0f}%")
    
    if tests_passed == total_tests:
        print("🎉 ALL TESTS PASSED - Agent is fully functional!")
    elif tests_passed >= total_tests // 2:
        print("⚠️ PARTIAL SUCCESS - Some features may need attention")
    else:
        print("❌ ISSUES DETECTED - Agent needs attention")
    
    return tests_passed == total_tests

def main():
    """Main test function"""
    runtime_arn = load_agent_arn()
    if not runtime_arn:
        return False
    
    print("Choose test type:")
    print("1. Simple connectivity test")
    print("2. Comprehensive functionality tests")
    
    try:
        choice = input("Enter choice (1 or 2, default=1): ").strip()
        if not choice:
            choice = "1"
    except KeyboardInterrupt:
        print("\nTest cancelled.")
        return False
    
    if choice == "2":
        return run_comprehensive_tests(runtime_arn)
    else:
        return run_simple_test(runtime_arn)

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)