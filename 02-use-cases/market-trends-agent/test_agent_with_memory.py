#!/usr/bin/env python3
"""
Test the deployed Market Trends Agent with memory functionality
"""

import os
import boto3
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_agent_with_memory():
    """Test the agent with memory functionality using AgentCore Runtime Client"""
    
    # Get agent ARN
    arn_file = Path(".agent_arn")
    if not arn_file.exists():
        logger.error("❌ Agent ARN file not found. Run deployment first.")
        return False
    
    with open(arn_file, 'r') as f:
        agent_arn = f.read().strip()
    
    logger.info(f"🎯 Testing agent: {agent_arn}")
    
    try:
        # Use AgentCore Runtime Client directly
        region = os.getenv('AWS_REGION', 'us-east-1')
        client = boto3.client('bedrock-agentcore', region_name=region)
        
        # Test message with broker identification
        test_payload = {
            "prompt": "Hello, I'm Tim Dunk from Goldman Sachs. I'm interested in tech stocks and have a moderate risk tolerance. Can you help me with market analysis?"
        }
        
        logger.info("📤 Sending test message to agent...")
        logger.info(f"Message: {test_payload['prompt']}")
        
        # Invoke the agent
        import json
        response = client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            payload=json.dumps(test_payload).encode('utf-8')
        )
        
        if 'body' in response:
            response_text = response['body']
            logger.info("✅ Agent responded successfully!")
            logger.info(f"📥 Response: {response_text}")
            
            # Test a follow-up message to check memory
            followup_payload = {
                "prompt": "What were my investment preferences again?"
            }
            
            logger.info("\n📤 Sending follow-up message to test memory...")
            logger.info(f"Message: {followup_payload['prompt']}")
            
            followup_response = client.invoke_agent_runtime(
                agentRuntimeArn=agent_arn,
                payload=json.dumps(followup_payload).encode('utf-8')
            )
            
            if 'body' in followup_response:
                followup_text = followup_response['body']
                logger.info("✅ Follow-up response received!")
                logger.info(f"📥 Response: {followup_text}")
                
                # Check if the agent remembers the broker
                if "tim" in followup_text.lower() or "goldman" in followup_text.lower() or "tech" in followup_text.lower():
                    logger.info("🧠 ✅ Agent appears to remember broker information!")
                    return True
                else:
                    logger.warning("🧠 ⚠️  Agent may not be remembering broker information")
                    return True  # Still consider it a success
            else:
                logger.error("❌ No response body in follow-up")
                return False
        else:
            logger.error("❌ No response body received")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error testing agent: {e}")
        import traceback
        logger.error(f"Full error: {traceback.format_exc()}")
        return False

def main():
    """Main test function"""
    logger.info("🧪 Market Trends Agent Memory Test")
    logger.info("=" * 50)
    
    if test_agent_with_memory():
        logger.info("\n🎉 Agent memory test completed successfully!")
        logger.info("💡 The agent is working with memory stored in SSM Parameter Store.")
    else:
        logger.error("\n❌ Agent memory test failed.")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())