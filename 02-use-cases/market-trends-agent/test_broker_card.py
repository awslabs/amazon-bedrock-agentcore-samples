#!/usr/bin/env python3
"""
Test the conversational broker card functionality

This demonstrates the correct way users should interact with the Market Trends Agent:
1. Send broker profile in structured format
2. Agent parses and stores the profile in memory
3. All future interactions are personalized based on the stored profile
"""

import boto3
import json
from botocore.config import Config

def test_broker_card_conversation():
    """Test the broker card parsing and memory functionality"""
    
    # Load agent ARN
    with open('.agent_arn', 'r') as f:
        runtime_arn = f.read().strip()
    
    client = boto3.client('bedrock-agentcore', region_name='us-east-1')
    
    # Test 1: Send broker card format - This is how users should provide their profile
    broker_card_prompt = """Name: Maria Rodriguez
Company: JP Morgan Chase
Role: Senior Investment Advisor
Preferred News Feed: Reuters
Industry Interests: cryptocurrency, fintech, gaming
Investment Strategy: growth investing
Risk Tolerance: aggressive
Client Demographics: millennial retail investors
Geographic Focus: Latin America, Asia-Pacific
Recent Interests: blockchain technology, NFTs, metaverse"""
    
    print("🧪 Testing Broker Card Parsing...")
    print("=" * 50)
    print("📋 Sending broker profile in structured format:")
    print(broker_card_prompt)
    print("\n" + "=" * 50)
    
    try:
        # Configure client with longer timeout for complex broker card processing
        config = Config(read_timeout=120)
        client = boto3.client('bedrock-agentcore', region_name='us-east-1', config=config)
        
        response = client.invoke_agent_runtime(
            agentRuntimeArn=runtime_arn,
            payload=json.dumps({"prompt": broker_card_prompt})
        )
        
        if 'response' in response:
            result = response['response'].read().decode('utf-8')
            print("✅ Agent Response to Broker Card:")
            print(result)
            print("\n" + "=" * 50)
            
            # Test 2: Ask for market analysis - Should be personalized based on stored profile
            print("🧪 Testing Personalized Market Analysis...")
            print("📋 Follow-up question: 'It's Maria Rodriguez, What's the latest news on cryptocurrency and fintech stocks?'")
            print("\n" + "=" * 50)
            
            analysis_prompt = "It's Maria Rodriguez, What's the latest news on cryptocurrency and fintech stocks?"
            
            response2 = client.invoke_agent_runtime(
                agentRuntimeArn=runtime_arn,
                payload=json.dumps({"prompt": analysis_prompt})
            )
            
            if 'response' in response2:
                result2 = response2['response'].read().decode('utf-8')
                print("✅ Personalized Market Analysis:")
                print(result2)
                
                # Check if response is personalized
                personalization_indicators = ['maria', 'jp morgan', 'aggressive', 'cryptocurrency', 'fintech', 'gaming', 'growth investing', 'millennial', 'blockchain', 'nft', 'metaverse']
                found_indicators = [indicator for indicator in personalization_indicators 
                                  if indicator in result2.lower()]
                
                if found_indicators:
                    print("\n🎯 SUCCESS: Response is personalized!")
                    print(f"   Found personalization indicators: {', '.join(found_indicators)}")
                else:
                    print("\n⚠️  WARNING: Response may not be fully personalized")
                    
                print("\n" + "=" * 50)
                print("✅ DEMONSTRATION COMPLETE")
                print("This shows how users should interact with the Market Trends Agent:")
                print("1. Send broker profile in structured format (as shown above)")
                print("2. Agent automatically parses and stores the profile")
                print("3. All future market analysis is personalized to their profile")
            
        else:
            print("❌ No response received")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def show_broker_card_template():
    """Show users the expected broker card format"""
    print("\n📋 BROKER CARD TEMPLATE")
    print("=" * 50)
    print("Copy and paste this template, filling in your information:")
    print()
    template = """Name: [Your Full Name]
Company: [Your Company/Firm]
Role: [Your Role/Title]
Preferred News Feed: [Bloomberg, WSJ, Reuters, etc.]
Industry Interests: [technology, healthcare, energy, etc.]
Investment Strategy: [growth, value, dividend, etc.]
Risk Tolerance: [conservative, moderate, aggressive]
Client Demographics: [retail, institutional, high net worth, etc.]
Geographic Focus: [North America, Europe, Asia-Pacific, etc.]
Recent Interests: [specific sectors, trends, or companies]"""
    
    print(template)
    print("\n" + "=" * 50)

if __name__ == "__main__":
    print("🚀 Market Trends Agent - Broker Card Demonstration")
    print("=" * 60)
    
    # Show template first
    show_broker_card_template()
    
    # Run the test
    test_broker_card_conversation()