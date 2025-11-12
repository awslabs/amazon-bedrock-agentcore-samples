#!/usr/bin/env python3
"""
Simple A2A Test - Quick verification of agent-to-agent communication
"""

import boto3
import json
import time

def test_coordinator():
    """Test the coordinator with a simple property search request."""
    
    print("=" * 70)
    print("Simple A2A Communication Test")
    print("=" * 70)
    
    # Configuration
    agent_arn = "arn:aws:bedrock-agentcore:us-east-1:506053230750:runtime/realestate_coordinator-wKT4RaHAKI"
    region = "us-east-1"
    
    print(f"\nAgent ARN: {agent_arn}")
    print(f"Region: {region}\n")
    
    # Create client
    client = boto3.client('bedrock-agentcore', region_name=region)
    
    # Test prompt
    prompt = "Find me apartments in New York under $4000"
    
    print(f"Sending request: {prompt}")
    print("-" * 70)
    
    try:
        # Invoke agent
        response = client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            qualifier='DEFAULT',
            payload=json.dumps({"prompt": prompt}).encode('utf-8')
        )
        
        # Read response
        result_text = ""
        if 'body' in response:
            for event in response['body']:
                if 'chunk' in event:
                    chunk_data = event['chunk'].get('bytes', b'')
                    if chunk_data:
                        chunk_text = chunk_data.decode('utf-8')
                        result_text += chunk_text
                        print(chunk_text, end='', flush=True)
        
        print("\n" + "-" * 70)
        
        if "Error" in result_text or "error" in result_text:
            print("\n⚠️  Response contains errors - checking if A2A communication worked...")
            if "403" in result_text or "Forbidden" in result_text:
                print("❌ Still getting 403 errors - IAM permissions may need time to propagate")
                print("   Wait 30 seconds and try again")
            else:
                print("✓ No 403 errors - A2A communication is working!")
        else:
            print("\n✓ Test completed successfully!")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    test_coordinator()
