#!/usr/bin/env python3
"""
Test script to verify memory deployment and agent functionality
"""

import os
import sys
import boto3
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_ssm_memory_parameter():
    """Test that memory ARN is stored in SSM Parameter Store"""
    logger.info("🧠 Testing SSM memory parameter...")

    region = os.getenv("AWS_REGION", "us-east-1")
    ssm_client = boto3.client("ssm", region_name=region)
    param_name = "/bedrock-agentcore/market-trends-agent/memory-arn"

    try:
        response = ssm_client.get_parameter(Name=param_name)
        memory_arn = response["Parameter"]["Value"]
        logger.info(f"✅ Memory ARN found in SSM: {memory_arn}")

        # Validate ARN format
        if (
            memory_arn.startswith("arn:aws:bedrock-agentcore:")
            and "memory/" in memory_arn
        ):
            logger.info("✅ Memory ARN format is valid")
            return memory_arn
        else:
            logger.error(f"❌ Invalid memory ARN format: {memory_arn}")
            return None

    except ssm_client.exceptions.ParameterNotFound:
        logger.error("❌ Memory ARN not found in SSM Parameter Store")
        return None
    except Exception as e:
        logger.error(f"❌ Error retrieving memory ARN: {e}")
        return None


def test_memory_access():
    """Test that we can access the memory using the SSM parameter"""
    logger.info("🔍 Testing memory access...")

    try:
        # Import the memory function
        sys.path.append(str(Path(__file__).parent))
        from tools.memory_tools import get_memory_from_ssm

        # Try to get memory client and ID
        memory_client, memory_id = get_memory_from_ssm()
        logger.info(f"✅ Successfully retrieved memory: {memory_id}")

        # Test listing memories to verify access
        memories = memory_client.list_memories()
        logger.info(f"✅ Memory client working - found {len(memories)} total memories")

        return True

    except Exception as e:
        logger.error(f"❌ Error accessing memory: {e}")
        return False


def test_agent_runtime():
    """Test that the agent runtime is deployed and accessible"""
    logger.info("🎯 Testing agent runtime...")

    # Check if agent ARN file exists
    arn_file = Path(".agent_arn")
    if not arn_file.exists():
        logger.error("❌ Agent ARN file not found")
        return False

    try:
        with open(arn_file, "r") as f:
            agent_arn = f.read().strip()

        logger.info(f"✅ Agent ARN found: {agent_arn}")

        # Validate ARN format
        if (
            agent_arn.startswith("arn:aws:bedrock-agentcore:")
            and "runtime/" in agent_arn
        ):
            logger.info("✅ Agent ARN format is valid")
            return agent_arn
        else:
            logger.error(f"❌ Invalid agent ARN format: {agent_arn}")
            return None

    except Exception as e:
        logger.error(f"❌ Error reading agent ARN: {e}")
        return None


def test_agent_invocation():
    """Test invoking the agent via AgentCore Runtime"""
    logger.info("💬 Testing agent invocation via AgentCore Runtime...")

    try:
        # Get agent ARN
        arn_file = Path(".agent_arn")
        if not arn_file.exists():
            logger.error("❌ Agent ARN file not found")
            return False

        with open(arn_file, "r") as f:
            agent_arn = f.read().strip()

        # Use boto3 bedrock-agentcore client to invoke
        import boto3
        import json

        region = os.getenv("AWS_REGION", "us-east-1")
        client = boto3.client("bedrock-agentcore", region_name=region)

        # Test with a simple message
        test_payload = {
            "prompt": "Hello, I'm Tim Dunk from Goldman Sachs. Can you help me with market analysis?"
        }

        logger.info("Sending test message to deployed agent...")
        response = client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn, payload=json.dumps(test_payload).encode("utf-8")
        )

        if response and "response" in response:
            # Read the streaming body
            response_body = response["response"].read().decode("utf-8")
            if response_body and len(response_body.strip()) > 0:
                logger.info("✅ Agent responded successfully via AgentCore Runtime")
                logger.info(f"Response preview: {response_body[:200]}...")
                return True
            else:
                logger.error("❌ Agent returned empty response body")
                logger.info(f"Status code: {response.get('statusCode')}")
                return False
        else:
            logger.error("❌ Agent returned no response")
            logger.info(f"Full response: {response}")
            return False

    except Exception as e:
        logger.error(f"❌ Error invoking agent via runtime: {e}")
        logger.warning(
            "⚠️  Agent invocation failed - this indicates the agent may not be properly deployed"
        )
        return False


def main():
    """Run all tests"""
    logger.info("🧪 Market Trends Agent Memory Deployment Test")
    logger.info("=" * 60)

    tests_passed = 0
    total_tests = 4

    # Test 1: SSM Parameter
    memory_arn = test_ssm_memory_parameter()
    if memory_arn:
        tests_passed += 1

    logger.info("-" * 60)

    # Test 2: Memory Access
    if test_memory_access():
        tests_passed += 1

    logger.info("-" * 60)

    # Test 3: Agent Runtime
    agent_arn = test_agent_runtime()
    if agent_arn:
        tests_passed += 1

    logger.info("-" * 60)

    # Test 4: Agent Invocation
    if test_agent_invocation():
        tests_passed += 1

    logger.info("=" * 60)
    logger.info(f"📊 Test Results: {tests_passed}/{total_tests} tests passed")

    if tests_passed == total_tests:
        logger.info("🎉 All tests passed! Memory deployment is working correctly.")
        logger.info(
            "💡 The agent is ready for use with memory stored in SSM Parameter Store."
        )
    else:
        logger.error(
            f"❌ {total_tests - tests_passed} tests failed. Please check the deployment."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
