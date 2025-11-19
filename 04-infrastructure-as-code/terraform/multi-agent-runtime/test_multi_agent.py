#!/usr/bin/env python3
"""
Multi-Agent System Test Script

This script tests a multi-agent system with Agent-to-Agent (A2A) communication.
It can work with agents deployed via any method (Terraform, CloudFormation, CDK, manual).

Usage:
    python test_multi_agent.py <agent1_arn> [agent2_arn]
    
    agent1_arn: ARN of the orchestrator agent (required)
    agent2_arn: ARN of the specialist agent (optional, for independent testing)

Examples:
    # Test orchestrator with A2A communication
    python test_multi_agent.py arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/agent1-id
    
    # Test both agents independently
    python test_multi_agent.py \\
        arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/agent1-id \\
        arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/agent2-id
"""

import boto3
import json
import sys

def test_agent(client, agent_arn, agent_name, prompt):
    """Test a single agent with a given prompt
    
    Args:
        client: boto3 bedrock-agentcore client
        agent_arn: ARN of the agent runtime
        agent_name: Name for display purposes
        prompt: Test prompt to send
    """
    print(f"\nPrompt: '{prompt}'")
    print("-" * 80)
    
    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            qualifier="DEFAULT",
            payload=json.dumps({"prompt": prompt})
        )
        
        print(f"Status: {response['ResponseMetadata']['HTTPStatusCode']}")
        print(f"Content Type: {response.get('contentType', 'N/A')}")
        
        # Read the streaming response body
        response_text = ""
        if 'response' in response:
            response_body = response['response'].read()
            response_text = response_body.decode('utf-8')
        
        if response_text:
            try:
                result = json.loads(response_text)
                response_content = result.get('response', response_text)
                # Truncate long responses for readability
                if len(response_content) > 500:
                    print(f"\n✅ Response:\n{response_content[:500]}...")
                    print("\n[Response truncated for display]")
                else:
                    print(f"\n✅ Response:\n{response_content}")
            except json.JSONDecodeError:
                if len(response_text) > 500:
                    print(f"\n✅ Response:\n{response_text[:500]}...")
                else:
                    print(f"\n✅ Response:\n{response_text}")
        else:
            print("\n⚠️  No response content received")
        
        return True
                
    except Exception as e:
        print(f"\n❌ Error testing {agent_name}: {e}")
        return False

def test_multi_agent(agent1_arn, agent2_arn=None):
    """Test the multi-agent system
    
    Args:
        agent1_arn: Agent1 (Orchestrator) runtime ARN (required)
        agent2_arn: Agent2 (Specialist) runtime ARN (optional)
    """
    
    print("\n" + "="*80)
    print("MULTI-AGENT SYSTEM TEST")
    print("="*80)
    print(f"\nAgent1 (Orchestrator) ARN: {agent1_arn}")
    if agent2_arn:
        print(f"Agent2 (Specialist) ARN: {agent2_arn}")
    else:
        print("Agent2: Not provided (will test Agent1 only)")
    
    # Create bedrock-agentcore client
    agentcore_client = boto3.client('bedrock-agentcore', region_name='us-west-2')
    
    test_results = []
    
    # Test 1: Simple query to Agent1
    print("\n" + "="*80)
    print("TEST 1: Simple Query (Agent1)")
    print("="*80)
    result = test_agent(
        agentcore_client,
        agent1_arn,
        "Agent1",
        "Hello! Can you introduce yourself and your capabilities?"
    )
    test_results.append(("Simple Query", result))
    
    # Test 2: Complex query triggering A2A communication
    print("\n" + "="*80)
    print("TEST 2: Complex Query with A2A Communication")
    print("="*80)
    result = test_agent(
        agentcore_client,
        agent1_arn,
        "Agent1",
        "I need expert analysis. Please coordinate with the specialist agent to provide a comprehensive explanation of cloud computing architectures and best practices."
    )
    test_results.append(("A2A Communication Test", result))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    all_passed = True
    for test_name, passed in test_results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status} - {test_name}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*80)
    if all_passed:
        print("✅ ALL TESTS PASSED")
    else:
        print("⚠️  SOME TESTS FAILED")
    print("="*80 + "\n")
    
    return all_passed

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print(__doc__)
        print("\n❌ ERROR: Agent runtime ARN is required")
        print("\nTo get your agent ARN:")
        print("  - Terraform: terraform output agent1_runtime_arn")
        print("  - CloudFormation: aws cloudformation describe-stacks --stack-name <stack> --query 'Stacks[0].Outputs'")
        print("  - CDK: cdk deploy --outputs-file outputs.json")
        print("  - Console: Check Bedrock Agent Core console")
        sys.exit(1)
    
    agent1_arn = sys.argv[1]
    agent2_arn = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Validate ARN format
    if not agent1_arn.startswith("arn:aws:bedrock-agentcore:"):
        print(f"\n❌ ERROR: Invalid ARN format for agent1: {agent1_arn}")
        print("Expected format: arn:aws:bedrock-agentcore:region:account:runtime/runtime-id")
        sys.exit(1)
    
    if agent2_arn and not agent2_arn.startswith("arn:aws:bedrock-agentcore:"):
        print(f"\n❌ ERROR: Invalid ARN format for agent2: {agent2_arn}")
        print("Expected format: arn:aws:bedrock-agentcore:region:account:runtime/runtime-id")
        sys.exit(1)
    
    # Run tests
    success = test_multi_agent(agent1_arn, agent2_arn)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
